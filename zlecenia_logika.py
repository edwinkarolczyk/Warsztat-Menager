# =============================
# FILE: zlecenia_logika.py
# version: 2.0.4
# Zmiany 2.0.4:
# - zapotrzebowanie liniowe zna standardową długość sztangi i liczy liczbę sztang do cięcia;
# - liczba sztang uwzględnia długości odcinków, rzaz na każdą sztukę i normę strat.
# Zmiany 2.0.3:
# - zlecenie może jawnie zezwolić na nadprodukcję rozliczaną do Magazynu.
# Zmiany 2.0.2:
# - usunięcie zlecenia zwalnia jego rezerwacje i usuwa powiązane Dyspozycje.
# Zmiany 2.0.1:
# - zachowano zgodność API reserve_materials: domyślnie zwraca mapę dostępnych stanów.
# Zmiany 2.0:
# - aktywny WM_DATA_ROOT zamiast sztywnego ./data
# - zlecenie zapisuje termin, rzaz_mm i wykonano
# - plan półproduktów uwzględnia stan/rezerwacje półproduktów
# - surowiec liczony tylko dla półproduktów do wykonania
# - rzaz (domyślnie 2 mm) jest doliczany do każdej wykonywanej sztuki
# - brak materiału nie blokuje zlecenia; zapisuje ostrzeżenie
# - tworzenie zlecenia automatycznie tworzy Dyspozycję wykonania
# - braki surowca mogą automatycznie tworzyć Dyspozycje typu magazyn
# - zmiana terminu/ilości synchronizuje plan, rezerwacje i Dyspozycję
# - anulowanie wstrzymuje Dyspozycję i zwalnia niewykorzystane rezerwacje
# - wpisanie wykonanej ilości rozlicza proporcjonalne zużycie materiału
# =============================

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import math

import bom
import logika_magazyn as LM
from config_manager import ConfigManager
from utils.json_io import _ensure_dirs as _ensure_dirs_impl, _read_json, _write_json

STATUSY = ["do akceptacji", "nowe", "w przygotowaniu", "w trakcie", "wstrzymane", "zakończone", "anulowane"]
DEFAULT_CUT_MM = 2.0


def _data_dir() -> Path:
    try:
        return Path(ConfigManager().path_data())
    except Exception:
        return Path("data")


def _paths():
    data = _data_dir()
    return data, data / "produkty", data / "magazyn", data / "zlecenia"


def _ensure_dirs():
    _data, bom_dir, mag_dir, orders_dir = _paths()
    _ensure_dirs_impl(orders_dir, bom_dir, mag_dir)


def _orders_dir() -> Path:
    _ensure_dirs()
    return _paths()[3]


def list_produkty():
    _ensure_dirs()
    out = []
    for f in _paths()[1].glob("*.json"):
        try:
            j = _read_json(f)
            out.append({"kod": j.get("kod") or j.get("symbol") or f.stem, "nazwa": j.get("nazwa") or f.stem})
        except Exception:
            continue
    return out


def read_bom(kod):
    p = _paths()[1] / f"{kod}.json"
    if not p.exists():
        raise FileNotFoundError(f"Brak BOM: {kod}")
    return _read_json(p)


def _canonical_magazyn_items():
    try:
        data = LM.load_magazyn(include_external=True)
        items = data.get("items") or data.get("pozycje") or {}
        return items if isinstance(items, dict) else {}
    except Exception:
        return {}


def read_magazyn():
    out = {}
    for kod, rec in _canonical_magazyn_items().items():
        if not isinstance(rec, dict):
            continue
        try:
            stan = float(rec.get("stan", 0) or 0)
        except Exception:
            stan = 0.0
        try:
            rez = max(0.0, float(rec.get("rezerwacje", 0) or 0))
        except Exception:
            rez = 0.0
        out[str(kod)] = {"nazwa": rec.get("nazwa", kod), "typ": rec.get("typ", ""), "stan": stan, "rezerwacje": rez, "dostepne": max(0.0, stan - rez), "jednostka": rec.get("jednostka", "")}
    return out


def check_materials(material_bom, ilosc=1):
    mag = read_magazyn()
    braki = []
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        rec = mag.get(kod, {})
        available = float(rec.get("dostepne", rec.get("stan", 0)) or 0)
        if available < req:
            braki.append({"kod": kod, "nazwa": rec.get("nazwa", kod), "potrzeba": req, "stan": float(rec.get("stan", 0) or 0), "zarezerwowane": float(rec.get("rezerwacje", 0) or 0), "dostepne": available, "brakuje": req - available, "jednostka": data.get("jednostka", rec.get("jednostka", ""))})
    return braki


