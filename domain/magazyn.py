from __future__ import annotations

import json
import os

from config.paths import get_path
from wm_log import dbg as wm_dbg, err as wm_err


def save_reservations(rezerwacje: list[dict]) -> bool:
    path = get_path("warehouse.reservations_file")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rezerwacje, f, ensure_ascii=False, indent=2)
        wm_dbg("magazyn.res", "saved", path=path, count=len(rezerwacje))
        return True
    except Exception as e:  # pragma: no cover - logowanie błędu
        wm_err("magazyn.res", "save failed", e, path=path)
        return False
