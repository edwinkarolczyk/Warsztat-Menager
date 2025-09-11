from __future__ import annotations

import json
import os
import unicodedata
from typing import Any, Dict, List, Set

CATALOG_PATH = "data/magazyn/katalog.json"
STANY_PATH = "data/magazyn/stany.json"


def _ensure_dirs(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, type(default)):
            return default
        return data
    except FileNotFoundError:
        return default
    except Exception:
        return default


def load_catalog(path: str | None = None) -> Dict[str, Any]:
    """Load and return the warehouse catalogue."""

    path = path or CATALOG_PATH
    return _load_json(path, {})


def save_catalog(catalog: Dict[str, Any], path: str | None = None) -> None:
    """Persist ``catalog`` to :data:`CATALOG_PATH`."""

    path = path or CATALOG_PATH
    _ensure_dirs(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)


def _normalize(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("ł", "l").replace("Ł", "L")
    s = s.replace(" ", "_")
    return s


def build_code(entry: Dict[str, Any]) -> str:
    """Build an item code based on ``entry`` details."""

    cat = str(entry.get("kategoria", "")).lower()
    if cat == "profil":
        rodzaj = _normalize(entry.get("rodzaj", "")).upper()
        wymiar = _normalize(entry.get("wymiar", ""))
        typ = _normalize(entry.get("typ", "")).upper()
        parts = ["PRF", rodzaj, wymiar, typ]
        return "_".join(p for p in parts if p)
    if cat == "rura":
        fi = _normalize(entry.get("fi", ""))
        scianka = entry.get("scianka") or entry.get("ścianka") or ""
        scianka = _normalize(scianka)
        typ = _normalize(entry.get("typ", "")).upper()
        fi_part = f"FI{fi}" + (f"x{scianka}" if scianka else "")
        parts = ["RUR", fi_part, typ]
        return "_".join(p for p in parts if p)
    if cat in {"półprodukt", "polprodukt"}:
        nazwa = _normalize(entry.get("nazwa", "")).upper()
        return f"PP_{nazwa}" if nazwa else "PP"
    return _normalize(entry.get("id", ""))


def suggest_names_for_category(kategoria: str, prefix: str) -> List[str]:
    """Return alphabetically sorted names for ``kategoria`` starting with ``prefix``."""

    catalog = load_catalog()
    stany = _load_json(STANY_PATH, {})
    prefix_low = prefix.lower()
    results: Set[str] = set()
    for item in catalog.values():
        if str(item.get("kategoria", "")).lower() == kategoria.lower():
            name = str(item.get("nazwa", ""))
            if name.lower().startswith(prefix_low):
                results.add(name)
    for iid, rec in stany.items():
        name = str(rec.get("nazwa", ""))
        if not name.lower().startswith(prefix_low):
            continue
        cat = catalog.get(iid, {}).get("kategoria")
        if cat and str(cat).lower() == kategoria.lower():
            results.add(name)
    return sorted(results)
