import json
from pathlib import Path

DATA_DIR = Path("data")


def _read_produkt_file(kod: str) -> dict:
    path = DATA_DIR / "produkty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_versions(kod: str):
    data = _read_produkt_file(kod)
    vers = data.get("versions")
    if vers:
        return [v.get("version") for v in vers]
    if "version" in data:
        return [data.get("version")]
    return []


def get_produkt(kod: str, version: str | None = None) -> dict:
    data = _read_produkt_file(kod)
    vers = data.get("versions")
    if vers:
        if version is None:
            item = next((v for v in vers if v.get("is_default")), vers[0])
        else:
            item = next((v for v in vers if v.get("version") == version), vers[0])
        base = {k: v for k, v in data.items() if k != "versions"}
        base.update(item)
        return base
    if version not in (None, data.get("version")):
        raise FileNotFoundError(f"Brak wersji: {version}")
    return data

def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))

def compute_bom_for_prd(kod_prd: str, ilosc: float, version: str | None = None) -> dict:
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    prd = get_produkt(kod_prd, version)
    bom = {}
    for pp in prd.get("polprodukty", []):
        if "ilosc_na_szt" not in pp:
            raise KeyError("Brak klucza 'ilosc_na_szt' w polprodukcie")
        bom[pp["kod"]] = pp["ilosc_na_szt"] * ilosc
    return bom

def compute_sr_for_pp(kod_pp: str, ilosc: float) -> dict:
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    pp = get_polprodukt(kod_pp)
    if "surowiec" not in pp:
        raise KeyError("Brak klucza 'surowiec' w polprodukcie")
    sr = pp["surowiec"]
    if "ilosc_na_szt" not in sr:
        raise KeyError("Brak klucza 'ilosc_na_szt' w surowcu")
    qty = sr["ilosc_na_szt"] * ilosc * (1 + pp.get("norma_strat_proc", 0) / 100)
    return {sr["kod"]: qty}
