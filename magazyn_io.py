"""I/O helpers for warehouse history."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from config_manager import ConfigManager, get_by_key
from utils.path_utils import cfg_path

__all__ = [
    "append_history",
    "get_mag_categories",
    "get_mag_material_types",
    "get_mag_units",
]
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


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    """Load ``settings_schema.json`` once and cache it."""

    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        path = cfg_path("settings_schema.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                _SCHEMA_CACHE = json.load(f)
        except Exception:
            _SCHEMA_CACHE = {}
    return _SCHEMA_CACHE


def _schema_default(key: str):
    """Return default value for ``key`` from settings schema."""

    def walk(obj) -> Iterable:
        if isinstance(obj, dict):
            if obj.get("key") == key:
                yield obj.get("default")
            for v in obj.values():
                yield from walk(v)
        elif isinstance(obj, list):
            for it in obj:
                yield from walk(it)

    for val in walk(_load_schema()):
        if val is not None:
            return val
    return None


def _cfg_get(cfg: Any, key: str):
    """Fetch ``key`` from ``cfg`` with fallback to schema defaults."""

    if isinstance(cfg, ConfigManager):
        val = cfg.get(key, None)
        if val is not None:
            return val
    elif isinstance(cfg, dict):
        val = get_by_key(cfg, key, None)
        if val is not None:
            return val
    return _schema_default(key)


def get_mag_categories(cfg: ConfigManager | Dict[str, Any] | None = None) -> list:
    """Return warehouse categories from config or schema defaults."""

    keys = (
        "magazyn_kategorie",
        "mag.categories",
        "magazyn.categories",
        "mag_categories",
    )
    cfg = cfg or ConfigManager()
    for key in keys:
        val = _cfg_get(cfg, key)
        if isinstance(val, list):
            return val
    return []


def get_mag_material_types(
    cfg: ConfigManager | Dict[str, Any] | None = None,
) -> list:
    """Return material types from config or schema defaults."""

    keys = (
        "magazyn_typy_materialow",
        "mag.material_types",
        "magazyn.material_types",
        "mag_material_types",
    )
    cfg = cfg or ConfigManager()
    for key in keys:
        val = _cfg_get(cfg, key)
        if isinstance(val, list):
            return val
    return []


def get_mag_units(
    cfg: ConfigManager | Dict[str, Any] | None = None,
):
    """Return units mapping from config or schema defaults."""

    keys = (
        "jednostki_miary",
        "mag.units",
        "magazyn.units",
        "mag_units",
        "magazyn_jednostki",
    )
    cfg = cfg or ConfigManager()
    for key in keys:
        val = _cfg_get(cfg, key)
        if isinstance(val, (dict, list)):
            return val
    default = _schema_default(keys[0])
    return default if isinstance(default, (dict, list)) else {}

