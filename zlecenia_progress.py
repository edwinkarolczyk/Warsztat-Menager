# WM-VERSION: 0.1
# Plik: zlecenia_progress.py
# version: 1.1
# Bezpieczne rozliczanie postepu zlecen produkcyjnych.
# 1.1:
# - planowanie tylko pozostalej ilosci,
# - nadprodukcja trafia do magazynu polproduktow tylko raz,
# - rozliczenie wykonania nie zwalnia cudzych rezerwacji,
# - walidacja stanow przed zuzyciem zapobiega czesciowemu rozliczeniu,
# - wykonano nie moze przekroczyc ilosci zlecenia,
# - nieaktualne dyspozycje brakow surowca sa wstrzymywane.

from __future__ import annotations

from datetime import datetime

import bom
import logika_magazyn as LM
import zlecenia_logika as ZL


def _f(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _remaining_overrides(order, remaining):
    overrides = order.get("korekty_polproduktow") or {}
    if not overrides:
        return None
    done = _f(order.get("wykonano"))
    completed = (
        bom.compute_bom_for_prd(order["produkt"], done, version=order.get("version"))
        if done > 0
        else {}
    )
    out = {}
    for code, total in overrides.items():
        already = _f((completed.get(code) or {}).get("ilosc"))
        out[str(code)] = max(0.0, _f(total) - already)
    return out


def _replan_remaining(order, kto="system"):
    """Zwalnia tylko rezerwacje tego zlecenia i planuje pozostala ilosc."""
    ZL._release_reservations(
        order.get("rezerwacje_polprodukty"), kto, f"przeliczenie:{order.get('id')}"
    )
    ZL._release_reservations(
        order.get("rezerwacje_surowce"), kto, f"przeliczenie:{order.get('id')}"
    )
    order["rezerwacje_polprodukty"] = {}
    order["rezerwacje_surowce"] = {}

    remaining = max(0.0, _f(order.get("ilosc")) - _f(order.get("wykonano")))
    plan, raw = ZL.build_production_plan(
        order["produkt"],
        remaining,
        cut_mm=(
            _f(order.get("rzaz_mm"))
            if order.get("rzaz_mm") is not None
            else ZL.DEFAULT_CUT_MM
        ),
        version=order.get("version"),
        overrides=_remaining_overrides(order, remaining),
    )
    order["pozostalo"] = remaining
    order["plan_polprodukty"] = plan
    order["zapotrzebowanie_surowce"] = raw
    order["braki"] = ZL.check_materials(raw, 1)

    if remaining > 0:
        order["rezerwacje_polprodukty"] = ZL._reserve_semis(
            plan, kto, f"zlecenie:{order.get('id')}"
        )
        _unused, order["rezerwacje_surowce"] = ZL.reserve_materials(
            raw,
            1,
            user=kto,
            context=f"zlecenie:{order.get('id')}",
            with_reserved=True,
        )
    order["materialy_zarezerwowane"] = bool(remaining > 0)
    return order


def _ensure_semi_item(code):
    rec = LM.get_item(code)
    if rec:
        return rec
    card = bom.get_polprodukt(code)
    return LM.upsert_item(
        {
            "id": code,
            "nazwa": card.get("nazwa") or code,
            "typ": "półprodukt",
            "jednostka": "szt",
            "stan": 0,
            "min_poziom": 0,
            "rezerwacje": 0,
        }
    )


def _credit_new_surplus(order, old_qty, new_qty, kto):
    """Ksiegowanie nowej nadprodukcji do magazynu polproduktow, bez duplikatow."""
    done = _f(order.get("wykonano"))
    old_over = max(0.0, done - _f(old_qty))
    new_over = max(0.0, done - _f(new_qty))
    credited = _f(order.get("nadprodukcja_zaksiegowana_prod"))
    target = max(old_over, new_over)
    delta_prod = max(0.0, target - credited)
    if delta_prod <= 0:
        return {}

    expanded = bom.compute_bom_for_prd(
        order["produkt"], delta_prod, version=order.get("version")
    )
    credited_semis = {}
    for code, rec in expanded.items():
        qty = _f(rec.get("ilosc"))
        if qty <= 0:
            continue
        _ensure_semi_item(code)
        LM.zwrot(code, qty, kto, kontekst=f"nadprodukcja:{order.get('id')}")
        credited_semis[code] = qty

    order["nadprodukcja_zaksiegowana_prod"] = credited + delta_prod
    if credited_semis:
        order.setdefault("historia", []).append(
            {
                "kiedy": datetime.now().isoformat(timespec="seconds"),
                "kto": kto,
                "co": f"nadprodukcja -> magazyn półproduktów ({delta_prod:g} produktu)",
                "polprodukty": credited_semis,
            }
        )
    return credited_semis


def _sync_material_dispositions(order, kto="system"):
    try:
        import dyspozycje_store as DS
    except Exception:
        return

    oid = str(order.get("id") or "")
    active_codes = {str(x.get("kod") or "") for x in (order.get("braki") or [])}
    prefix = f"zlecenie:{oid}:surowiec:"
    for disp in DS.load_dyspozycje():
        object_id = str(disp.get("obiekt_id") or "")
        if disp.get("typ_dyspozycji") != "magazyn" or not object_id.startswith(prefix):
            continue
        code = object_id[len(prefix) :]
        if code not in active_codes and disp.get("status") not in {"zamknieta", "wstrzymana"}:
            DS.update_dyspozycja(
                disp["id"],
                {
                    "status": "wstrzymana",
                    "opis": f"Brak surowca dla zlecenia {oid} już nie występuje.",
                },
            )
    ZL._sync_material_dispositions(order, autor=kto)


def update_zlecenie(
    zlec_id,
    *,
    ilosc=None,
    uwagi=None,
    zlec_wew=None,
    termin=None,
    rzaz_mm=None,
    korekty_polproduktow=None,
    kto="system",
):
    p = ZL._order_path(zlec_id)
    order = ZL._read_json(p)
    old_qty = _f(order.get("ilosc"))
    changed, replan = [], False

    if ilosc is not None:
        new_qty = float(ilosc)
        if new_qty < 0:
            raise ValueError("Ilość nie może być ujemna.")
        if new_qty != old_qty:
            order["ilosc"] = new_qty
            replan = True
            changed.append(f"ilosc -> {new_qty:g}")
            _credit_new_surplus(order, old_qty, new_qty, kto)

    if rzaz_mm is not None:
        cut = float(rzaz_mm)
        if cut < 0:
            raise ValueError("Rzaz nie może być ujemny.")
        if cut != _f(order.get("rzaz_mm", ZL.DEFAULT_CUT_MM)):
            order["rzaz_mm"] = cut
            replan = True
            changed.append(f"rzaz_mm -> {cut:g}")

    if korekty_polproduktow is not None:
        vals = {str(k): float(v) for k, v in korekty_polproduktow.items()}
        if any(v < 0 for v in vals.values()):
            raise ValueError("Ilość półproduktu nie może być ujemna.")
        order["korekty_polproduktow"] = vals
        replan = True
        changed.append("korekty półproduktów")

    if termin is not None and str(order.get("termin") or "") != str(termin or ""):
        order["termin"] = str(termin or "")
        changed.append(f"termin -> {order['termin']}")
    if uwagi is not None and order.get("uwagi") != uwagi:
        order["uwagi"] = uwagi
        changed.append("uwagi")
    if zlec_wew is not None and order.get("zlec_wew") != zlec_wew:
        if zlec_wew in ("", None):
            order.pop("zlec_wew", None)
        else:
            order["zlec_wew"] = zlec_wew
        changed.append(f"zlec_wew -> {zlec_wew}")

    if replan:
        _replan_remaining(order, kto)
    if changed:
        order.setdefault("historia", []).append(
            {
                "kiedy": datetime.now().isoformat(timespec="seconds"),
                "kto": kto,
                "co": "; ".join(changed),
            }
        )
        ZL._write_json(p, order)
        ZL._sync_execution_disposition(order, autor=kto)
        _sync_material_dispositions(order, kto)
    return order


def _planned_consumption(order, factor):
    semis = {
        code: _f(total) * factor
        for code, total in (order.get("rezerwacje_polprodukty") or {}).items()
        if _f(total) * factor > 0
    }
    raw = {
        code: _f(data.get("ilosc")) * factor
        for code, data in (order.get("zapotrzebowanie_surowce") or {}).items()
        if isinstance(data, dict) and _f(data.get("ilosc")) * factor > 0
    }
    return semis, raw


def _validate_stock_before_consumption(semis, raw):
    shortages = []
    for code, amount in {**semis, **raw}.items():
        rec = LM.get_item(code) or {}
        state = _f(rec.get("stan"))
        if state + 1e-9 < amount:
            shortages.append(f"{code}: potrzeba {amount:g}, stan {state:g}")
    if shortages:
        raise ValueError(
            "Nie można rozliczyć wykonania — stan magazynowy jest za mały:\n"
            + "\n".join(shortages)
        )


def _consume_mapping(order, mapping_name, consumption, kto, context):
    mapping = dict(order.get(mapping_name) or {})
    for code, amount in consumption.items():
        rec = LM.get_item(code) or {}
        reserved_for_order = _f(mapping.get(code))
        release = min(_f(rec.get("rezerwacje")), reserved_for_order, amount)
        if release > 0:
            LM.zwolnij_rezerwacje(code, release, kto, kontekst=context)
        LM.zuzyj(code, amount, kto, kontekst=context)
        mapping[code] = max(0.0, reserved_for_order - release)
    order[mapping_name] = {k: v for k, v in mapping.items() if _f(v) > 1e-9}


def report_wykonano(zlec_id, wykonano, kto="system"):
    p = ZL._order_path(zlec_id)
    order = ZL._read_json(p)
    old, new = _f(order.get("wykonano")), float(wykonano)
    qty = _f(order.get("ilosc"))

    if new < old:
        raise ValueError("Nie można zmniejszyć ilości już rozliczonej.")
    if new < 0:
        raise ValueError("Wykonana ilość nie może być ujemna.")
    if new > qty + 1e-9:
        raise ValueError(
            "Wykonano nie może przekraczać ilości zlecenia. "
            "Najpierw zwiększ ilość produktu w zleceniu."
        )

    delta = new - old
    if delta <= 0:
        return order

    remaining_before = max(0.0, qty - old)
    factor = delta / remaining_before if remaining_before > 0 else 0.0
    factor = max(0.0, min(1.0, factor))
    context = f"wykonanie:{zlec_id}"

    semis, raw = _planned_consumption(order, factor)
    _validate_stock_before_consumption(semis, raw)

    _consume_mapping(
        order, "rezerwacje_polprodukty", semis, kto, context
    )

    # Surowiec ma osobna mape rezerwacji, ale ilosc zuzycia pochodzi z planu surowcow.
    raw_reservations = dict(order.get("rezerwacje_surowce") or {})
    for code, amount in raw.items():
        rec = LM.get_item(code) or {}
        reserved_for_order = _f(raw_reservations.get(code))
        release = min(_f(rec.get("rezerwacje")), reserved_for_order, amount)
        if release > 0:
            LM.zwolnij_rezerwacje(code, release, kto, kontekst=context)
        LM.zuzyj(code, amount, kto, kontekst=context)
        raw_reservations[code] = max(0.0, reserved_for_order - release)
    order["rezerwacje_surowce"] = {
        k: v for k, v in raw_reservations.items() if _f(v) > 1e-9
    }

    order["wykonano"] = new
    if qty > 0 and new >= qty:
        order["status"] = "zakończone"
    elif new > 0 and order.get("status") == "nowe":
        order["status"] = "w trakcie"

    order.setdefault("historia", []).append(
        {
            "kiedy": datetime.now().isoformat(timespec="seconds"),
            "kto": kto,
            "co": f"wykonano -> {new:g}",
        }
    )

    _replan_remaining(order, kto)
    ZL._write_json(p, order)
    ZL._sync_execution_disposition(order, autor=kto)
    _sync_material_dispositions(order, kto)
    return order
