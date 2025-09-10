"""Helpers for magazyn JSON I/O and history handling."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict

from io_utils import read_json, write_json
from logger import log_akcja

MAGAZYN_PATH = "data/magazyn/magazyn.json"


def load_magazyn(path: str = MAGAZYN_PATH) -> Dict[str, Any]:
    """Load magazyn data from ``path``.

    Returns an empty structure when the file does not exist or contains invalid
    data. The returned structure at minimum includes ``items`` and ``meta``
    mappings.
    """

    data = read_json(path)
    if not isinstance(data, dict):
        data = {}
    items = data.setdefault("items", {})
    data.setdefault("meta", {})
    if not isinstance(items, dict):
        data["items"] = {}
    return data


def save_magazyn(data: Dict[str, Any], path: str = MAGAZYN_PATH, *, backup: bool = True) -> bool:
    """Persist ``data`` to ``path`` in UTF-8 JSON format.

    When ``backup`` is ``True`` a ``*.bak`` copy of the previous file is
    created. Every save operation is logged with ``[WM-DBG]`` prefix.
    """

    if backup and os.path.exists(path):
        try:
            shutil.copyfile(path, f"{path}.bak")
        except OSError:  # pragma: no cover - defensive
            pass
    log_akcja(f"[WM-DBG] Zapis magazynu: {path}")
    return write_json(path, data)


_OP_PL = {
    "PZ": "przyjecie",
    "ZW": "zwrot",
    "RW": "zuzycie",
    "RESERVE": "rezerwacja",
    "UNRESERVE": "zwolnienie",
    "USUN": "usun",
}


def append_history(item_id: str, entry: Dict[str, Any], path_or_items) -> Dict[str, Any]:
    """Validate ``entry`` and append it to ``historia`` for ``item_id``.

    ``entry`` must contain keys: ``ts``, ``user``, ``op``, ``qty`` and
    ``comment``. Missing ``ts`` generates current UTC timestamp. ``qty`` is
    converted to ``float``. Additional aliases with Polish field names are added
    for backwards compatibility.

    ``path_or_items`` can be a path to ``magazyn.json`` or a mapping with items
    where the history should be appended. When a path is provided the file is
    loaded and saved automatically.
    """

    required = {"user", "op", "qty", "comment"}
    if ts := entry.get("ts") is None:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"entry missing keys: {missing}")

    # normalised entry used for storage
    norm = {
        "ts": entry["ts"],
        "user": entry["user"],
        "op": entry["op"],
        "qty": float(entry["qty"]),
        "comment": entry["comment"],
    }

    # Polish aliases for legacy code/tests
    norm.update(
        {
            "czas": norm["ts"],
            "uzytkownik": norm["user"],
            "operacja": _OP_PL.get(norm["op"], norm["op"]),
            "ilosc": norm["qty"],
            "komentarz": norm["comment"],
        }
    )

    if isinstance(path_or_items, dict):
        items = path_or_items
        data = None
    else:
        data = load_magazyn(path_or_items)
        items = data.setdefault("items", {})

    item = items.setdefault(item_id, {})
    history = item.setdefault("historia", [])
    history.append(norm)

    if data is not None:
        save_magazyn(data, path_or_items)

    return norm

