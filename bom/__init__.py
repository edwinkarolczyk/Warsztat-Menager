from __future__ import annotations

from pathlib import Path
from typing import Dict

DATA_DIR = Path("data")

from .products import Product, get_produkt
from .polprodukty import SemiProduct, get_polprodukt
from .surowce import RawMaterial, get_surowiec

__all__ = [
    "DATA_DIR",
    "Product",
    "SemiProduct",
    "RawMaterial",
    "get_produkt",
    "get_polprodukt",
    "get_surowiec",
    "compute_bom_for_prd",
    "compute_sr_for_pp",
]


def compute_bom_for_prd(kod_prd: str, ilosc: float, version: str | None = None) -> Dict[str, dict]:
    """Oblicza zapotrzebowanie półproduktów dla danego produktu."""

    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")

    prd = get_produkt(kod_prd, version=version)
    bom: Dict[str, dict] = {}
    for pp in prd.polprodukty or []:
        if "ilosc_na_szt" not in pp:
            raise KeyError("ilosc_na_szt")
        if not pp.get("czynnosci"):
            raise KeyError("czynnosci")
        if "surowiec" not in pp:
            raise KeyError("surowiec")
        sr = pp["surowiec"]
        if "typ" not in sr or "dlugosc" not in sr:
            raise KeyError("surowiec")
        qty = pp["ilosc_na_szt"] * ilosc
        bom[pp["kod"]] = {
            "ilosc": qty,
            "czynnosci": list(pp["czynnosci"]),
            "surowiec": {"typ": sr["typ"], "dlugosc": sr["dlugosc"]},
        }
    return bom


def compute_sr_for_pp(kod_pp: str, ilosc: float) -> Dict[str, float]:
    """Oblicza zapotrzebowanie surowca dla danego półproduktu."""

    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")

    pp = get_polprodukt(kod_pp)
    if pp.surowiec is None:
        raise KeyError("Brak klucza 'surowiec' w polprodukcie")
    sr = pp.surowiec
    if "ilosc_na_szt" not in sr:
        raise KeyError("Brak klucza 'ilosc_na_szt' w surowcu")
    qty = sr["ilosc_na_szt"] * ilosc * (1 + (pp.norma_strat_proc or 0) / 100)
    return {sr["kod"]: qty}