def _semi_stock(code: str):
    rec = read_magazyn().get(code, {})
    return {"stan": float(rec.get("stan", 0) or 0), "rezerwacje": float(rec.get("rezerwacje", 0) or 0), "dostepne": float(rec.get("dostepne", 0) or 0)}


def _raw_definitions() -> dict[str, dict]:
    """Czyta definicje surowców Planisty z aktywnego WM_DATA_ROOT."""
    path = _paths()[2] / "surowce.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict] = {}
    if isinstance(payload, dict):
        iterable = []
        for key, value in payload.items():
            if isinstance(value, dict):
                rec = dict(value)
                rec.setdefault("kod", key)
                iterable.append(rec)
    elif isinstance(payload, list):
        iterable = payload
    else:
        iterable = []
    for rec in iterable:
        if not isinstance(rec, dict):
            continue
        code = str(rec.get("kod") or rec.get("id") or "").strip()
        if code:
            out[code] = dict(rec)
    return out


def _bars_for_cuts(cut_lengths_mm, bar_length_mm: float, total_need_mm: float):
    """Best-fit decreasing dla odcinków; wynik nie może być niższy niż potrzeba łączna."""
    bar_length = max(0.0, float(bar_length_mm or 0))
    total_need = max(0.0, float(total_need_mm or 0))
    cuts = [max(0.0, float(x or 0)) for x in cut_lengths_mm if float(x or 0) > 0]
    if bar_length <= 0:
        return {"sztangi_potrzebne": None, "odpad_mm": None, "blad_ciecia": "Brak standardowej długości sztangi."}
    too_long = [x for x in cuts if x > bar_length + 1e-9]
    if too_long:
        longest = max(too_long)
        return {
            "sztangi_potrzebne": None,
            "odpad_mm": None,
            "blad_ciecia": f"Odcinek {longest:g} mm jest dłuższy niż sztanga {bar_length:g} mm.",
        }

    remaining: list[float] = []
    for cut in sorted(cuts, reverse=True):
        best_idx = None
        best_after = None
        for idx, free in enumerate(remaining):
            if free + 1e-9 < cut:
                continue
            after = free - cut
            if best_after is None or after < best_after:
                best_idx, best_after = idx, after
        if best_idx is None:
            remaining.append(bar_length - cut)
        else:
            remaining[best_idx] -= cut

    bars_for_pieces = len(remaining)
    bars_for_total = int(math.ceil(total_need / bar_length - 1e-12)) if total_need > 0 else 0
    bars = max(bars_for_pieces, bars_for_total)
    return {
        "sztangi_potrzebne": bars,
        "odpad_mm": max(0.0, bars * bar_length - total_need),
        "blad_ciecia": "",
    }


def _attach_bar_plan(plan_pp: dict, raw_total: dict, cut_mm: float) -> dict:
    """Uzupełnia surowce liniowe o długość sztangi i realną liczbę sztang do pobrania."""
    definitions = _raw_definitions()
    cuts_by_raw: dict[str, list[float]] = {}

    for pp_code, rec in (plan_pp or {}).items():
        if not isinstance(rec, dict):
            continue
        sr = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
        raw_code = str(sr.get("kod") or sr.get("id") or "").strip()
        unit = str(sr.get("jednostka") or "").strip().lower()
        if not raw_code or unit not in {"mm", "milimetr", "milimetry", "milimetrów"}:
            continue
        try:
            piece = max(0.0, float(sr.get("ilosc_na_szt", 0) or 0)) + max(0.0, float(cut_mm or 0))
            qty = max(0.0, float(rec.get("do_wykonania", rec.get("ilosc", 0)) or 0))
        except Exception:
            continue
        if piece <= 0 or qty <= 0:
            continue
        count = int(math.ceil(qty - 1e-9))
        cuts_by_raw.setdefault(raw_code, []).extend([piece] * count)

    enriched: dict[str, dict] = {}
    for raw_code, raw_info in (raw_total or {}).items():
        if not isinstance(raw_info, dict):
            continue
        rec = dict(raw_info)
        definition = definitions.get(str(raw_code), {})
        try:
            bar_length = max(
                0.0,
                float(
                    definition.get(
                        "dlugosc_sztangi_mm",
                        definition.get(
                            "dlugosc",
                            rec.get("dlugosc_sztangi_mm", rec.get("dlugosc", 0)),
                        ),
                    )
                    or 0
                ),
            )
        except Exception:
            bar_length = 0.0
        rec["nazwa"] = definition.get("nazwa") or rec.get("nazwa") or raw_code
        rec["dlugosc_sztangi_mm"] = bar_length
        if str(rec.get("jednostka") or "").strip().lower() in {"mm", "milimetr", "milimetry", "milimetrów"}:
            plan = _bars_for_cuts(cuts_by_raw.get(str(raw_code), []), bar_length, rec.get("ilosc", 0))
            rec.update(plan)
            rec["rzaz_mm"] = max(0.0, float(cut_mm or 0))
        enriched[str(raw_code)] = rec
    return enriched


