"""Utilities for goods receipt (PZ) operations.

This module provides helper functions for generating PZ identifiers,
recording new PZ entries and updating warehouse state files.  The
functions mirror the light-weight I/O helpers present in :mod:`magazyn_io`.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Dict, Iterable

PZ_SEQ_PATH = "data/magazyn/_seq_pz.json"
PRZYJECIA_PATH = "data/magazyn/przyjecia.json"
STANY_PATH = "data/magazyn/stany.json"
KATALOG_PATH = "data/magazyn/magazyn.json"


def _ensure_dirs(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, type(default)):
            return default
        return data
    except FileNotFoundError:
        return default
    except Exception:
        return default


def generate_pz_id(seq_path: str = PZ_SEQ_PATH) -> str:
    """Return a new PZ identifier.

    The identifier uses the format ``PZ/YYYY/NNNN`` where ``NNNN`` is a
    zero padded sequence number.  The sequence is stored in
    ``seq_path`` and is reset at the beginning of each year.
    """
    now = datetime.now()
    data = _load_json(seq_path, {"year": now.year, "seq": 0})
    year = now.year
    if data.get("year") == year:
        seq = int(data.get("seq", 0)) + 1
    else:
        seq = 1
    _ensure_dirs(seq_path)
    with open(seq_path, "w", encoding="utf-8") as fh:
        json.dump({"year": year, "seq": seq}, fh, ensure_ascii=False, indent=2)
    return f"PZ/{year}/{seq:04d}"


def save_pz(entry: Dict[str, object], path: str = PRZYJECIA_PATH) -> None:
    """Append a ``entry`` to the PZ log stored at ``path``."""
    _ensure_dirs(path)
    data = _load_json(path, [])
    data.append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def update_stany_after_pz(entries: Iterable[Dict[str, object]], path: str = STANY_PATH) -> Dict[str, Dict[str, object]]:
    """Update warehouse stock after applying PZ ``entries``.

    Each entry must contain ``item_id`` and ``qty``.  Quantities for the
    same ``item_id`` are summed before applying to the state file located
    at ``path``.  The updated state dictionary is returned.
    """
    stany = _load_json(path, {})
    totals: Dict[str, float] = {}
    for e in entries:
        iid = str(e.get("item_id"))
        qty = float(e.get("qty", 0))
        totals[iid] = totals.get(iid, 0) + qty

    for iid, qty in totals.items():
        rec = stany.setdefault(iid, {"nazwa": iid, "stan": 0})
        rec["stan"] = float(rec.get("stan", 0)) + qty

    _ensure_dirs(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(stany, fh, ensure_ascii=False, indent=2)
    return stany


def ensure_in_katalog(entry: Dict[str, object], path: str = KATALOG_PATH) -> bool:
    """Ensure ``entry`` exists in the warehouse catalogue file.

    Returns ``True`` if the entry was added and ``False`` if it already
    existed.
    """
    katalog = _load_json(path, {"items": {}, "meta": {"order": []}})
    items = katalog.setdefault("items", {})
    item_id = str(entry.get("id"))
    if item_id in items:
        return False

    items[item_id] = entry
    meta = katalog.setdefault("meta", {})
    order = meta.setdefault("order", [])
    if item_id not in order:
        order.append(item_id)

    _ensure_dirs(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(katalog, fh, ensure_ascii=False, indent=2)
    return True
