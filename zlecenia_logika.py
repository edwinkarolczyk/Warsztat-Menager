# =============================
# FILE: zlecenia_logika.py
# version: 1.2
# Zmiany 1.2:
# - planowanie rozwija Produkt -> Półprodukt -> Surowiec
# - rezerwacja zwiększa pole `rezerwacje`, nie pomniejsza fizycznego `stan`
# - zlecenie zapisuje rozwinięty plan półproduktów i zapotrzebowanie materiałowe
# =============================

from pathlib import Path
from datetime import datetime

import bom
import logika_magazyn as LM
from utils.json_io import _ensure_dirs as _ensure_dirs_impl, _read_json, _write_json

DATA_DIR = Path("data")
BOM_DIR = DATA_DIR / "produkty"
MAG_DIR = DATA_DIR / "magazyn"
ZLECENIA_DIR = DATA_DIR / "zlecenia"


def _ensure_dirs():
    _ensure_dirs_impl(ZLECENIA_DIR, BOM_DIR, MAG_DIR)


STATUSY = ["nowe", "w przygotowaniu", "w trakcie", "wstrzymane", "zakończone", "anulowane"]


def list_produkty():
    _ensure_dirs()
    out = []
    for f in BOM_DIR.glob("*.json"):
        try:
            j = _read_json(f)
            out.append({"kod": j.get("kod") or j.get("symbol") or f.stem, "nazwa": j.get("nazwa") or f.stem})
        except Exception:
            continue
    return out


def read_bom(kod):
    p = BOM_DIR / f"{kod}.json"
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
    """Zwraca stany magazynu wraz z rezerwacjami i ilością dostępną."""
    items = _canonical_magazyn_items()
    if items:
        out = {}
        for kod, rec in items.items():
            if not isinstance(rec, dict):
                continue
            stan = float(rec.get("stan", 0) or 0)
            rez = max(0.0, float(rec.get("rezerwacje", 0) or 0))
            out[str(kod)] = {
                "nazwa": rec.get("nazwa", kod),
                "stan": stan,
                "rezerwacje": rez,
                "dostepne": max(0.0, stan - rez),
                "jednostka": rec.get("jednostka", ""),
            }
        return out

    # fallback dla starszych instalacji/testów
    p = MAG_DIR / "stany.json"
    if not p.exists():
        return {}
    raw = _read_json(p)
    for rec in raw.values() if isinstance(raw, dict) else []:
        if isinstance(rec, dict):
            stan = float(rec.get("stan", 0) or 0)
            rez = max(0.0, float(rec.get("rezerwacje", 0) or 0))
            rec.setdefault("dostepne", max(0.0, stan - rez))
    return raw


def check_materials(material_bom, ilosc=1):
    """Sprawdza dostępność po odjęciu wcześniejszych rezerwacji."""
    mag = read_magazyn()
    braki = []
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        rec = mag.get(kod, {})
        available = float(rec.get("dostepne", rec.get("stan", 0)) or 0)
        if available < req:
            braki.append(
                {
                    "kod": kod,
                    "nazwa": rec.get("nazwa", kod),
                    "potrzeba": req,
                    "stan": float(rec.get("stan", 0) or 0),
                    "zarezerwowane": float(rec.get("rezerwacje", 0) or 0),
                    "dostepne": available,
                    "brakuje": req - available,
                }
            )
    return braki


def compute_material_needs(kod_produktu, ilosc=1, version=None):
    """Rozwija produkt do surowców i porównuje potrzeby z realnie dostępnym stanem."""
    bom_sr = bom.compute_sr_for_prd(kod_produktu, float(ilosc), version=version)
    mag = read_magazyn()
    potrzeby = []
    for kod, data in bom_sr.items():
        req = float(data["ilosc"])
        rec = mag.get(kod, {})
        stan = float(rec.get("stan", 0) or 0)
        rez = float(rec.get("rezerwacje", 0) or 0)
        available = float(rec.get("dostepne", max(0.0, stan - rez)) or 0)
        potrzeby.append(
            {
                "kod": kod,
                "jednostka": data.get("jednostka", rec.get("jednostka", "")),
                "potrzeba": req,
                "stan": stan,
                "zarezerwowane": rez,
                "dostepne": available,
                "brakuje": max(0.0, req - available),
            }
        )
    return potrzeby, bom_sr


