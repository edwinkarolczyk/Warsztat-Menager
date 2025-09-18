"""Narzędzia pomocnicze dla modułu zleceń."""

# Wersja pliku: 1.4.0
# Zmiany:
# - create_order_skeleton przyjmuje jawne pola: produkt, ilosc, narzedzie_id,
#   maszyna_id, material, dostawca, termin, pilnosc, komentarz
# - pole 'powiazania' staje się opcjonalnym dodatkiem (może być None); NIE jest
#   wymagane
# - dodatkowe walidacje typów oraz bezpieczne fallbacki

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

from bom import compute_sr_for_pp
from io_utils import read_json

try:  # pragma: no cover - fallback dla środowisk testowych
    from config_manager import ConfigManager  # type: ignore
except Exception:  # pragma: no cover - ConfigManager opcjonalny w testach
    ConfigManager = None  # type: ignore

try:  # pragma: no cover - zabezpieczenie inicjalizacji konfiguracji
    _CONFIG = ConfigManager() if ConfigManager else None  # type: ignore[misc]
except Exception:  # pragma: no cover - ignorujemy błędy przy starcie
    _CONFIG = None

DATA_DIR = os.path.join("data", "zlecenia")


def _orders_cfg() -> Dict[str, object]:
    """Zwraca konfigurację modułu zleceń."""

    if not _CONFIG:
        return {}
    try:
        cfg = _CONFIG.get("orders") or {}
    except Exception:
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _orders_types() -> Dict[str, Dict[str, object]]:
    types = _orders_cfg().get("types", {})
    return types if isinstance(types, dict) else {}


def _orders_id_width() -> int:
    try:
        width = _orders_cfg().get("id_width", 4)
    except Exception:
        return 4
    try:
        return int(width)
    except (TypeError, ValueError):
        return 4


def _seq_path() -> str:
    return os.path.join(DATA_DIR, "_seq.json")


def _load_seq() -> Dict[str, int]:
    defaults = {"ZW": 0, "ZN": 0, "ZM": 0, "ZZ": 0}
    path = _seq_path()
    if not os.path.exists(path):
        return defaults.copy()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return defaults.copy()
    result: Dict[str, int] = {}
    for key, value in defaults.items():
        try:
            result[key] = int(data.get(key, value))
        except Exception:
            result[key] = value
    return result


def _save_seq(seq: Dict[str, int]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_seq_path(), "w", encoding="utf-8") as handle:
        json.dump(seq, handle, ensure_ascii=False, indent=2)


def next_order_id(kind: str) -> str:
    """Zwraca kolejny identyfikator zlecenia dla danego rodzaju."""

    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj: {kind}")

    kind_cfg = kinds.get(kind) if isinstance(kinds, dict) else None
    prefix = (
        kind_cfg.get("prefix", f"{kind}-")
        if isinstance(kind_cfg, dict)
        else f"{kind}-"
    )
    width = _orders_id_width()

    seq = _load_seq()
    seq[kind] = int(seq.get(kind, 0)) + 1
    _save_seq(seq)

    return f"{prefix}{str(seq[kind]).zfill(width)}"


def statuses_for(kind: str) -> List[str]:
    types = _orders_types()
    if not isinstance(types, dict):
        return []
    kind_cfg = types.get(kind)
    if not isinstance(kind_cfg, dict):
        return []
    statuses = kind_cfg.get("statuses", [])
    return statuses if isinstance(statuses, list) else []


def _calc_bom(produkt: str | None, ilosc: int | None) -> Dict[str, int]:
    if not produkt or ilosc is None:
        return {}

    try:
        qty = int(ilosc)
    except (TypeError, ValueError):
        qty = 0

    if qty <= 0:
        return {}

    path = os.path.join("data", "produkty", f"{produkt}.json")
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            prod = json.load(handle)
    except Exception:
        return {}

    bom = prod.get("bom", {}) or {}
    if not isinstance(bom, dict):
        return {}

    result: Dict[str, int] = {}
    for key, value in bom.items():
        try:
            result[str(key)] = int(value) * qty
        except Exception:
            continue
    return result


