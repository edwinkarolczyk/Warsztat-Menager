import json
from pathlib import Path

DATA_DIR = Path("data")


def _produkt_candidates(kod: str):
    """Wyszukuje wszystkie wersje produktu o podanym kodzie."""
    products_dir = DATA_DIR / "produkty"
    out = []
    for p in products_dir.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if obj.get("kod") == kod:
            obj["_path"] = p
            out.append(obj)
    return out


def get_produkt(kod: str, version: str | None = None) -> dict:
    """Zwraca definicję produktu w danej wersji.

    Jeśli ``version`` jest ``None``, wybierana jest wersja oznaczona
    ``is_default`` lub pierwsza z listy.
    """
    candidates = _produkt_candidates(kod)
    if not candidates:
        raise FileNotFoundError(f"Brak definicji: {kod}")
    if version is not None:
        for obj in candidates:
            if str(obj.get("version")) == str(version):
                return obj
        raise FileNotFoundError(f"Brak wersji {version} produktu {kod}")
    for obj in candidates:
        if obj.get("is_default"):
            return obj
    return candidates[0]


def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))


def compute_bom_for_prd(
    kod_prd: str, ilosc: float, version: str | None = None
) -> dict:
    """Oblicza ilości półproduktów wraz z dodatkowymi danymi.

    Zwracany jest słownik w postaci ``{kod_pp: {...}}`` gdzie dla każdego
    półproduktu przechowywana jest wynikowa ilość, lista czynności oraz
    parametry surowca przekazane w definicji produktu.
    """
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    prd = get_produkt(kod_prd, version=version)
    bom = {}
    for pp in prd.get("polprodukty", []):
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


def compute_sr_for_prd(
    kod_prd: str,
    ilosc: float,
    version: str | None = None,
    bom_revision: int | None = None,
    at_date: str | None = None,
) -> dict:
    """Oblicza zapotrzebowanie na surowce dla produktu.

    Zwracany jest słownik ``{kod_sr: {\"ilosc\": qty, \"jednostka\": unit}}``.
    Parametry ``bom_revision`` i ``at_date`` są zarezerwowane na przyszłość.
    """
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    bom_pp = compute_bom_for_prd(kod_prd, ilosc, version=version)
    result: dict[str, dict] = {}
    for kod_pp, info in bom_pp.items():
        sr_qty = compute_sr_for_pp(kod_pp, info["ilosc"])
        pp_def = get_polprodukt(kod_pp)
        if "surowiec" not in pp_def or "jednostka" not in pp_def["surowiec"]:
            raise KeyError("jednostka")
        unit = pp_def["surowiec"]["jednostka"]
        for kod_sr, qty in sr_qty.items():
            if kod_sr not in result:
                result[kod_sr] = {"ilosc": 0, "jednostka": unit}
            result[kod_sr]["ilosc"] += qty
    return result
