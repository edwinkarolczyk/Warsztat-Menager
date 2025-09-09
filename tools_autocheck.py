"""Helpers for determining if a tool should be automatically checked."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Base directory with tool data. Tests may monkeypatch this path.
DATA_DIR = Path("data")


def should_autocheck(status_id: str, collection_id: str, config: Dict[str, Any]) -> bool:
    """Return ``True`` when a tool entry should be auto checked.

    The decision is based on two sources with the following precedence:

    1. ``auto_check_on_entry`` flag in the data for ``status_id`` within
       ``collection_id``. When present, its boolean value is returned.
    2. Otherwise, the status identifier is checked against the global list
       ``tools.auto_check_on_status_global`` from ``config``.
    3. If none of the above apply the function returns ``False``.
    """

    entry_path = DATA_DIR / collection_id / f"{status_id}.json"
    try:
        with entry_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        flag = data.get("auto_check_on_entry")
        if flag is not None:
            return bool(flag)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    statuses = config.get("tools", {}).get("auto_check_on_status_global", [])
    return status_id in statuses
