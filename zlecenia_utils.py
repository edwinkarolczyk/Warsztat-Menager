# Plik: zlecenia_utils.py
# Wersja pliku: 1.0.0

import json
import os
from datetime import datetime

from bom import compute_sr_for_pp
from io_utils import read_json, write_json

try:
    from config_manager import ConfigManager
except Exception:
    ConfigManager = None


def _orders_cfg():
    """Zwraca sekcję config['orders'] lub sensowne domyślne wartości."""
    if ConfigManager:
        cfg = ConfigManager.get()
        return (cfg or {}).get("orders", {}) or {}
    return {}


def _orders_types():
    return _orders_cfg().get("types", {}) or {}


def _orders_id_width():
    return int(_orders_cfg().get("id_width", 4))


def _seq_path():
    return os.path.join("data", "zlecenia", "_seq.json")


def _load_seq():
    p = _seq_path()
    if not os.path.exists(p):
        return {"ZW": 0, "ZN": 0, "ZM": 0}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ZW": 0, "ZN": 0, "ZM": 0}


def _save_seq(seq):
    os.makedirs(os.path.join("data", "zlecenia"), exist_ok=True)
    with open(_seq_path(), "w", encoding="utf-8") as f:
        json.dump(seq, f, ensure_ascii=False, indent=2)


def next_order_id(kind: str) -> str:
    """Zwraca np. 'ZN-0001' zgodnie z configiem."""
    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj zlecenia: {kind}")

    prefix = kinds[kind].get("prefix", f"{kind}-")
    width = _orders_id_width()
    seq = _load_seq()
    seq[kind] = int(seq.get(kind, 0)) + 1
    _save_seq(seq)
    return f"{prefix}{str(seq[kind]).zfill(width)}"


def statuses_for(kind: str):
    kinds = _orders_types()
    if kind not in kinds:
        return []
    return kinds[kind].get("statuses", []) or []


def is_valid_status(kind: str, status: str) -> bool:
    return status in statuses_for(kind)


def create_order_skeleton(
    kind: str,
    autor: str,
    opis: str,
    powiazania: dict | None = None,
    rezerwacja: bool | None = None,
) -> dict:
    """
    Tworzy dane zlecenia bez zapisu do pliku (do użycia w wyższym poziomie).
    Wymagane powiązania:
      - ZN: powiazania['narzedzie_id']
      - ZM: powiazania['maszyna_id']
    """
    kinds = _orders_types()
    if kind not in kinds:
        raise ValueError(f"[ERROR][ZLECENIA] Nieznany rodzaj: {kind}")

    if rezerwacja is None:
        rezerwacja = bool(kinds[kind].get("reserve_by_default", False))

    powiazania = powiazania or {}
    if kind == "ZN" and not powiazania.get("narzedzie_id"):
        raise ValueError("[ERROR][ZLECENIA] ZN wymaga 'powiazania.narzedzie_id'.")
    if kind == "ZM" and not powiazania.get("maszyna_id"):
        raise ValueError("[ERROR][ZLECENIA] ZM wymaga 'powiazania.maszyna_id'.")

    start_status = (statuses_for(kind) or ["nowe"])[0]
    order_id = next_order_id(kind)
    ts = datetime.now().isoformat(timespec="seconds")

    data = {
        "id": order_id,
        "rodzaj": kind,
        "status": start_status,
        "utworzono": ts,
        "autor": autor,
        "opis": opis,
        "powiazania": powiazania,
        "materialy": {
            "rezerwacja": rezerwacja,
            "pozycje": []
        },
        "historia": [
            {"ts": ts, "kto": autor, "operacja": "utworzenie", "szczegoly": ""}
        ],
        "uwagi": ""
    }
    return data


def przelicz_zapotrzebowanie(plik_produktu: str, ilosc: float) -> dict:
    """Oblicz zapotrzebowanie na surowce dla produktu.

    Funkcja odczytuje definicję produktu (``polprodukty``) i dla każdego
    półproduktu wylicza zapotrzebowanie na surowiec na podstawie
    ``polproduktów`` oraz norm zużycia zdefiniowanych w plikach
    ``data/polprodukty``. Wynik zwracany jest jako słownik w postaci
    ``{kod_surowca: {"ilosc": qty, "jednostka": unit}}``.
    """

    data = read_json(plik_produktu) or {}
    wynik: dict = {}

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


def sprawdz_magazyn(plik_magazynu: str, zapotrzebowanie: dict, prog: float = 0.1):
    """Sprawdź dostępność surowców w magazynie.

    ``zapotrzebowanie`` to słownik ``{kod_surowca: {"ilosc": qty, "jednostka": unit}}``.
    Funkcja zwraca krotkę ``(ok, alerty, ostrzezenia)`` gdzie ``ok`` jest
    ``True`` jeśli wszystkie surowce są dostępne w wymaganych ilościach.
    """

    magazyn = read_json(plik_magazynu) or {}
    alerty: list[str] = []
    zuzycie: list[str] = []

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


def zapisz_zlecenie(folder, produkt, ilosc):
    numer = f"ZL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    dane = {
        "numer": numer,
        "typ": "produkcja",
        "produkt": produkt,
        "ilość": ilosc,
        "status": "oczekujące",
        "data_start": datetime.now().strftime("%Y-%m-%d"),
        "data_koniec": "",
        "użytkownik": "Edwin",
        "komentarze": []
    }
    write_json(os.path.join(folder, f"{numer}.json"), dane)