def material_bar_summary(order: dict) -> dict:
    """Zwraca aktualny plan sztang także dla starszych zleceń zapisanych bez tych pól."""
    raw = {
        str(code): dict(rec)
        for code, rec in (order.get("zapotrzebowanie_surowce") or {}).items()
        if isinstance(rec, dict)
    }
    return _attach_bar_plan(
        order.get("plan_polprodukty") or {},
        raw,
        float(order.get("rzaz_mm", DEFAULT_CUT_MM) or 0),
    )


def _raw_need_for_pp(kod_pp: str, qty: float, cut_mm: float):
    if qty <= 0:
        return {}
    card = bom.get_polprodukt(kod_pp)
    sr = card.get("surowiec") or {}
    raw_code = str(sr.get("kod") or sr.get("id") or "").strip()
    if not raw_code:
        raise KeyError(f"Półprodukt {kod_pp} nie ma przypisanego surowca")
    base = float(sr.get("ilosc_na_szt", 0) or 0)
    unit = str(sr.get("jednostka") or "").strip()
    if not unit:
        try:
            unit = next(iter(bom.compute_sr_for_pp(kod_pp, 1).values())).get("jednostka", "")
        except Exception:
            unit = ""
    per_piece = base
    if unit.strip().lower() in {"mm", "milimetr", "milimetry", "milimetrów"}:
        per_piece += max(0.0, float(cut_mm or 0))
    loss = float(card.get("norma_strat_procent", card.get("norma_strat_proc", 0)) or 0)
    return {raw_code: {"ilosc": per_piece * float(qty) * (1.0 + loss / 100.0), "jednostka": unit}}


def build_production_plan(kod_produktu, ilosc, *, cut_mm=DEFAULT_CUT_MM, version=None, overrides=None):
    raw_pp = bom.compute_bom_for_prd(kod_produktu, float(ilosc), version=version)
    overrides = overrides or {}
    plan_pp, raw_total = {}, {}
    for code, rec in raw_pp.items():
        calculated = float(rec.get("ilosc", 0) or 0)
        target = float(overrides.get(code, calculated) or 0)
        stock = _semi_stock(code)
        from_stock = min(target, stock["dostepne"])
        to_make = max(0.0, target - from_stock)
        plan_pp[code] = {"nazwa": rec.get("nazwa") or code, "potrzeba": target, "wyliczone": calculated, "z_magazynu": from_stock, "do_wykonania": to_make, "stan": stock["stan"], "zarezerwowane": stock["rezerwacje"], "czynnosci": list(rec.get("czynnosci") or []), "surowiec": dict(rec.get("surowiec") or {}), "norma_strat_procent": float(rec.get("norma_strat_procent", 0) or 0)}
        for raw_code, raw_info in _raw_need_for_pp(code, to_make, cut_mm).items():
            ent = raw_total.setdefault(raw_code, {"ilosc": 0.0, "jednostka": raw_info.get("jednostka", "")})
            ent["ilosc"] += float(raw_info.get("ilosc", 0) or 0)
    return plan_pp, _attach_bar_plan(plan_pp, raw_total, cut_mm)


