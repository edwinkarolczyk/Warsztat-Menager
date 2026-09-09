# version: 1.1
import json
import logging
import os
from pathlib import Path

from config_manager import ConfigManager
from packaging.version import parse as parse_version

logger = logging.getLogger(__name__)
try:
    cfg = ConfigManager()
    data_root = Path(cfg.path_data())
    produkty_dir = data_root / "produkty"
    polprodukty_dir = data_root / "polprodukty"
    if os.path.isdir("data"):
        produkty_ok = produkty_dir.is_dir() and any(produkty_dir.glob("*.json"))
        polprodukty_ok = polprodukty_dir.is_dir() and any(polprodukty_dir.glob("*.json"))
        if not produkty_ok or not polprodukty_ok:
            raise FileNotFoundError("Configured data root missing BOM data.")
    DATA_DIR = data_root
except Exception:
    DATA_DIR = Path("data")


def _produkt_candidates(kod: str):
    products_dir = DATA_DIR / "produkty"
    out = []
    for p in products_dir.glob("*.json"):
        try:
            with p.open(encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if obj.get("kod") == kod or obj.get("symbol") == kod:
            obj["_path"] = p
            out.append(obj)
    return out


def get_produkt(kod: str, version: str | None = None) -> dict:
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
        logger.warning("Produkt %s ma wiele domyślnych wersji: %s", kod, [obj.get("version") for obj in defaults])
        return sorted(defaults, key=_sort_key)[0]
    if defaults:
        return defaults[0]
    return sorted(candidates, key=_sort_key)[0]


def get_polprodukt(kod: str) -> dict:
    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    # zgodność z wcześniejszym pojedynczym plikiem słownikowym
    legacy = DATA_DIR / "magazyn" / "polprodukty.json"
    if legacy.exists():
        with legacy.open(encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict) and isinstance(payload.get(kod), dict):
            rec = dict(payload[kod])
            rec.setdefault("kod", kod)
            return rec
        if isinstance(payload, list):
            for rec in payload:
                if isinstance(rec, dict) and str(rec.get("kod") or rec.get("id")) == str(kod):
                    return rec
    raise FileNotFoundError(f"Brak definicji półproduktu: {kod}")


def _product_components(product: dict) -> list[dict]:
    raw = product.get("polprodukty")
    if raw is None:
        raw = product.get("BOM") or product.get("bom") or []
    if isinstance(raw, dict):
        return [{"kod": kod, "ilosc_na_szt": qty} for kod, qty in raw.items()]
    return [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []


def compute_bom_for_prd(kod_prd: str, ilosc: float, version: str | None = None) -> dict:
    """Rozwija produkt do półproduktów.

    Produkt przechowuje przede wszystkim kod półproduktu i ilość na sztukę.
    Technologia oraz surowiec są pobierane z kartoteki półproduktu. Starszy
    format z osadzonym ``surowiec`` nadal jest obsługiwany.
    """
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    prd = get_produkt(kod_prd, version=version)
    result = {}
    for ref in _product_components(prd):
        kod_pp = str(ref.get("kod") or ref.get("id") or ref.get("symbol") or "").strip()
        if not kod_pp:
            raise KeyError("kod półproduktu")
        qty_per_product = ref.get("ilosc_na_szt", ref.get("ilosc_na_sztuke", ref.get("ilosc", 1)))
        qty = float(qty_per_product) * float(ilosc)

        try:
            card = get_polprodukt(kod_pp)
        except FileNotFoundError:
            card = dict(ref)

        surowiec = card.get("surowiec") or ref.get("surowiec")
        if not isinstance(surowiec, dict) or not (surowiec.get("kod") or surowiec.get("id")):
            raise KeyError(f"Półprodukt {kod_pp} nie ma przypisanego surowca")

        result[kod_pp] = {
            "ilosc": qty,
            "nazwa": card.get("nazwa") or ref.get("nazwa") or kod_pp,
            "czynnosci": list(card.get("czynnosci") or ref.get("czynnosci") or []),
            "surowiec": dict(surowiec),
            "norma_strat_procent": float(card.get("norma_strat_procent", card.get("norma_strat_proc", 0)) or 0),
        }
    return result


def _find_raw_material_unit(kod: str, fallback=None):
    surowce_path = DATA_DIR / "magazyn" / "surowce.json"
    if surowce_path.exists():
        with surowce_path.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            rec = data.get(kod)
            if isinstance(rec, dict):
                return rec.get("jednostka") or fallback
        elif isinstance(data, list):
            for rec in data:
                if isinstance(rec, dict) and str(rec.get("kod") or rec.get("id")) == str(kod):
                    return rec.get("jednostka") or fallback
    return fallback


def compute_sr_for_pp(kod_pp: str, ilosc: float) -> dict:
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    pp = get_polprodukt(kod_pp)
    sr = pp.get("surowiec")
    if not isinstance(sr, dict):
        raise KeyError("Brak klucza 'surowiec' w polprodukcie")
    sr_kod = str(sr.get("kod") or sr.get("id") or "").strip()
    if not sr_kod:
        raise KeyError("Brak ID/kodu surowca")
    if "ilosc_na_szt" not in sr:
        raise KeyError("Brak klucza 'ilosc_na_szt' w surowcu")
    loss = float(pp.get("norma_strat_procent", pp.get("norma_strat_proc", 0)) or 0)
    qty = float(sr["ilosc_na_szt"]) * float(ilosc) * (1 + loss / 100.0)
    unit = _find_raw_material_unit(sr_kod, sr.get("jednostka"))
    if not unit:
        raise KeyError(f"Brak klucza 'jednostka' dla surowca {sr_kod}")
    return {sr_kod: {"ilosc": qty, "jednostka": unit}}


def compute_sr_for_prd(kod_prd: str, ilosc: float, version: str | None = None) -> dict:
    """Rozwija produkt przez półprodukty do łącznego zapotrzebowania surowców."""
    if ilosc <= 0:
        raise ValueError("Parametr 'ilosc' musi byc wiekszy od zera")
    bom_pp = compute_bom_for_prd(kod_prd, ilosc, version=version)
    wynik: dict[str, dict] = {}
    for kod_pp, info in bom_pp.items():
        for kod_sr, sr_info in compute_sr_for_pp(kod_pp, info["ilosc"]).items():
            entry = wynik.setdefault(kod_sr, {"ilosc": 0.0, "jednostka": sr_info["jednostka"]})
            entry["ilosc"] += float(sr_info["ilosc"])
    return wynik
