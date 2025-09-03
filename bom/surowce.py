from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import Dict


@dataclass
class RawMaterial:
    """Reprezentuje stan surowca w magazynie."""

    kod: str
    nazwa: str
    jednostka: str
    stan: float
    prog_alertu: float


def _filter_fields(data: dict) -> dict:
    allowed = {f.name for f in fields(RawMaterial)}
    return {k: v for k, v in data.items() if k in allowed}


def get_surowiec(kod: str) -> RawMaterial:
    from . import DATA_DIR

    path = DATA_DIR / "magazyn" / "surowce.json"
    if not path.exists():
        raise FileNotFoundError("Brak pliku surowców")
    data: Dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))
    if kod not in data:
        raise FileNotFoundError(f"Brak definicji: {kod}")
    obj = dict(data[kod])
    obj["kod"] = kod
    return RawMaterial(**_filter_fields(obj))
