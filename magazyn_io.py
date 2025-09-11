"""I/O helpers for warehouse history."""

from __future__ import annotations

import json
import os
import re
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
STANY_PATH = os.path.join(os.path.dirname(MAGAZYN_PATH), "stany.json")
KATALOG_PATH = os.path.join(os.path.dirname(MAGAZYN_PATH), "katalog.json")


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


def suggest_names_for_category(kategoria: str, prefix: str) -> list[str]:
    """Return list of names for ``kategoria`` starting with ``prefix``.

    Names are looked up in :data:`KATALOG_PATH` and :data:`STANY_PATH`.
    Duplicate results are removed and the output is sorted alphabetically.
    """

    prefix_norm = (prefix or "").strip().lower()
    if not prefix_norm:
        return []

    katalog = _load_json(KATALOG_PATH, {})
    stany = _load_json(STANY_PATH, {})
    results: list[str] = []

    if isinstance(katalog, dict):
        kat = katalog.get(kategoria) or {}
        if isinstance(kat, dict):
            for name in kat.values():
                if isinstance(name, str) and name.lower().startswith(prefix_norm):
                    results.append(name)

    if isinstance(stany, dict):
        for rec in stany.values():
            name = rec.get("nazwa")
            if isinstance(name, str) and name.lower().startswith(prefix_norm):
                results.append(name)

    return sorted(set(results))


def get_or_build_code(entry: Dict[str, Any]) -> str:
    """Return existing code for ``entry`` or generate a new one.

    ``entry`` should contain at least ``kategoria`` and ``nazwa`` keys.
    Generated codes are added to :data:`KATALOG_PATH` and are unique across
    catalog and current warehouse states from :data:`STANY_PATH`.
    """

    code = str(entry.get("kod") or "").strip()
    if code:
        return code

    kategoria = str(entry.get("kategoria") or "").strip()
    nazwa = str(entry.get("nazwa") or "").strip()
    if not kategoria or not nazwa:
        raise ValueError("entry must contain 'kategoria' and 'nazwa'")

    katalog = _load_json(KATALOG_PATH, {})
    stany = _load_json(STANY_PATH, {})
    cat = katalog.get(kategoria) or {}

    # try to find existing code by name
    for kod, nm in cat.items():
        if isinstance(nm, str) and nm.strip().lower() == nazwa.lower():
            return kod

    # build new code based on name
    base = re.sub(r"[^A-Za-z0-9]+", "_", nazwa.upper()).strip("_")
    kod = base or "ITEM"
    used = set(cat.keys()) | set(stany.keys())
    idx = 1
    while kod in used:
        idx += 1
        kod = f"{base}_{idx}"

    # persist new code in katalog
    cat[kod] = nazwa
    katalog[kategoria] = cat
    _ensure_dirs(KATALOG_PATH)
    with open(KATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(katalog, f, ensure_ascii=False, indent=2)

    return kod


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
    an additional record is stored in :data:`PRZYJECIA_PATH` and the simplified
    stock file :data:`STANY_PATH` is updated (new items are added when
    missing).
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

        # update simplified stock file and auto-register the item
        _ensure_dirs(STANY_PATH)
        stany = _load_json(STANY_PATH, {})
        rec = stany.setdefault(
            item_id,
            {
                "nazwa": item.get("nazwa", item_id),
                "stan": 0.0,
                "prog_alert": item.get("prog_alert", 0),
            },
        )
        rec["stan"] = float(rec.get("stan", 0)) + qty
        with open(STANY_PATH, "w", encoding="utf-8") as f:
            json.dump(stany, f, ensure_ascii=False, indent=2)

    return entry