def _ensure_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _ensure_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def create_order_skeleton(
    kind: str,
    autor: str,
    opis: str,
    *,
    produkt: str | None = None,
    ilosc: int | None = None,
    komentarz: str | None = None,
    pilnosc: str | None = None,
    narzedzie_id: str | None = None,
    maszyna_id: str | None = None,
    material: str | None = None,
    dostawca: str | None = None,
    termin: str | None = None,
    nowy: bool = False,
    powiazania: Dict[str, object] | None = None,
) -> Dict[str, object]:
    """Buduje strukturę zlecenia dla podanego rodzaju."""

    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj: {kind}")

    if isinstance(powiazania, dict):
        narzedzie_id = narzedzie_id or _ensure_str(powiazania.get("narzedzie_id"))
        maszyna_id = maszyna_id or _ensure_str(powiazania.get("maszyna_id"))
        produkt = produkt or _ensure_str(powiazania.get("produkt"))
        material = material or _ensure_str(powiazania.get("material"))

    order_id = next_order_id(kind)
    ts = datetime.now().isoformat(timespec="seconds")
    statuses = statuses_for(kind)
    start_status = statuses[0] if statuses else "nowe"

    data: Dict[str, object] = {
        "id": order_id,
        "rodzaj": kind,
        "status": start_status,
        "utworzono": ts,
        "autor": autor,
        "opis": opis,
        "historia": [
            {
                "ts": ts,
                "kto": autor,
                "operacja": "utworzenie",
                "szczegoly": opis,
            }
        ],
    }

    komentarz_val = _ensure_str(komentarz)
    pilnosc_val = _ensure_str(pilnosc)

    if kind == "ZW":
        produkt_val = _ensure_str(produkt)
        ilosc_val = _ensure_int(ilosc)
        data["produkt"] = produkt_val
        data["ilosc"] = ilosc_val
        data["zapotrzebowanie"] = _calc_bom(produkt_val, ilosc_val)
    elif kind == "ZN":
        data["narzedzie_id"] = _ensure_str(narzedzie_id)
        data["komentarz"] = komentarz_val
    elif kind == "ZM":
        data["maszyna_id"] = _ensure_str(maszyna_id)
        data["awaria"] = komentarz_val
        data["pilnosc"] = pilnosc_val
    elif kind == "ZZ":
        material_val = _ensure_str(material)
        ilosc_val = _ensure_int(ilosc)
        data["material"] = material_val
        data["ilosc"] = ilosc_val
        data["dostawca"] = _ensure_str(dostawca)
        data["termin"] = _ensure_str(termin)
        if nowy:
            data["nowy"] = True
        _add_oczekujace(
            {
                "id": order_id,
                "material": material_val,
                "ilosc": ilosc_val,
                "status": "oczekuje",
                "zrodlo": "zlecenie",
                "nowy": bool(nowy),
            }
        )

    return data


def save_order(data: Dict[str, object]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = data.get("id", "UNKNOWN")
    path = os.path.join(DATA_DIR, f"{filename}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(f"[WM-DBG][ZLECENIA] Zapisano zlecenie {data.get('id')}")


# --- Zamówienia oczekujące (ZZ) ---

def _zamowienia_oczek_path() -> str:
    return os.path.join("data", "zamowienia_oczekujace.json")


def _load_oczekujace() -> List[Dict[str, object]]:
    path = _zamowienia_oczek_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_oczekujace(data: List[Dict[str, object]]) -> None:
    path = _zamowienia_oczek_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _add_oczekujace(entry: Dict[str, object]) -> None:
    if not isinstance(entry, dict):
        return
    data = _load_oczekujace()
    data.append(entry)
    _save_oczekujace(data)


def load_orders() -> List[Dict[str, object]]:
    os.makedirs(DATA_DIR, exist_ok=True)
    results: List[Dict[str, object]] = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("_") or not filename.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                results.append(json.load(handle))
        except Exception:
            continue
    return results


# --- Funkcje zachowane dla zgodności wstecznej ---

def przelicz_zapotrzebowanie(plik_produktu: str, ilosc: float) -> Dict[str, Dict[str, float]]:
    """Oblicz zapotrzebowanie na surowce dla produktu."""

    data = read_json(plik_produktu) or {}
    wynik: Dict[str, Dict[str, float]] = {}

    for pp in data.get("polprodukty", []):
        kod_pp = pp.get("kod")
        if not kod_pp:
            continue
        qty_pp = ilosc * pp.get("ilosc_na_szt", 0)
        for kod_sr, sr_info in compute_sr_for_pp(kod_pp, qty_pp).items():
            entry = wynik.setdefault(
                kod_sr,
                {"ilosc": 0, "jednostka": sr_info["jednostka"]},
            )
            entry["ilosc"] += sr_info["ilosc"]

    return wynik


def sprawdz_magazyn(
    plik_magazynu: str,
    zapotrzebowanie: Dict[str, Dict[str, float]],
    prog: float = 0.1,
) -> Tuple[bool, str, str]:
    """Sprawdź dostępność surowców w magazynie."""

    magazyn = read_json(plik_magazynu) or {}
    alerty: List[str] = []
    zuzycie: List[str] = []

    for kod, info in zapotrzebowanie.items():
        potrzebne = info.get("ilosc", 0)
        dane = magazyn.get(kod)
        if not dane:
            alerty.append(f"{kod} (brak w magazynie)")
            continue

        dostepne = dane.get("stan", 0)
        if potrzebne > dostepne:
            alerty.append(
                f"{kod} (potrzeba {potrzebne}, dostępne {dostepne})",
            )
            continue

        pozostalo = dostepne - potrzebne
        prog_alertu = max(dane.get("prog_alertu", 0), dostepne * prog)
        if pozostalo < prog_alertu:
            zuzycie.append(f"{kod} – UWAGA: niski stan po zużyciu")

    return (len(alerty) == 0), ", ".join(alerty), ", ".join(zuzycie)
