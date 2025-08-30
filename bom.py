import json
from pathlib import Path

DATA_DIR = Path("data")


def list_versions(kod: str) -> list[dict]:
    """Zwraca listę dostępnych wersji produktu."""
    out: list[dict] = []
    for p in (DATA_DIR / "produkty").glob(f"{kod}*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append(
            {
                "version": str(j.get("version")),
                "bom_revision": j.get("bom_revision"),
                "effective_from": j.get("effective_from"),
                "effective_to": j.get("effective_to"),
                "is_default": j.get("is_default", False),
            }
        )
    return out


def get_produkt(kod: str, version: str | None = None) -> dict:
    """Pobiera definicję produktu, uwzględniając wersję."""
    files = list((DATA_DIR / "produkty").glob(f"{kod}*.json"))
    if not files:
        raise FileNotFoundError(f"Brak definicji: {kod}")
    selected = None
    for p in files:
        data = json.loads(p.read_text(encoding="utf-8"))
        ver = str(data.get("version")) if data.get("version") is not None else None
        if version:
            if ver == str(version):
                return data
        elif data.get("is_default"):
            return data
        if selected is None:
            selected = data
    if version:
        raise FileNotFoundError(f"Brak wersji {version} dla produktu {kod}")
    return selected

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
