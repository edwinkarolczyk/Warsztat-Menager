# version: 1.1
# Zmiany 1.1:
# - Statusy zachowują flagę visit_base z definicji narzędzi.
# - Jawnie oznaczony status bazowy jest zwracany jako pierwszy niezależnie od kolejności w pliku.
# - Dodano get_base_status() z fallbackiem do pierwszego statusu dla starych konfiguracji.
"""Utilities for loading tool tasks definitions with caching."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict

from config.paths import p_tools_defs
from config_manager import ConfigManager
import tools_autocheck

_CACHE_LOCK = threading.RLock()


def _resolve_tasks_path() -> str:
    """Return preferred path to ``zadania_narzedzia.json``."""

    try:
        cfg = ConfigManager()
        path = p_tools_defs(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception:
        return str(Path("zadania_narzedzia.json").resolve())


_TASKS_PATH = _resolve_tasks_path()
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
    "get_base_status",
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
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME, _TASKS_PATH, TOOL_TASKS_PATH
    with _CACHE_LOCK:
        path = _resolve_tasks_path()
        if path != _TASKS_PATH:
            _TASKS_PATH = TOOL_TASKS_PATH = path
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
    """Return statuses for given tool type, with the explicit visit base first."""
    _ensure_cache()
    coll = collection or _default_collection()
    with _CACHE_LOCK:
        tasks = _TOOL_TASKS_CACHE or {}
        types_list = tasks.get(coll, [])
    for t in types_list:
        if t.get("id") != type_id:
            continue

        result: list[dict] = []
        explicit_base_index: int | None = None
        for s in (t.get("statuses") or []):
            is_base = bool(s.get("visit_base"))
            row = {
                "id": s.get("id"),
                "name": s.get("name", s.get("id")),
                "visit_base": is_base,
            }
            if is_base and explicit_base_index is None:
                explicit_base_index = len(result)
            result.append(row)

        # Stare GUI wizyt traktuje pierwszy status jako bazowy. Jeżeli mamy
        # jawne visit_base, przenosimy go logicznie na początek odpowiedzi,
        # nie zmieniając kolejności zapisanej w pliku konfiguracyjnym.
        if explicit_base_index is not None and explicit_base_index > 0:
            base = result.pop(explicit_base_index)
            result.insert(0, base)
        return result
    return []


def get_base_status(type_id: str, collection: str | None = None) -> dict | None:
    """Return the visit base status; fall back to the first status for legacy data."""
    statuses = get_statuses(type_id, collection=collection)
    if not statuses:
        return None
    for status in statuses:
        if bool(status.get("visit_base")):
            return status
    return statuses[0]


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


# Backward compatibility aliases
get_tool_types_list = get_tool_types
get_statuses_for_type = get_statuses
