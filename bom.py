import json
from pathlib import Path

DATA_DIR = Path("data")


def list_produkty_wersje() -> list[dict]:
    """Zwraca listę dostępnych produktów wraz z wersjami."""
    out: list[dict] = []
    for path in (DATA_DIR / "produkty").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        kod = data.get("kod") or path.stem
        nazwa = data.get("nazwa") or kod
        versions = data.get("versions") or [data]
        for v in versions:
            out.append(
                {
                    "kod": kod,
                    "nazwa": nazwa,
                    "version": v.get("version"),
                    "is_default": v.get("is_default", False),
                }
            )
    return out


def get_produkt(kod: str, version: str | int | None = None) -> dict:
    """Pobiera definicję produktu, obsługując wiele wersji."""
    path = DATA_DIR / "produkty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    data = json.loads(path.read_text(encoding="utf-8"))
    versions = data.get("versions")
    if versions:
        if version is None:
            version = next(
                (v.get("version") for v in versions if v.get("is_default")),
                versions[0].get("version"),
            )
        ver = next(
            (v for v in versions if str(v.get("version")) == str(version)),
            versions[0],
        )
        res = {"kod": data.get("kod", kod), "nazwa": data.get("nazwa", kod)}
        res.update(ver)
        return res
    return data

def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))

def compute_bom_for_prd(kod_prd: str, ilosc: float, version: str | int | None = None) -> dict:
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
