"""Obsługa zapisu i odczytu danych hal."""

from __future__ import annotations

import json
import os
from typing import List

from .const import HALLS_FILE
from .models import Hala, Machine, TechnicianRoute, WallSegment

try:  # pragma: no cover - logger may not exist in tests
    from logger import log_akcja as _log
except Exception:  # pragma: no cover - fallback for logger
    def _log(msg: str) -> None:
        print(msg)


def load_hale() -> List[Hala]:
    """Wczytaj listę hal z pliku JSON."""
    if not os.path.exists(HALLS_FILE):
        _log(f"[HALA][WARN] Brak pliku {HALLS_FILE}; tworzę pusty")
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []

    try:
        with open(HALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][WARN] Błąd odczytu {HALLS_FILE}: {e}")
        return []

    hale: List[Hala] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            _log(f"[HALA][WARN] Pominięto rekord {i} – nie jest dict")
            continue
        missing = [k for k in ("nazwa", "x1", "y1", "x2", "y2") if k not in item]
        if missing:
            _log(f"[HALA][WARN] Rekord {i} bez kluczy {missing}")
            continue
        try:
            hale.append(Hala(**item))
        except Exception as e:  # pragma: no cover - defensive
            _log(f"[HALA][WARN] Rekord {i} nieprawidłowy: {e}")
    return hale


def save_hale(hale: List[Hala]) -> None:
    """Zapisz listę hal do pliku JSON."""
    try:
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump(
                [h.__dict__ for h in hale], fh, indent=2, ensure_ascii=False
            )
    except Exception as e:  # pragma: no cover - defensive
        _log(f"[HALA][WARN] Błąd zapisu {HALLS_FILE}: {e}")
