import json
import logging
from pathlib import Path

from packaging.version import parse as parse_version

logger = logging.getLogger(__name__)
DATA_DIR = Path("data")


def _produkt_candidates(kod: str):
    """Wyszukuje wszystkie wersje produktu o podanym kodzie."""
    products_dir = DATA_DIR / "produkty"
    out = []
    for p in products_dir.glob("*.json"):
        try:
            with p.open(encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if obj.get("kod") == kod:
            obj["_path"] = p
            out.append(obj)
    return out


def get_produkt(kod: str, version: str | None = None) -> dict:
    """Zwraca definicję produktu w danej wersji.

    Jeśli ``version`` jest ``None``, wybierana jest wersja oznaczona
    ``is_default`` lub pierwsza z listy."""
    candidates = _produkt_candidates(kod)
    if not candidates:
        raise FileNotFoundError(f"Brak definicji: {kod}")
    if version is not None:
        for obj in candidates:
            if str(obj.get("version")) == str(version):
                return obj
        raise FileNotFoundError(f"Brak wersji {version} produktu {kod}")

    def _sort_key(obj):
        ver = obj.get("version")
        ver_key = parse_version(str(ver)) if ver is not None else parse_version("0")
        return ver_key, str(obj.get("_path"))

    defaults = [obj for obj in candidates if obj.get("is_default")]
    if len(defaults) > 1:
        logger.warning(
            "Produkt %s ma wiele domyślnych wersji: %s",
            kod,
            [obj.get("version") for obj in defaults],
        )
        defaults = sorted(defaults, key=_sort_key)
        return defaults[0]
    if defaults:
        return defaults[0]
    return sorted(candidates, key=_sort_key)[0]

def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def compute_bom_for_prd(kod_prd: str, ilosc: float, version: str | None = None) -> dict:
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
        if "surowiec" not in pp:
            raise KeyError("surowiec")
        sr = pp["surowiec"]
        if "typ" not in sr or "dlugosc" not in sr:
            raise KeyError("surowiec")
        if not pp.get("czynnosci"):
            logger.warning(
                "Półprodukt %s w produkcie %s nie zawiera klucza 'czynnosci'",
                pp.get("kod"),
                kod_prd,
            )
        qty = pp["ilosc_na_szt"] * ilosc
        bom[pp["kod"]] = {
            "ilosc": qty,
            "czynnosci": list(pp.get("czynnosci") or []),
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
    qty = sr["ilosc_na_szt"] * ilosc * (
        1 + pp.get("norma_strat_proc", 0) / 100
    )
    surowce_path = DATA_DIR / "magazyn" / "surowce.json"
    jednostka = None
    if surowce_path.exists():
        with surowce_path.open(encoding="utf-8") as f:
            surowce = json.load(f)

        def _get_unit(data, kod):
            if isinstance(data, dict):
                return data.get(kod, {}).get("jednostka")
            if isinstance(data, list):
                for rec in data:
                    if isinstance(rec, dict) and rec.get("kod") == kod:
                        return rec.get("jednostka")
            return None

        jednostka = _get_unit(surowce, sr["kod"])
        if jednostka is None:
            jednostka = sr.get("jednostka")
    else:
        jednostka = sr.get("jednostka")
        if jednostka is None:
            raise FileNotFoundError(
                f"Brak pliku {surowce_path} oraz jednostki dla surowca {sr['kod']}"
            )
    if jednostka is None:
        raise KeyError(f"Brak klucza 'jednostka' dla surowca {sr['kod']}")
    return {sr["kod"]: {"ilosc": qty, "jednostka": jednostka}}


def compute_sr_for_prd(
    kod_prd: str, ilosc: float, version: str | None = None
) -> dict:
    """Oblicza zapotrzebowanie na surowce dla produktu.

    Zwracany jest słownik ``{kod_sr: {"ilosc": qty, "jednostka": unit}}``.
    """
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    bom_pp = compute_bom_for_prd(kod_prd, ilosc, version=version)
    wynik: dict[str, dict] = {}
    for kod_pp, info in bom_pp.items():
        for kod_sr, sr_info in compute_sr_for_pp(kod_pp, info["ilosc"]).items():
            entry = wynik.setdefault(
                kod_sr,
                {"ilosc": 0, "jednostka": sr_info["jednostka"]},
            )
            entry["ilosc"] += sr_info["ilosc"]
    return wynik
