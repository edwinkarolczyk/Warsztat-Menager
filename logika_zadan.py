"""Utilities for loading tool tasks definitions with caching."""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

from config_manager import ConfigManager
import tools_autocheck

_CACHE_LOCK = threading.RLock()
_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOL_TASKS_CACHE: dict[str, list[dict]] | None = None
_TOOL_TASKS_MTIME: float | None = None

# Backward compatibility for external modules
TOOL_TASKS_PATH = _TASKS_PATH


def invalidate_cache() -> None:
    """Clear cached tasks definitions."""
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    with _CACHE_LOCK:
        _TOOL_TASKS_CACHE = None
        _TOOL_TASKS_MTIME = None
        print("[WM-DBG][NARZ] Cache zadań wyczyszczony.")

__all__ = [
    "TOOL_TASKS_PATH",
    "HISTORY_PATH",
    "invalidate_cache",
    "get_collections",
    "get_default_collection",
    "get_tool_types",
    "get_statuses",
    "get_tasks",
    "should_autocheck",
    "get_tool_types_list",
    "get_statuses_for_type",
    "register_tasks_state",
    "consume_for_task",
]


def _safe_load() -> dict:
    try:
        with open(_TASKS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WM-DBG][NARZ][WARN] Nie można odczytać {_TASKS_PATH}: {exc}")
        return {}


def _ensure_cache() -> None:
    """Load definitions if cache is empty or file changed."""
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    with _CACHE_LOCK:
        try:
            mtime = os.path.getmtime(_TASKS_PATH)
        except OSError:
            mtime = None
        if _TOOL_TASKS_CACHE is not None and _TOOL_TASKS_MTIME == mtime:
            return
        data = _safe_load() or {}
        collections = data.get("collections") or {}
        _TOOL_TASKS_CACHE = {
            cid: coll.get("types") or [] for cid, coll in collections.items()
        }
        _TOOL_TASKS_MTIME = mtime
        print(f"[WM-DBG][NARZ] Przeładowano definicje zadań (mtime={mtime})")


def _default_collection() -> str:
    cfg = ConfigManager()
    enabled = cfg.get("tools.collections_enabled", []) or []
    return cfg.get("tools.default_collection", enabled[0] if enabled else "default")


def get_collections(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    """Return list of available collections."""
    _ensure_cache()
    with _CACHE_LOCK:
        cache = _TOOL_TASKS_CACHE or {}
    return [{"id": cid, "name": cid} for cid in cache.keys()]


def get_default_collection(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> str:
    cfg = settings or ConfigManager()
    getter = cfg.get
    enabled = getter("tools.collections_enabled", []) or []
    return getter("tools.default_collection", enabled[0] if enabled else "default")


def get_tool_types(collection: str | None = None) -> list[dict]:
    """Return tool types for given collection."""
    _ensure_cache()
    coll = collection or _default_collection()
    with _CACHE_LOCK:
        tasks = _TOOL_TASKS_CACHE or {}
        types_list = tasks.get(coll, [])
    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in types_list
    ]


def get_statuses(type_id: str, collection: str | None = None) -> list[dict]:
    """Return statuses for given tool type."""
    _ensure_cache()
    coll = collection or _default_collection()
    with _CACHE_LOCK:
        tasks = _TOOL_TASKS_CACHE or {}
        types_list = tasks.get(coll, [])
    for t in types_list:
        if t.get("id") == type_id:
            return [
                {"id": s.get("id"), "name": s.get("name", s.get("id"))}
                for s in (t.get("statuses") or [])
            ]
    return []


def get_tasks(type_id: str, status_id: str, collection: str | None = None) -> list[str]:
    """Return tasks list for given type and status."""
    _ensure_cache()
    coll = collection or _default_collection()
    with _CACHE_LOCK:
        tasks = _TOOL_TASKS_CACHE or {}
        types_list = tasks.get(coll, [])
    for t in types_list:
        if t.get("id") == type_id:
            for st in t.get("statuses") or []:
                if st.get("id") == status_id:
                    return list(st.get("tasks") or [])
    return []


def should_autocheck(
    status_id: str,
    collection_id: str,
    config: ConfigManager | Dict[str, Any] | None = None,
) -> bool:
    _ensure_cache()
    cfg = config
    if cfg is None:
        cfg = ConfigManager().merged
    elif isinstance(cfg, ConfigManager):
        cfg = cfg.merged
    return tools_autocheck.should_autocheck(status_id, collection_id, cfg)

get_tool_types_list = get_tool_types
get_statuses_for_type = get_statuses


get_tool_types_list = get_tool_types
get_statuses_for_type = get_statuses


# Backward compatibility aliases
get_tool_types_list = get_tool_types
get_statuses_for_type = get_statuses

