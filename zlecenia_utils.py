# Plik: zlecenia_utils.py
# Wersja pliku: 1.0.0

import os
from datetime import datetime

from bom import compute_sr_for_pp
from io_utils import read_json, write_json


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
