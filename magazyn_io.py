"""I/O helpers for warehouse history."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

ALLOWED_OPS = {
    "CREATE",
    "PZ",
    "ZW",
    "RW",
    "RESERVE",
    "UNRESERVE",
}

MAGAZYN_PATH = "data/magazyn/magazyn.json"
PRZYJECIA_PATH = "data/magazyn/przyjecia.json"
HISTORY_PATH = os.path.join(os.path.dirname(MAGAZYN_PATH), "magazyn_history.json")
PZ_SEQ_PATH = "data/magazyn/_seq_pz.json"


def _ensure_dirs(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, type(default)):
                return default
            return data
    except FileNotFoundError:
        return default
    except Exception:
        return default


def append_history(
    items: Dict[str, Any],
    item_id: str,
    user: str,
    op: str,
    qty: float,
    comment: str = "",
    ts: str | None = None,
) -> Dict[str, Any]:
    """Append a history entry for ``item_id``.

    Parameters:
        items: Mapping of warehouse items.
        item_id: Identifier of the item being modified.
        user: Name of the user performing the operation.
        op: Operation type. Must be one of :data:`ALLOWED_OPS`.
        qty: Positive quantity of the operation.
        comment: Optional comment stored with the entry.
        ts: Optional timestamp (ISO 8601). Generated when missing.

    The entry is appended to ``items[item_id]['historia']``. For ``op == 'PZ'``
    an additional record is stored in :data:`PRZYJECIA_PATH`.
    """

    op = op.upper()
    if op not in ALLOWED_OPS:
        raise ValueError(f"Unknown op: {op}")

    qty = float(qty)
    if qty <= 0:
        raise ValueError("qty must be > 0")

    if not ts:
        ts = datetime.now(timezone.utc).isoformat()

    entry = {
        "ts": ts,
        "user": user,
        "op": op,
        "qty": qty,
        "comment": comment,
    }

    item = items.setdefault(item_id, {})
    history = item.setdefault("historia", [])
    history.append(entry)

    _ensure_dirs(HISTORY_PATH)
    hist = _load_json(HISTORY_PATH, [])
    hist.append({**entry, "item_id": item_id})
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    if op == "PZ":
        _ensure_dirs(PRZYJECIA_PATH)
        data = _load_json(PRZYJECIA_PATH, [])
        data.append(
            {
                "ts": ts,
                "item_id": item_id,
                "qty": qty,
                "user": user,
                "comment": comment,
            }
        )
        with open(PRZYJECIA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return entry


def _next_pz_code() -> str:
    """Generate next PZ document code (year based sequence)."""

    now = datetime.now(timezone.utc)
    seq_data = _load_json(PZ_SEQ_PATH, {"year": now.year, "seq": 0})
    if int(seq_data.get("year", 0)) != now.year:
        seq_data = {"year": now.year, "seq": 0}
    seq_data["seq"] = int(seq_data.get("seq", 0)) + 1
    _ensure_dirs(PZ_SEQ_PATH)
    with open(PZ_SEQ_PATH, "w", encoding="utf-8") as f:
        json.dump(seq_data, f, ensure_ascii=False, indent=2)
    return f"PZ{now.year}-{seq_data['seq']:04d}"


def save_pz(record: Dict[str, Any]) -> str:
    """Persist information about a goods receipt (PZ).

    Parameters
    ----------
    record:
        Mapping containing details about the received item. The function
        augments the record with automatically generated ``pz_id`` and
        timestamp and appends it to :data:`PRZYJECIA_PATH`.

    Returns
    -------
    str
        Generated PZ document identifier.
    """

    rec = record.copy()
    rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
    rec["pz_id"] = _next_pz_code()

    _ensure_dirs(PRZYJECIA_PATH)
    data = _load_json(PRZYJECIA_PATH, [])
    data.append(rec)
    with open(PRZYJECIA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return rec["pz_id"]

