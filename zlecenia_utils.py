"""Narzędzia pomocnicze dla modułu zleceń."""

# Wersja pliku: 1.3.0
# Zmiany:
# - skeleton dla ZZ
# - zapis draftu do zamowienia_oczekujace.json

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

from bom import compute_sr_for_pp
from io_utils import read_json

try:
    from config_manager import ConfigManager  # type: ignore
except Exception:  # pragma: no cover - fallback dla środowisk testowych
    ConfigManager = None  # type: ignore

DATA_DIR = os.path.join("data", "zlecenia")


def _zamowienia_oczek_path() -> str:
    return os.path.join("data", "zamowienia_oczekujace.json")


def _load_oczekujace() -> List[Dict[str, object]]:
    path = _zamowienia_oczek_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []


def _save_oczekujace(data: List[Dict[str, object]]) -> None:
    path = _zamowienia_oczek_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _add_oczekujace(entry: Dict[str, object]) -> None:
    data = _load_oczekujace()
    data.append(entry)
    _save_oczekujace(data)


def _orders_cfg() -> Dict[str, object]:
    """Zwraca sekcję konfiguracyjną modułu zleceń."""

    if ConfigManager:
        cfg = ConfigManager.get()
        return (cfg or {}).get("orders", {}) or {}
    return {}


def _orders_types() -> Dict[str, Dict[str, object]]:
    return _orders_cfg().get("types", {}) or {}


def _orders_id_width() -> int:
    return int(_orders_cfg().get("id_width", 4))


def _seq_path() -> str:
    return os.path.join(DATA_DIR, "_seq.json")


def _load_seq() -> Dict[str, int]:
    defaults = {"ZW": 0, "ZN": 0, "ZM": 0, "ZZ": 0}
    if not os.path.exists(_seq_path()):
        return defaults.copy()
    with open(_seq_path(), "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            return defaults.copy()
    return {key: int(data.get(key, 0)) for key in defaults}


def _save_seq(seq: Dict[str, int]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_seq_path(), "w", encoding="utf-8") as handle:
        json.dump(seq, handle, ensure_ascii=False, indent=2)


def next_order_id(kind: str) -> str:
    """Zwraca kolejny identyfikator zlecenia dla danego rodzaju."""

    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj: {kind}")

    prefix = kinds[kind].get("prefix", f"{kind}-")
    width = _orders_id_width()

    seq = _load_seq()
    seq[kind] = int(seq.get(kind, 0)) + 1
    _save_seq(seq)

    return f"{prefix}{str(seq[kind]).zfill(width)}"


def statuses_for(kind: str) -> List[str]:
    return _orders_types().get(kind, {}).get("statuses", []) or []


def is_valid_status(kind: str, status: str) -> bool:
    return status in statuses_for(kind)


def create_order_skeleton(
    kind: str,
    autor: str,
    opis: str,
    powiazania: Dict[str, object] | None = None,
    ilosc: int | None = None,
    produkt: str | None = None,
    komentarz: str | None = None,
    pilnosc: str | None = None,
    material: str | None = None,
    dostawca: str | None = None,
    termin: str | None = None,
    nowy: bool = False,
) -> Dict[str, object]:
    """Buduje strukturę zlecenia dla podanego rodzaju."""

    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj: {kind}")

    powiazania = powiazania or {}
    order_id = next_order_id(kind)
    ts = datetime.now().isoformat(timespec="seconds")
    start_status = (statuses_for(kind) or ["nowe"])[0]

    data: Dict[str, object] = {
        "id": order_id,
        "rodzaj": kind,
        "status": start_status,
        "utworzono": ts,
        "autor": autor,
        "opis": opis,
        "powiazania": powiazania,
        "historia": [
            {
                "ts": ts,
                "kto": autor,
                "operacja": "utworzenie",
                "szczegoly": opis,
            }
        ],
    }

    if kind == "ZW":
        data["produkt"] = produkt
        data["ilosc"] = ilosc
        data["zapotrzebowanie"] = _calc_bom(produkt or "", ilosc or 0)
    elif kind == "ZN":
        data["narzedzie_id"] = powiazania.get("narzedzie_id")
        data["komentarz"] = komentarz
    elif kind == "ZM":
        data["maszyna_id"] = powiazania.get("maszyna_id")
        data["awaria"] = komentarz
        data["pilnosc"] = pilnosc
    elif kind == "ZZ":
        data["material"] = material
        data["ilosc"] = ilosc
        data["dostawca"] = dostawca
        data["termin"] = termin
        if nowy:
            data["nowy"] = True
        draft: Dict[str, object] = {
            "id": order_id,
            "material": material,
            "ilosc": ilosc,
            "status": "oczekuje",
            "zrodlo": "zlecenie",
        }
        if nowy:
            draft["nowy"] = True
        _add_oczekujace(draft)

    return data


def save_order(data: Dict[str, object]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{data['id']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(f"[WM-DBG][ZLECENIA] Zapisano zlecenie {data['id']}")


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


def _calc_bom(produkt: str, ilosc: int) -> Dict[str, int]:
    if not produkt or not ilosc:
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
    return {key: value * ilosc for key, value in bom.items()}


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