def compute_material_needs(kod_produktu, ilosc=1, version=None, cut_mm=DEFAULT_CUT_MM, overrides=None):
    _plan_pp, bom_sr = build_production_plan(kod_produktu, ilosc, cut_mm=cut_mm, version=version, overrides=overrides)
    mag, potrzeby = read_magazyn(), []
    for kod, data in bom_sr.items():
        req = float(data["ilosc"])
        rec = mag.get(kod, {})
        stan = float(rec.get("stan", 0) or 0)
        rez = float(rec.get("rezerwacje", 0) or 0)
        available = float(rec.get("dostepne", max(0.0, stan - rez)) or 0)
        potrzeby.append({"kod": kod, "jednostka": data.get("jednostka", rec.get("jednostka", "")), "potrzeba": req, "stan": stan, "zarezerwowane": rez, "dostepne": available, "brakuje": max(0.0, req - available)})
    return potrzeby, bom_sr


def reserve_materials(material_bom, ilosc=1, user="system", context=None, with_reserved=False):
    updated, reserved = {}, {}
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        try:
            actual = float(LM.rezerwuj(kod, req, user, kontekst=context or "zlecenie_produkcyjne") or 0)
            reserved[kod] = actual
            rec = LM.get_item(kod) or {}
            stan, rez = float(rec.get("stan", 0) or 0), float(rec.get("rezerwacje", 0) or 0)
            updated[kod] = max(0.0, stan - rez)
        except KeyError:
            updated[kod], reserved[kod] = 0.0, 0.0
    return (updated, reserved) if with_reserved else updated


def rezerwuj_materialy(material_bom, ilosc=1):
    return reserve_materials(material_bom, ilosc)


def _reserve_semis(plan_pp, user, context):
    reserved = {}
    for code, rec in plan_pp.items():
        qty = float(rec.get("z_magazynu", 0) or 0)
        if qty <= 0:
            continue
        try:
            reserved[code] = float(LM.rezerwuj(code, qty, user, kontekst=context) or 0)
        except KeyError:
            reserved[code] = 0.0
    return reserved


def _release_reservations(mapping, user, context):
    for code, qty in (mapping or {}).items():
        amount = float(qty or 0)
        if amount <= 0:
            continue
        try:
            rec = LM.get_item(code) or {}
            actual = min(float(rec.get("rezerwacje", 0) or 0), amount)
            if actual > 0:
                LM.zwolnij_rezerwacje(code, actual, user, kontekst=context)
        except Exception:
            continue


def _find_disposition_for_order(order_id):
    try:
        import dyspozycje_store as DS
        object_id = f"zlecenie:{order_id}"
        for item in DS.load_dyspozycje():
            if item.get("typ_dyspozycji") == "zlecenie_wykonania" and item.get("obiekt_id") == object_id:
                return item
    except Exception:
        pass
    return None


def _sync_execution_disposition(order, autor="system"):
    try:
        import dyspozycje_store as DS
    except Exception:
        return None
    oid, plan = str(order.get("id") or ""), order.get("plan_polprodukty") or {}
    title = f"Wykonanie produktu {order.get('produkt', '')} — zlecenie {oid}"
    rows = [f"{rec.get('nazwa') or code}: potrzeba {rec.get('potrzeba', 0)}, z magazynu {rec.get('z_magazynu', 0)}, do wykonania {rec.get('do_wykonania', 0)}" for code, rec in plan.items() if isinstance(rec, dict)]
    meta = {"zlecenie_id": oid, "produkt": order.get("produkt", ""), "ilosc": order.get("ilosc", 0), "wykonano": order.get("wykonano", 0), "rzaz_mm": order.get("rzaz_mm", DEFAULT_CUT_MM), "plan_polprodukty": plan}
    existing = _find_disposition_for_order(oid)
    payload = {"tytul": title, "opis": "\n".join(rows), "termin": str(order.get("termin") or ""), "meta": meta}
    if existing:
        # Preserve status history/closure metadata when Planista refreshes the order.
        # Only the order-derived keys are updated, never replace the whole meta.
        payload["meta"] = {**dict(existing.get("meta") or {}), **meta}
        return DS.update_dyspozycja(existing["id"], payload)
    return DS.add_dyspozycja(DS.make_dyspozycja(typ_dyspozycji="zlecenie_wykonania", tytul=title, opis=payload["opis"], autor=autor, termin=payload["termin"], modul_zrodlowy="zlecenia", obiekt_id=f"zlecenie:{oid}", meta=meta))


