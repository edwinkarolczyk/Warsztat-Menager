from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, List


@dataclass
class Product:
    """Reprezentuje definicję produktu."""

    kod: str
    nazwa: str | None = None
    version: str | None = None
    bom_revision: int | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    is_default: bool | None = None
    polprodukty: List[dict] = field(default_factory=list)


def _produkt_candidates(kod: str) -> List[dict]:
    """Zwraca wszystkie wersje produktu o podanym kodzie."""

    from . import DATA_DIR

    products_dir = DATA_DIR / "produkty"
    out: List[dict] = []
    for p in products_dir.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if obj.get("kod") == kod:
            obj["_path"] = p
            out.append(obj)
    return out


def _filter_fields(data: dict) -> dict:
    allowed = {f.name for f in fields(Product)}
    return {k: v for k, v in data.items() if k in allowed}


def get_produkt(kod: str, version: str | None = None) -> Product:
    """Zwraca definicję produktu w danej wersji."""

    candidates = _produkt_candidates(kod)
    if not candidates:
        raise FileNotFoundError(f"Brak definicji: {kod}")

    if version is not None:
        for obj in candidates:
            if str(obj.get("version")) == str(version):
                return Product(**_filter_fields(obj))
        raise FileNotFoundError(f"Brak wersji {version} produktu {kod}")

    for obj in candidates:
        if obj.get("is_default"):
            return Product(**_filter_fields(obj))

    return Product(**_filter_fields(candidates[0]))
