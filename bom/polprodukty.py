from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import List


@dataclass
class SemiProduct:
    """Reprezentuje definicję półproduktu."""

    kod: str
    nazwa: str | None = None
    operacje: List[str] = field(default_factory=list)
    czynnosci: List[str] = field(default_factory=list)
    surowiec: dict | None = None
    norma_strat_proc: float | None = None


def _filter_fields(data: dict) -> dict:
    allowed = {f.name for f in fields(SemiProduct)}
    return {k: v for k, v in data.items() if k in allowed}


def get_polprodukt(kod: str) -> SemiProduct:
    from . import DATA_DIR

    path = DATA_DIR / "polprodukty" / f"{kod}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak definicji: {kod}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    return SemiProduct(**_filter_fields(obj))
