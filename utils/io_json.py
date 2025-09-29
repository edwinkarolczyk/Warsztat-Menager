from __future__ import annotations

import json
import os
from typing import Any


def load_or_seed_json(path: str, seed_data: Any, *, indent: int = 2):
    """
    Jeśli plik istnieje → wczytaj JSON.
    Jeśli nie istnieje lub jest uszkodzony → utwórz z ``seed_data`` i zwróć seed.
    """

    try:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(seed_data, handle, indent=indent, ensure_ascii=False)
            return seed_data
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(seed_data, handle, indent=indent, ensure_ascii=False)
        return seed_data
