"""Obsługa zapisu i odczytu danych hal."""

from __future__ import annotations

import json
import os
from typing import List

from .const import HALLS_FILE
from .models import Hala, Machine, TechnicianRoute, WallSegment


def load_hale() -> List[Hala]:
    """Wczytaj listę hal z pliku JSON."""
    if not os.path.exists(HALLS_FILE):
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    try:
        with open(HALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Hala(**item) for item in data]
    except Exception:
        return []


def save_hale(hale: List[Hala]) -> None:
    """Zapisz listę hal do pliku JSON."""
    with open(HALLS_FILE, "w", encoding="utf-8") as fh:
        json.dump([h.__dict__ for h in hale], fh, indent=2, ensure_ascii=False)
