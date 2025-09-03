import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
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
    ``is_default`` lub pierwsza z listy."""
    candidates = _produkt_candidates(kod)
    if not candidates:
        raise FileNotFoundError(f"Brak definicji: {kod}")
    if version is not None:
        for obj in candidates:
            if str(obj.get("version")) == str(version):
                return obj
        raise FileNotFoundError(f"Brak wersji {version} produktu {kod}")

    defaults = [obj for obj in candidates if obj.get("is_default")]
    if len(defaults) > 1:
        logger.warning(
            "Produkt %s ma wiele domyślnych wersji: %s",
            kod,
            [obj.get("version") for obj in defaults],
        )
        defaults = sorted(
            defaults,
            key=lambda o: (str(o.get("version")), str(o.get("_path"))),
        )
        return defaults[0]
    if defaults:
        return defaults[0]
    return sorted(
        candidates,
        key=lambda o: (str(o.get("version")), str(o.get("_path"))),
    )[0]

def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    return json.loads(path.read_text(encoding="utf-8"))

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
    qty = sr["ilosc_na_szt"] * ilosc * (
        1 + pp.get("norma_strat_proc", 0) / 100
    )
    surowce_path = DATA_DIR / "magazyn" / "surowce.json"
    jednostka = None
    if surowce_path.exists():
        surowce = json.loads(surowce_path.read_text(encoding="utf-8"))
        jednostka = surowce.get(sr["kod"], {}).get("jednostka")
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
