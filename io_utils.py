"""Common JSON I/O helpers."""

from __future__ import annotations

import json
import os
import logging
from typing import Any

from logger import log_akcja

logger = logging.getLogger(__name__)


def read_json(path: str) -> Any | None:
    """Read JSON file from *path*.

    Returns parsed object or ``None`` if the file does not exist or an error
    occurs during reading. Errors are logged via ``log_akcja``.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:  # pragma: no cover - defensive
        log_akcja(f"[IO] Błąd odczytu {path}: {e}")
        return None


def write_json(path: str, data: Any) -> bool:
    """Write ``data`` to ``path`` as UTF-8 JSON with indent=2.

    Returns ``True`` on success, otherwise logs the error and returns ``False``.
    Parent directories are created automatically.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:  # pragma: no cover - defensive
        log_akcja(f"[IO] Błąd zapisu {path}: {e}")
        return False

