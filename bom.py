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
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    prd = get_produkt(kod_prd)
    pp_out: dict[str, float] = {}
    ops_out: dict[str, float] = {}
    sr_out: dict[str, float] = {}
    for pp in prd.get("polprodukty", []):
        if "ilosc_na_szt" not in pp:
            raise KeyError("Brak klucza 'ilosc_na_szt' w polprodukcie")
        qty = pp["ilosc_na_szt"] * ilosc
        pp_out[pp["kod"]] = qty
        for op in pp.get("operacje", []):
            ops_out[op] = ops_out.get(op, 0) + qty
        sr = pp.get("surowiec") or {}
        typ = sr.get("typ")
        dl = sr.get("dlugosc")
        if typ is not None and dl is not None:
            sr_out[typ] = sr_out.get(typ, 0) + dl * qty
    return {"polprodukty": pp_out, "operacje": ops_out, "surowce": sr_out}

def compute_sr_for_pp(kod_pp: str, ilosc: float) -> dict:
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    pp = get_polprodukt(kod_pp)
    if "surowiec" not in pp:
        raise KeyError("Brak klucza 'surowiec' w polprodukcie")
    sr = pp["surowiec"]
    if "dlugosc" not in sr:
        raise KeyError("Brak klucza 'dlugosc' w surowcu")
    typ = sr.get("typ")
    qty = sr["dlugosc"] * ilosc * (1 + pp.get("norma_strat_proc", 0) / 100)
    ops: dict[str, float] = {}
    for op in pp.get("operacje", []):
        ops[op] = ops.get(op, 0) + ilosc
    return {"surowce": {typ: qty} if typ else {}, "operacje": ops}
