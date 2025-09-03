"""Logika operacji związanych z BOM.

Moduł zawiera pomocnicze funkcje do obliczeń ilości
surowców oraz półproduktów na podstawie definicji
półproduktów i bieżących stanów magazynowych.
"""

from __future__ import annotations

from typing import Dict, Iterable


def compute_sr_for_pp(kod_pp: str, ilosc: float, polprodukty_def: Dict[str, dict]) -> float:
    """Oblicz ilość surowca wymaganą dla półproduktu.

    Parametry
    ---------
    kod_pp:
        Kod półproduktu, dla którego liczone jest zapotrzebowanie.
    ilosc:
        Liczba sztuk półproduktu.
    polprodukty_def:
        Słownik definicji półproduktów w postaci ``{kod: definicja}``.

    Zwraca
    ------
    float
        Ilość surowca potrzebna do wykonania ``ilosc`` sztuk półproduktu.
    """
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi być większy od zera")
    if kod_pp not in polprodukty_def:
        raise KeyError(f"Brak definicji półproduktu: {kod_pp}")
    pp = polprodukty_def[kod_pp]
    sr = pp.get("surowiec")
    if not sr:
        raise KeyError("surowiec")
    if "ilosc_na_szt" not in sr:
        raise KeyError("ilosc_na_szt")
    qty = sr["ilosc_na_szt"] * ilosc
    norma = pp.get("norma_strat_proc", 0)
    return qty * (1 + norma / 100)


def compute_material_needs(
    bom: Iterable[dict],
    ilosc_produktu: float,
    magazyn_surowce: Dict[str, dict],
    polprodukty_def: Dict[str, dict],
) -> dict:
    """Wyznacz zapotrzebowanie na surowce i półprodukty.

    Funkcja przyjmuje strukturę BOM produktu oraz ilość produktów
    do wykonania. Na podstawie definicji półproduktów obliczana jest
    wymagana ilość surowców, która następnie porównywana jest ze stanem
    magazynowym ``magazyn_surowce``.

    Zwracany jest słownik z dwiema sekcjami: ``"surowce"`` oraz
    ``"polprodukty"``. W pierwszej znajdują się braki surowców (po
    uwzględnieniu stanu magazynowego), natomiast w drugiej całkowite
    zapotrzebowanie na półprodukty.
    """
    if ilosc_produktu <= 0:
        raise ValueError("Parametr 'ilosc_produktu' musi być większy od zera")

    potrzeby_sr: Dict[str, float] = {}
    potrzeby_pp: Dict[str, float] = {}

    for pp in bom:
        kod_pp = pp.get("kod")
        if not kod_pp:
            continue
        ilosc_pp = ilosc_produktu * pp.get("ilosc_na_szt", 0)
        if ilosc_pp <= 0:
            continue
        potrzeby_pp[kod_pp] = potrzeby_pp.get(kod_pp, 0) + ilosc_pp
        ilosc_sr = compute_sr_for_pp(kod_pp, ilosc_pp, polprodukty_def)
        sr_kod = polprodukty_def[kod_pp]["surowiec"]["kod"]
        potrzeby_sr[sr_kod] = potrzeby_sr.get(sr_kod, 0) + ilosc_sr

    braki_sr: Dict[str, float] = {}
    for kod_sr, wymagane in potrzeby_sr.items():
        stan = magazyn_surowce.get(kod_sr, {}).get("stan", 0)
        brak = wymagane - stan
        if brak > 0:
            braki_sr[kod_sr] = brak

    return {"surowce": braki_sr, "polprodukty": potrzeby_pp}
