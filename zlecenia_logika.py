# =============================
# FILE: zlecenia_logika.py
# version: 2.0
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

import bom
import logika_magazyn as LM
from config_manager import ConfigManager
from utils.json_io import _ensure_dirs as _ensure_dirs_impl, _read_json, _write_json

STATUSY = ["nowe", "w przygotowaniu", "w trakcie", "wstrzymane", "zakończone", "anulowane"]
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
    bom_dir = _paths()[1]
    for f in bom_dir.glob("*.json"):
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
    items = _canonical_magazyn_items()
    out = {}
    for kod, rec in items.items():
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
        out[str(kod)] = {
            "nazwa": rec.get("nazwa", kod),
            "typ": rec.get("typ", ""),
            "stan": stan,
            "rezerwacje": rez,
            "dostepne": max(0.0, stan - rez),
            "jednostka": rec.get("jednostka", ""),
        }
    return out


def check_materials(material_bom, ilosc=1):
    mag = read_magazyn()
    braki = []
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        rec = mag.get(kod, {})
        available = float(rec.get("dostepne", rec.get("stan", 0)) or 0)
        if available < req:
            braki.append({
                "kod": kod,
                "nazwa": rec.get("nazwa", kod),
                "potrzeba": req,
                "stan": float(rec.get("stan", 0) or 0),
                "zarezerwowane": float(rec.get("rezerwacje", 0) or 0),
                "dostepne": available,
                "brakuje": req - available,
                "jednostka": data.get("jednostka", rec.get("jednostka", "")),
            })
    return braki


def _semi_stock(code: str):
    rec = read_magazyn().get(code, {})
    return {
        "stan": float(rec.get("stan", 0) or 0),
        "rezerwacje": float(rec.get("rezerwacje", 0) or 0),
        "dostepne": float(rec.get("dostepne", 0) or 0),
    }


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
    total = per_piece * float(qty) * (1.0 + loss / 100.0)
    return {raw_code: {"ilosc": total, "jednostka": unit}}


def build_production_plan(kod_produktu, ilosc, *, cut_mm=DEFAULT_CUT_MM, version=None, overrides=None):
    qty_product = float(ilosc)
    raw_pp = bom.compute_bom_for_prd(kod_produktu, qty_product, version=version)
    overrides = overrides or {}
    plan_pp = {}
    raw_total = {}
    for code, rec in raw_pp.items():
        calculated = float(rec.get("ilosc", 0) or 0)
        target = float(overrides.get(code, calculated) or 0)
        stock = _semi_stock(code)
        from_stock = min(target, stock["dostepne"])
        to_make = max(0.0, target - from_stock)
        plan_pp[code] = {
            "nazwa": rec.get("nazwa") or code,
            "potrzeba": target,
            "wyliczone": calculated,
            "z_magazynu": from_stock,
            "do_wykonania": to_make,
            "stan": stock["stan"],
            "zarezerwowane": stock["rezerwacje"],
            "czynnosci": list(rec.get("czynnosci") or []),
            "surowiec": dict(rec.get("surowiec") or {}),
        }
        for raw_code, raw_info in _raw_need_for_pp(code, to_make, cut_mm).items():
            ent = raw_total.setdefault(raw_code, {"ilosc": 0.0, "jednostka": raw_info.get("jednostka", "")})
            ent["ilosc"] += float(raw_info.get("ilosc", 0) or 0)
    return plan_pp, raw_total


def compute_material_needs(kod_produktu, ilosc=1, version=None, cut_mm=DEFAULT_CUT_MM, overrides=None):
    plan_pp, bom_sr = build_production_plan(kod_produktu, ilosc, cut_mm=cut_mm, version=version, overrides=overrides)
    mag = read_magazyn()
    potrzeby = []
    for kod, data in bom_sr.items():
        req = float(data["ilosc"])
        rec = mag.get(kod, {})
        stan = float(rec.get("stan", 0) or 0)
        rez = float(rec.get("rezerwacje", 0) or 0)
        available = float(rec.get("dostepne", max(0.0, stan - rez)) or 0)
        potrzeby.append({
            "kod": kod,
            "jednostka": data.get("jednostka", rec.get("jednostka", "")),
            "potrzeba": req,
            "stan": stan,
            "zarezerwowane": rez,
            "dostepne": available,
            "brakuje": max(0.0, req - available),
        })
    return potrzeby, bom_sr


def reserve_materials(material_bom, ilosc=1, user="system", context=None):
    updated = {}
    reserved = {}
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        try:
            actual = float(LM.rezerwuj(kod, req, user, kontekst=context or "zlecenie_produkcyjne") or 0)
            reserved[kod] = actual
            rec = LM.get_item(kod) or {}
            stan = float(rec.get("stan", 0) or 0)
            rez = float(rec.get("rezerwacje", 0) or 0)
            updated[kod] = max(0.0, stan - rez)
        except KeyError:
            updated[kod] = 0.0
            reserved[kod] = 0.0
    return updated, reserved