def reserve_materials(material_bom, ilosc=1, user="system", context=None):
    """Rezerwuje surowce bez zmiany stanu fizycznego.

    Zwraca ``{kod: dostępne_po_rezerwacji}``. Jeżeli stan jest za mały,
    rezerwuje tylko ilość faktycznie dostępną; informację o braku wylicza
    ``check_materials`` przed rezerwacją.
    """
    updated = {}
    for kod, data in material_bom.items():
        req = float(data["ilosc"]) * float(ilosc)
        try:
            LM.rezerwuj(kod, req, user, kontekst=context or "zlecenie_produkcyjne")
            rec = LM.get_item(kod) or {}
            stan = float(rec.get("stan", 0) or 0)
            rez = float(rec.get("rezerwacje", 0) or 0)
            updated[kod] = max(0.0, stan - rez)
        except KeyError:
            # Brak kartoteki: niczego nie tworzymy sztucznie.
            updated[kod] = 0.0
    return updated


def rezerwuj_materialy(material_bom, ilosc=1):
    return reserve_materials(material_bom, ilosc)


def create_zlecenie(
    kod_produktu,
    ilosc,
    uwagi: str = "",
    autor: str = "system",
    zlec_wew=None,
    reserve: bool = True,
    version=None,
):
    """Tworzy zlecenie wraz z rozwiniętym planem półproduktów i surowców."""
    _ensure_dirs()
    ilosc = float(ilosc)
    plan_pp = bom.compute_bom_for_prd(kod_produktu, ilosc, version=version)
    bom_sr = bom.compute_sr_for_prd(kod_produktu, ilosc, version=version)
    braki = check_materials(bom_sr, 1)

    zlec_id = _next_id()
    if reserve:
        reserve_materials(bom_sr, 1, user=autor, context=f"zlecenie:{zlec_id}")

    zlec = {
        "id": zlec_id,
        "produkt": kod_produktu,
        "ilosc": ilosc,
        "status": "nowe",
        "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uwagi": uwagi,
        "plan_polprodukty": plan_pp,
        "zapotrzebowanie_surowce": bom_sr,
        "materialy_zarezerwowane": bool(reserve),
        "historia": [
            {
                "kiedy": datetime.now().isoformat(timespec="seconds"),
                "kto": autor,
                "co": "utworzenie",
            }
        ],
    }
    if version is not None:
        zlec["version"] = version
    if zlec_wew not in (None, ""):
        zlec["zlec_wew"] = zlec_wew
    if braki:
        zlec["braki"] = braki
    _write_json(ZLECENIA_DIR / f"{zlec['id']}.json", zlec)
    return zlec, braki


def _next_id():
    _ensure_dirs()
    nums = []
    for f in ZLECENIA_DIR.glob("*.json"):
        try:
            nums.append(int(f.stem))
        except Exception:
            pass
    nid = max(nums) + 1 if nums else 1
    return f"{nid:06d}"


def list_zlecenia():
    _ensure_dirs()
    out = []
    for f in sorted(ZLECENIA_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            out.append(_read_json(f))
        except Exception:
            continue
    return out


def update_status(zlec_id, new_status, kto="system"):
    assert new_status in STATUSY, "Nieprawidłowy status"
    p = ZLECENIA_DIR / f"{zlec_id}.json"
    j = _read_json(p)
    j["status"] = new_status
    j.setdefault("historia", []).append({
        "kiedy": datetime.now().isoformat(timespec="seconds"),
        "kto": kto,
        "co": f"status -> {new_status}",
    })
    _write_json(p, j)
    return j


def update_zlecenie(zlec_id, *, ilosc=None, uwagi=None, zlec_wew=None, kto="system"):
    p = ZLECENIA_DIR / f"{zlec_id}.json"
    j = _read_json(p)
    changed = []
    if ilosc is not None:
        try:
            ilosc = int(ilosc)
        except Exception:
            raise ValueError("ilosc musi być liczbą całkowitą")
        if j.get("ilosc") != ilosc:
            j["ilosc"] = ilosc
            changed.append(f"ilosc -> {ilosc}")
    if uwagi is not None and j.get("uwagi") != uwagi:
        j["uwagi"] = uwagi
        changed.append("uwagi")
    if zlec_wew is not None and j.get("zlec_wew") != zlec_wew:
        if zlec_wew in ("", None):
            j.pop("zlec_wew", None)
        else:
            j["zlec_wew"] = zlec_wew
        changed.append(f"zlec_wew -> {zlec_wew}")
    if changed:
        j.setdefault("historia", []).append(
            {
                "kiedy": datetime.now().isoformat(timespec="seconds"),
                "kto": kto,
                "co": "; ".join(changed),
            }
        )
        _write_json(p, j)
    return j


def delete_zlecenie(zlec_id: str) -> bool:
    _ensure_dirs()
    p = ZLECENIA_DIR / f"{zlec_id}.json"
    if p.exists():
        p.unlink()
        print(f"[INFO][delete_zlecenie] Usunięto {p.name}")
        return True
    return False
