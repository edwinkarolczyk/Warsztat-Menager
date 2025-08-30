"""Obsługa zapisu i odczytu danych hal."""

from __future__ import annotations

import json
import os
from typing import List, Dict, Any

from .const import HALLS_FILE, GRID_STEP, SHOW_GRID
from .models import Hala


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


def load_config_hala() -> Dict[str, Any]:
    """Wczytaj konfigurację widoku hali z pliku ``config.json``.

    Zwraca słownik z kluczami ``grid_step_px`` oraz ``show_grid``.
    Jeśli brakuje wartości w pliku, używane są domyślne
    z ``widok_hali.const``.
    """

    cfg: Dict[str, Any] = {}
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
    except Exception:
        cfg = {}

    hall_cfg = cfg.get("hall", {}) if isinstance(cfg, dict) else {}
    return {
        "grid_step_px": int(
            hall_cfg.get("grid_step_px", hall_cfg.get("grid_size_px", GRID_STEP))
        ),
        "show_grid": bool(hall_cfg.get("show_grid", SHOW_GRID)),
    }