def rezerwuj_materialy(material_bom, ilosc=1):
    updated, _reserved = reserve_materials(material_bom, ilosc)
    return updated


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
            current = float(rec.get("rezerwacje", 0) or 0)
            actual = min(current, amount)
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
    oid = str(order.get("id") or "")
    title = f"Wykonanie produktu {order.get('produkt', '')} — zlecenie {oid}"
    plan = order.get("plan_polprodukty") or {}
    rows = []
    for code, rec in plan.items():
        if not isinstance(rec, dict):
            continue
        rows.append(f"{rec.get('nazwa') or code}: potrzeba {rec.get('potrzeba', 0)}, z magazynu {rec.get('z_magazynu', 0)}, do wykonania {rec.get('do_wykonania', 0)}")
    desc = "\n".join(rows)
    meta = {
        "zlecenie_id": oid,
        "produkt": order.get("produkt", ""),
        "ilosc": order.get("ilosc", 0),
        "wykonano": order.get("wykonano", 0),
        "rzaz_mm": order.get("rzaz_mm", DEFAULT_CUT_MM),
        "plan_polprodukty": plan,
    }
    existing = _find_disposition_for_order(oid)
    if existing:
        return DS.update_dyspozycja(existing["id"], {"tytul": title, "opis": desc, "termin": str(order.get("termin") or ""), "meta": meta})
    item = DS.make_dyspozycja(
        typ_dyspozycji="zlecenie_wykonania",
        tytul=title,
        opis=desc,
        autor=autor,
        termin=str(order.get("termin") or ""),
        modul_zrodlowy="zlecenia",
        obiekt_id=f"zlecenie:{oid}",
        meta=meta,
    )
    return DS.add_dyspozycja(item)


def _sync_material_dispositions(order, autor="system"):
    try:
        import dyspozycje_store as DS
    except Exception:
        return []
    created = []
    oid = str(order.get("id") or "")
    existing = DS.load_dyspozycje()
    for shortage in order.get("braki") or []:
        code = str(shortage.get("kod") or "")
        if not code:
            continue
        object_id = f"zlecenie:{oid}:surowiec:{code}"
        match = next((x for x in existing if x.get("typ_dyspozycji") == "magazyn" and x.get("obiekt_id") == object_id), None)
        missing = float(shortage.get("brakuje", 0) or 0)
        unit = shortage.get("jednostka", "")
        title = f"Zamówić surowiec {shortage.get('nazwa') or code}"
        description = f"Zlecenie {oid}: brakuje {missing:g} {unit}. Produkt: {order.get('produkt','')}."
        meta = {"zlecenie_id": oid, "surowiec": code, "brakuje": missing, "jednostka": unit}
        if match:
            created.append(DS.update_dyspozycja(match["id"], {"tytul": title, "opis": description, "termin": str(order.get("termin") or ""), "meta": meta}))
        else:
            created.append(DS.add_dyspozycja(DS.make_dyspozycja(
                typ_dyspozycji="magazyn",
                autor=autor,
                modul_zrodlowy="zlecenia",
                obiekt_id=object_id,
                tytul=title,
                opis=description,
                termin=str(order.get("termin") or ""),
                meta=meta,
            )))
    return [x for x in created if x]


def create_zlecenie(kod_produktu, ilosc, uwagi: str = "", autor: str = "system", zlec_wew=None, reserve: bool = True, version=None, termin: str = "", rzaz_mm: float = DEFAULT_CUT_MM, overrides=None, auto_dyspozycje: bool = True):
    _ensure_dirs()
    ilosc = float(ilosc)
    rzaz_mm = max(0.0, float(rzaz_mm))
    plan_pp, bom_sr = build_production_plan(kod_produktu, ilosc, cut_mm=rzaz_mm, version=version, overrides=overrides)
    braki = check_materials(bom_sr, 1)
    zlec_id = _next_id()
    context = f"zlecenie:{zlec_id}"
    reserved_raw = {}
    reserved_pp = {}
    if reserve:
        reserved_pp = _reserve_semis(plan_pp, autor, context)
        _updated, reserved_raw = reserve_materials(bom_sr, 1, user=autor, context=context)
    zlec = {
        "id": zlec_id,
        "produkt": kod_produktu,
        "ilosc": ilosc,
        "wykonano": 0.0,
        "status": "nowe",
        "termin": str(termin or ""),
        "rzaz_mm": rzaz_mm,
        "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uwagi": uwagi,
        "plan_polprodukty": plan_pp,
        "zapotrzebowanie_surowce": bom_sr,
        "rezerwacje_polprodukty": reserved_pp,
        "rezerwacje_surowce": reserved_raw,
        "materialy_zarezerwowane": bool(reserve),
        "historia": [{"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": autor, "co": "utworzenie"}],
    }
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
    nid = max(nums) + 1 if nums else 1
    return f"{nid:06d}"


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
    p = _order_path(zlec_id)
    j = _read_json(p)
    if new_status == "anulowane":
        _release_reservations(j.get("rezerwacje_polprodukty"), kto, f"anulowanie:{zlec_id}")
        _release_reservations(j.get("rezerwacje_surowce"), kto, f"anulowanie:{zlec_id}")
        j["rezerwacje_polprodukty"] = {}
        j["rezerwacje_surowce"] = {}
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