def _sync_material_dispositions(order, autor="system"):
    try:
        import dyspozycje_store as DS
    except Exception:
        return []
    created, oid, existing = [], str(order.get("id") or ""), DS.load_dyspozycje()
    for shortage in order.get("braki") or []:
        code = str(shortage.get("kod") or "")
        if not code:
            continue
        object_id = f"zlecenie:{oid}:surowiec:{code}"
        match = next((x for x in existing if x.get("typ_dyspozycji") == "magazyn" and x.get("obiekt_id") == object_id), None)
        missing, unit = float(shortage.get("brakuje", 0) or 0), shortage.get("jednostka", "")
        title = f"Zamówić surowiec {shortage.get('nazwa') or code}"
        description = f"Zlecenie {oid}: brakuje {missing:g} {unit}. Produkt: {order.get('produkt','')}."
        meta = {"zlecenie_id": oid, "surowiec": code, "brakuje": missing, "jednostka": unit}
        if match:
            created.append(DS.update_dyspozycja(match["id"], {"tytul": title, "opis": description, "termin": str(order.get("termin") or ""), "meta": meta}))
        else:
            created.append(DS.add_dyspozycja(DS.make_dyspozycja(typ_dyspozycji="magazyn", autor=autor, modul_zrodlowy="zlecenia", obiekt_id=object_id, tytul=title, opis=description, termin=str(order.get("termin") or ""), meta=meta)))
    return [x for x in created if x]


