import json
from pathlib import Path

DATA_DIR = Path("data")

def get_produkt(kod: str) -> dict:
    path = DATA_DIR / "produkty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))

def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))

def compute_bom_for_prd(kod_prd: str, ilosc: float) -> dict:
    prd = get_produkt(kod_prd)
    return {
        pp["kod"]: pp["ilosc_na_szt"] * ilosc
        for pp in prd.get("polprodukty", [])
    }

def compute_sr_for_pp(kod_pp: str, ilosc: float) -> dict:
    pp = get_polprodukt(kod_pp)
    sr = pp["surowiec"]
    qty = sr["ilosc_na_szt"] * ilosc * (1 + pp.get("norma_strat_proc", 0)/100)
    return {sr["kod"]: qty}