def _replan_order(j, *, kto):
    _release_reservations(j.get("rezerwacje_polprodukty"), kto, f"przeliczenie:{j.get('id')}")
    _release_reservations(j.get("rezerwacje_surowce"), kto, f"przeliczenie:{j.get('id')}")
    plan_pp, bom_sr = build_production_plan(
        j["produkt"],
        float(j.get("ilosc", 0) or 0),
        cut_mm=float(j.get("rzaz_mm", DEFAULT_CUT_MM) or DEFAULT_CUT_MM),
        version=j.get("version"),
        overrides=j.get("korekty_polproduktow") or None,
    )
    j["plan_polprodukty"] = plan_pp
    j["zapotrzebowanie_surowce"] = bom_sr
    j["braki"] = check_materials(bom_sr, 1)
    context = f"zlecenie:{j.get('id')}"
    j["rezerwacje_polprodukty"] = _reserve_semis(plan_pp, kto, context)
    _updated, reserved_raw = reserve_materials(bom_sr, 1, user=kto, context=context)
    j["rezerwacje_surowce"] = reserved_raw
    j["materialy_zarezerwowane"] = True
    return j


def update_zlecenie(zlec_id, *, ilosc=None, uwagi=None, zlec_wew=None, termin=None, rzaz_mm=None, korekty_polproduktow=None, kto="system"):
    p = _order_path(zlec_id)
    j = _read_json(p)
    changed = []
    requires_replan = False
    if ilosc is not None:
        try:
            new_qty = float(ilosc)
        except Exception:
            raise ValueError("ilosc musi być liczbą")
        if new_qty < 0:
            raise ValueError("ilosc nie może być ujemna")
        if float(j.get("ilosc", 0) or 0) != new_qty:
            j["ilosc"] = new_qty
            changed.append(f"ilosc -> {new_qty:g}")
            requires_replan = True
    if rzaz_mm is not None:
        new_cut = max(0.0, float(rzaz_mm))
        if float(j.get("rzaz_mm", DEFAULT_CUT_MM) or 0) != new_cut:
            j["rzaz_mm"] = new_cut
            changed.append(f"rzaz_mm -> {new_cut:g}")
            requires_replan = True
    if korekty_polproduktow is not None:
        j["korekty_polproduktow"] = {str(k): float(v) for k, v in korekty_polproduktow.items()}
        changed.append("korekty półproduktów")
        requires_replan = True
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
    p = _order_path(zlec_id)
    j = _read_json(p)
    old = float(j.get("wykonano", 0) or 0)
    new = float(wykonano)
    if new < old:
        raise ValueError("Nie można zmniejszyć ilości już rozliczonej.")
    if new < 0:
        raise ValueError("Wykonana ilość nie może być ujemna.")
    delta = new - old
    if delta <= 0:
        return j
    order_qty = float(j.get("ilosc", 0) or 0)
    basis = max(order_qty, new, 1.0)
    ratio = delta / basis
    context = f"wykonanie:{zlec_id}"
    for code, total in (j.get("rezerwacje_polprodukty") or {}).items():
        amount = float(total or 0) * ratio
        if amount <= 0:
            continue
        try:
            rec = LM.get_item(code) or {}
            reserved = float(rec.get("rezerwacje", 0) or 0)
            release = min(reserved, amount)
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
            reserved = float(rec.get("rezerwacje", 0) or 0)
            release = min(reserved, amount)
            if release > 0:
                LM.zwolnij_rezerwacje(code, release, kto, kontekst=context)
            LM.zuzyj(code, amount, kto, kontekst=context)
        except Exception:
            pass
    j["wykonano"] = new
    if order_qty > 0 and new >= order_qty:
        j["status"] = "zakończone"
    elif new > 0 and j.get("status") == "nowe":
        j["status"] = "w trakcie"
    j.setdefault("historia", []).append({"kiedy": datetime.now().isoformat(timespec="seconds"), "kto": kto, "co": f"wykonano -> {new:g}"})
    _write_json(p, j)
    _sync_execution_disposition(j, autor=kto)
    return j


def delete_zlecenie(zlec_id: str) -> bool:
    _ensure_dirs()
    p = _order_path(zlec_id)
    if p.exists():
        try:
            j = _read_json(p)
            _release_reservations(j.get("rezerwacje_polprodukty"), "system", f"usuniecie:{zlec_id}")
            _release_reservations(j.get("rezerwacje_surowce"), "system", f"usuniecie:{zlec_id}")
        except Exception:
            pass
        p.unlink()
        print(f"[INFO][delete_zlecenie] Usunięto {p.name}")
        return True
    return False
