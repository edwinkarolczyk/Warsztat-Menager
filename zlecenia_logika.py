# =============================
# FILE: zlecenia_logika.py
# VERSION: 1.1.5
# Zmiany 1.1.5:
# - create_zlecenie: opcjonalna rezerwacja materiałów (reserve=True)
# - create_zlecenie nadal obsługuje `zlec_wew`; start = "nowe"
# =============================

from pathlib import Path
from datetime import datetime

import bom
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
            out.append({"kod": j.get("kod") or f.stem, "nazwa": j.get("nazwa") or f.stem})
        except Exception:
            continue
    return out

def read_bom(kod):
    p = BOM_DIR / f"{kod}.json"
    if not p.exists():
        raise FileNotFoundError(f"Brak BOM: {kod}")
    return _read_json(p)

def read_magazyn():
    p = MAG_DIR / "stany.json"
    if not p.exists():
        return {}
    return _read_json(p)

def check_materials(bom, ilosc=1):
    """Sprawdza dostępność surowców w magazynie.

    ``bom`` powinien być słownikiem w postaci
    ``{kod_sr: {"ilosc": ilosc_na_szt, "jednostka": unit}}``.
    ``ilosc`` oznacza liczbę sztuk produktu, dla której należy
    sprawdzić zapotrzebowanie.
    """
    mag_path = MAG_DIR / "stany.json"
    mag = _read_json(mag_path) if mag_path.exists() else {}
    braki = []
    for kod, data in bom.items():
        req = data["ilosc"] * ilosc
        stan = mag.get(kod, {}).get("stan", 0)
        if stan < req:
            braki.append(
                {
                    "kod": kod,
                    "nazwa": mag.get(kod, {}).get("nazwa", kod),
                    "potrzeba": req,
                    "stan": stan,
                    "brakuje": req - stan,
                }
            )
    return braki


def compute_material_needs(kod_produktu, ilosc=1):
    """Oblicza zapotrzebowanie i dostępność surowców dla produktu."""
    bom_sr = bom.compute_sr_for_prd(kod_produktu, 1)
    mag = read_magazyn()
    potrzeby = []
    for kod, data in bom_sr.items():
        req = data["ilosc"] * ilosc
        stan = mag.get(kod, {}).get("stan", 0)
        potrzeby.append(
            {
                "kod": kod,
                "potrzeba": req,
                "dostepne": stan,
                "brakuje": max(0, req - stan),
            }
        )
    return potrzeby, bom_sr


def reserve_materials(bom, ilosc=1):
    """Rezerwuje surowce na magazynie i zwraca nowe stany.

    ``bom`` powinien być słownikiem w postaci
    ``{kod_sr: {"ilosc": ilosc_na_szt, "jednostka": unit}}``.
    Zwracany jest słownik ``{kod_sr: stan_po_rezerwacji}`` dla każdej pozycji.
    Informacja ta jest wykorzystywana przez GUI do zasilenia kolumny
    "dostępne po".
    """
    mag_path = MAG_DIR / "stany.json"
    default_item = lambda k: {"nazwa": k, "stan": 0, "prog_alert": 0}

    mag = _read_json(mag_path) if mag_path.exists() else {}
    updated = {}
    for kod, data in bom.items():
        req = data["ilosc"] * ilosc
        if kod not in mag:
            mag[kod] = default_item(kod)
        mag[kod]["stan"] = max(0, mag[kod].get("stan", 0) - req)
        updated[kod] = mag[kod]["stan"]
    _write_json(mag_path, mag)
    return updated


def rezerwuj_materialy(bom, ilosc=1):
    """Polska nazwa pomocnicza dla ``reserve_materials``."""
    return reserve_materials(bom, ilosc)

def create_zlecenie(
    kod_produktu,
    ilosc,
    uwagi: str = "",
    autor: str = "system",
    zlec_wew=None,
    reserve: bool = True,
):
    """Tworzy zlecenie w statusie "nowe".

    Opcjonalnie zapisuje numer zlecenia wewnętrznego i rezerwuje materiały.
    """
    _ensure_dirs()
    bom_sr = bom.compute_sr_for_prd(kod_produktu, 1)
    braki = check_materials(bom_sr, ilosc)  # tylko informacyjnie na start
    if reserve:
        reserve_materials(bom_sr, ilosc)
    zlec = {
        "id": _next_id(),
        "produkt": kod_produktu,
        "ilosc": ilosc,
        "status": "nowe",
        "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uwagi": uwagi,
        "historia": [
            {
                "kiedy": datetime.now().isoformat(timespec="seconds"),
                "kto": autor,
                "co": "utworzenie",
            }
        ],
    }
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
        "kto": kto, "co": f"status -> {new_status}"
    })
    _write_json(p, j)
    return j


def update_zlecenie(zlec_id, *, ilosc=None, uwagi=None, zlec_wew=None, kto="system"):
    """Aktualizuje podstawowe dane zlecenia.

    Pozwala zmienić ilość, uwagi oraz numer wewnętrzny. Dodaje wpis do
    historii dla każdej zmienionej wartości.
    """
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