def create_zlecenie(
    kod_produktu,
    ilosc,
    uwagi: str = "",
    autor: str = "system",
    zlec_wew=None,
    reserve: bool = True,
    version=None,
    termin: str = "",
    rzaz_mm: float = DEFAULT_CUT_MM,
    overrides=None,
    auto_dyspozycje: bool = True,
    allow_overproduction: bool = False,
):
    _ensure_dirs()
    ilosc, rzaz_mm = float(ilosc), max(0.0, float(rzaz_mm))
    plan_pp, bom_sr = build_production_plan(kod_produktu, ilosc, cut_mm=rzaz_mm, version=version, overrides=overrides)
    braki, zlec_id = check_materials(bom_sr, 1), _next_id()
    reserved_raw, reserved_pp = {}, {}
    if reserve:
        reserved_pp = _reserve_semis(plan_pp, autor, f"zlecenie:{zlec_id}")
        _updated, reserved_raw = reserve_materials(bom_sr, 1, user=autor, context=f"zlecenie:{zlec_id}", with_reserved=True)
    zlec = {"id": zlec_id, "produkt": kod_produktu, "ilosc": ilosc, "wykonano": 0.0, "status": "nowe", "termin": str(termin or ""), "rzaz_mm": rzaz_mm, "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "uwagi": uwagi, "plan_polprodukty": plan_pp, "zapotrzebowanie_surowce": bom_sr, "rezerwacje_polprodukty": reserved_pp, "rezerwacje_surowce": reserved_raw, "materialy_zarezerwowane": bool(reserve), "zezwol_nadprodukcja": bool(allow_overproduction), "historia": [{"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": autor, "co": "utworzenie"}]}
    if version is not None:
        zlec["version"] = version
    if zlec_wew not in (None, ""):
        zlec["zlec_wew"] = zlec_wew
    if overrides:
        zlec["korekty_polproduktow"] = {str(k): float(v) for k, v in overrides.items()}
    if braki:
        zlec["braki"] = braki
    _write_json(_orders_dir() / f"{zlec['id']}.json", zlec)
    if auto_dyspozycje:
        _sync_execution_disposition(zlec, autor=autor)
        _sync_material_dispositions(zlec, autor=autor)
    return zlec, braki


def _next_id():
    _ensure_dirs()
    nums = []
    for f in _orders_dir().glob("*.json"):
        try:
            nums.append(int(f.stem))
        except Exception:
            pass
    return f"{(max(nums) + 1 if nums else 1):06d}"


def list_zlecenia():
    _ensure_dirs()
    out = []
    for f in sorted(_orders_dir().glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            out.append(_read_json(f))
        except Exception:
            continue
    return out


def _order_path(zlec_id):
    return _orders_dir() / f"{zlec_id}.json"


def update_status(zlec_id, new_status, kto="system"):
    assert new_status in STATUSY, "Nieprawidłowy status"
    p, j = _order_path(zlec_id), _read_json(_order_path(zlec_id))
    if new_status == "anulowane":
        _release_reservations(j.get("rezerwacje_polprodukty"), kto, f"anulowanie:{zlec_id}")
        _release_reservations(j.get("rezerwacje_surowce"), kto, f"anulowanie:{zlec_id}")
        j["rezerwacje_polprodukty"], j["rezerwacje_surowce"] = {}, {}
        try:
            import dyspozycje_store as DS
            disp = _find_disposition_for_order(zlec_id)
            if disp and disp.get("status") != "zamknieta":
                DS.update_dyspozycja(disp["id"], {"status": "wstrzymana"})
        except Exception:
            pass
    j["status"] = new_status
    j.setdefault("historia", []).append({"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": kto, "co": f"status -> {new_status}"})
    _write_json(p, j)
    _sync_execution_disposition(j, autor=kto)
    return j


def approve_zlecenie(zlec_id, kto="system"):
    """Zatwierdź ręcznie utworzone zlecenie oczekujące na akceptację."""
    p = _order_path(zlec_id)
    j = _read_json(p)
    if str(j.get("status") or "").strip().lower() != "do akceptacji":
        raise ValueError(f"Zlecenie {zlec_id} nie oczekuje na akceptację.")

    transitions = {
        "ZW": "nowe",
        "ZN": "projekt",
        "ZM": "awaria zgłoszona",
        "ZZ": "nowe",
    }
    rodzaj = str(j.get("rodzaj") or j.get("typ") or "").strip().upper()
    new_status = transitions.get(rodzaj, "nowe")

    j["status"] = new_status
    approval = j.get("akceptacja")
    if not isinstance(approval, dict):
        approval = {}
    approval.update({
        "wymagana": True,
        "status": "zaakceptowane",
        "zaakceptowano": datetime.now().isoformat(timespec="seconds"),
        "zaakceptowal": kto,
    })
    j["akceptacja"] = approval
    j.setdefault("historia", []).append({
        "kiedy": datetime.now().isoformat(timespec="seconds"),
        "kto": kto,
        "co": f"akceptacja -> {new_status}",
    })
    _write_json(p, j)
    _sync_execution_disposition(j, autor=kto)
    return j


def _replan_order(j, *, kto):
    _release_reservations(j.get("rezerwacje_polprodukty"), kto, f"przeliczenie:{j.get('id')}")
    _release_reservations(j.get("rezerwacje_surowce"), kto, f"przeliczenie:{j.get('id')}")
    plan_pp, bom_sr = build_production_plan(j["produkt"], float(j.get("ilosc", 0) or 0), cut_mm=float(j.get("rzaz_mm", DEFAULT_CUT_MM) or DEFAULT_CUT_MM), version=j.get("version"), overrides=j.get("korekty_polproduktow") or None)
    j["plan_polprodukty"], j["zapotrzebowanie_surowce"] = plan_pp, bom_sr
    j["braki"] = check_materials(bom_sr, 1)
    j["rezerwacje_polprodukty"] = _reserve_semis(plan_pp, kto, f"zlecenie:{j.get('id')}")
    _updated, j["rezerwacje_surowce"] = reserve_materials(bom_sr, 1, user=kto, context=f"zlecenie:{j.get('id')}", with_reserved=True)
    j["materialy_zarezerwowane"] = True
    return j


def update_zlecenie(zlec_id, *, ilosc=None, uwagi=None, zlec_wew=None, termin=None, rzaz_mm=None, korekty_polproduktow=None, kto="system"):
    p, j, changed, requires_replan = _order_path(zlec_id), _read_json(_order_path(zlec_id)), [], False
    if ilosc is not None:
        new_qty = float(ilosc)
        if new_qty < 0:
            raise ValueError("ilosc nie może być ujemna")
        if float(j.get("ilosc", 0) or 0) != new_qty:
            j["ilosc"], requires_replan = new_qty, True
            changed.append(f"ilosc -> {new_qty:g}")
    if rzaz_mm is not None:
        new_cut = max(0.0, float(rzaz_mm))
        if float(j.get("rzaz_mm", DEFAULT_CUT_MM) or 0) != new_cut:
            j["rzaz_mm"], requires_replan = new_cut, True
            changed.append(f"rzaz_mm -> {new_cut:g}")
    if korekty_polproduktow is not None:
        j["korekty_polproduktow"], requires_replan = {str(k): float(v) for k, v in korekty_polproduktow.items()}, True
        changed.append("korekty półproduktów")
    if termin is not None and str(j.get("termin") or "") != str(termin or ""):
        j["termin"] = str(termin or "")
        changed.append(f"termin -> {j['termin']}")
    if uwagi is not None and j.get("uwagi") != uwagi:
        j["uwagi"] = uwagi
        changed.append("uwagi")
    if zlec_wew is not None and j.get("zlec_wew") != zlec_wew:
        if zlec_wew in ("", None):
            j.pop("zlec_wew", None)
        else:
            j["zlec_wew"] = zlec_wew
        changed.append(f"zlec_wew -> {zlec_wew}")
    if requires_replan:
        j = _replan_order(j, kto=kto)
    if changed:
        j.setdefault("historia", []).append({"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": kto, "co": "; ".join(changed)})
        _write_json(p, j)
        _sync_execution_disposition(j, autor=kto)
        _sync_material_dispositions(j, autor=kto)
    return j


def report_wykonano(zlec_id, wykonano, kto="system"):
    p, j = _order_path(zlec_id), _read_json(_order_path(zlec_id))
    old, new = float(j.get("wykonano", 0) or 0), float(wykonano)
    if new < old:
        raise ValueError("Nie można zmniejszyć ilości już rozliczonej.")
    if new < 0:
        raise ValueError("Wykonana ilość nie może być ujemna.")
    delta = new - old
    if delta <= 0:
        return j
    basis = max(float(j.get("ilosc", 0) or 0), new, 1.0)
    ratio, context = delta / basis, f"wykonanie:{zlec_id}"
    for code, total in (j.get("rezerwacje_polprodukty") or {}).items():
        amount = float(total or 0) * ratio
        if amount <= 0:
            continue
        try:
            rec = LM.get_item(code) or {}
            release = min(float(rec.get("rezerwacje", 0) or 0), amount)
            if release > 0:
                LM.zwolnij_rezerwacje(code, release, kto, kontekst=context)
            LM.zuzyj(code, amount, kto, kontekst=context)
        except Exception:
            pass
    for code, data in (j.get("zapotrzebowanie_surowce") or {}).items():
        amount = float(data.get("ilosc", 0) or 0) * ratio
        if amount <= 0:
            continue
        try:
            rec = LM.get_item(code) or {}
            release = min(float(rec.get("rezerwacje", 0) or 0), amount)
            if release > 0:
                LM.zwolnij_rezerwacje(code, release, kto, kontekst=context)
            LM.zuzyj(code, amount, kto, kontekst=context)
        except Exception:
            pass
    j["wykonano"] = new
    if float(j.get("ilosc", 0) or 0) > 0 and new >= float(j.get("ilosc", 0) or 0):
        j["status"] = "zakończone"
    elif new > 0 and j.get("status") == "nowe":
        j["status"] = "w trakcie"
    j.setdefault("historia", []).append({"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": kto, "co": f"wykonano -> {new:g}"})
    _write_json(p, j)
    _sync_execution_disposition(j, autor=kto)
    return j


def delete_zlecenie(zlec_id: str, kto: str = "system") -> bool:
    p = _order_path(zlec_id)
    if not p.exists():
        return False

    # Dyspozycje wykonania i braków surowca są rekordami pochodnymi tego zlecenia.
    # Usuwamy je razem ze zleceniem, aby po kasowaniu nie zostawały osierocone wpisy.
    try:
        import dyspozycje_store as DS

        prefix = f"zlecenie:{zlec_id}"
        linked = [
            item
            for item in DS.load_dyspozycje()
            if str(item.get("obiekt_id") or "") == prefix
            or str(item.get("obiekt_id") or "").startswith(prefix + ":")
        ]
        for item in linked:
            dysp_id = str(item.get("id") or "").strip()
            if dysp_id:
                DS.delete_dyspozycja(dysp_id)
    except Exception as exc:
        raise RuntimeError(f"Nie udało się usunąć powiązanych dyspozycji: {exc}") from exc

    try:
        j = _read_json(p)
        _release_reservations(
            j.get("rezerwacje_polprodukty"),
            kto,
            f"usuniecie:{zlec_id}",
        )
        _release_reservations(
            j.get("rezerwacje_surowce"),
            kto,
            f"usuniecie:{zlec_id}",
        )
    except Exception:
        # Zachowujemy dotychczasową odporność usuwania: brak/stary format rezerwacji
        # nie może zablokować usunięcia samego zlecenia.
        pass

    p.unlink()
    print(f"[INFO][delete_zlecenie] Usunięto {p.name} | kto={kto}")
    return True
