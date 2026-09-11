# version: 1.1
# Zmiany 1.1:
# - Zapisy zadań pojedynczego narzędzia korzystają ze wspólnego, blokowanego writer-a JSON.
"""Helper utilities for working with narzędzia JSON data."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from config.paths import p_tools_data, p_tools_defs
from config_manager import ConfigManager
from utils_json import safe_write_json


def _tools_data_dir() -> Path:
    try:
        cfg = ConfigManager()
        path = p_tools_data(cfg).parent
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return Path(__file__).resolve().parent / "data" / "narzedzia"


DATA_DIR = _tools_data_dir()


def _task_definitions_path() -> Path:
    try:
        cfg = ConfigManager()
        path = p_tools_defs(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return Path(__file__).resolve().parent / "data" / "zadania_narzedzia.json"


RE_NR3 = re.compile(r"^\d{3}$")

_STATUS_TASKS_CACHE: Optional[Dict[str, Dict[str, List[str]]]] = None


def tool_task_id(tool_nr: str, index: int) -> str:
    """Return stable task identifier for ``tool_nr`` and zero-based ``index``."""

    nr = str(tool_nr).strip()
    if not nr:
        nr = "000"
    try:
        idx = max(0, int(index))
    except (TypeError, ValueError):
        idx = 0
    return f"NARZ-{nr}-{idx + 1:02d}"


def _now_iso() -> str:
    """Return current timestamp in ISO format without microseconds."""

    return datetime.now().replace(microsecond=0).isoformat()


def is_valid_tool_record(doc: dict) -> bool:
    """Return True when the tool document has a three-digit ``nr`` field."""

    if not isinstance(doc, dict):
        return False
    nr = str(doc.get("nr") or "").strip()
    return bool(RE_NR3.match(nr))


def iter_tools_json() -> Iterable[Tuple[Path, dict]]:
    """Yield ``(path, doc)`` for tool files with valid ``nr`` values."""

    if not DATA_DIR.exists():
        return
    for path in DATA_DIR.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if is_valid_tool_record(doc):
                yield path, doc
        except Exception:
            continue


def _load_status_tasks() -> Dict[str, Dict[str, List[str]]]:
    """Load and cache status task definitions from the data file."""

    global _STATUS_TASKS_CACHE
    if _STATUS_TASKS_CACHE is not None:
        return _STATUS_TASKS_CACHE
    try:
        payload = json.loads(_task_definitions_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        _STATUS_TASKS_CACHE = {}
        return _STATUS_TASKS_CACHE
    except json.JSONDecodeError:
        _STATUS_TASKS_CACHE = {}
        return _STATUS_TASKS_CACHE
    typy = payload.get("typy")
    if not isinstance(typy, dict):
        _STATUS_TASKS_CACHE = {}
        return _STATUS_TASKS_CACHE
    normalized: Dict[str, Dict[str, List[str]]] = {}
    for typ_name, typ_payload in typy.items():
        statusy = typ_payload.get("statusy") if isinstance(typ_payload, dict) else None
        if not isinstance(statusy, dict):
            continue
        normalized[typ_name] = {}
        for status_name, tasks in statusy.items():
            if isinstance(tasks, list):
                normalized[typ_name][status_name] = [str(t) for t in tasks]
    _STATUS_TASKS_CACHE = normalized
    return _STATUS_TASKS_CACHE


def status_tasks_for(tool_type: str, status: str) -> List[str]:
    """Return task titles defined for ``(tool_type, status)``."""

    if not tool_type or not status:
        return []
    status_map = _load_status_tasks()
    return list(status_map.get(tool_type, {}).get(status, []))


def ensure_task_shape(task: dict) -> dict:
    """Normalize a single task entry to ensure expected fields exist."""

    if not isinstance(task, dict):
        return {}
    if "tytul" not in task and task.get("title") is not None:
        task["tytul"] = task.get("title")
    task.setdefault("done", False)
    if task.get("assigned_to") in ("", " "):
        task["assigned_to"] = None
    task.setdefault("assigned_to", None)
    task.setdefault("source", "own")
    return task


def is_pending_task(task: dict) -> bool:
    """Return ``True`` when a task should be considered pending."""

    if not isinstance(task, dict):
        return False
    done_val = task.get("done")
    if done_val in (None, "", "nie", "false", "False", "0", 0, False):
        return True
    try:
        if isinstance(done_val, str):
            if done_val.strip().lower() in ("false", "nie", "no", "0", ""):
                return True
        if isinstance(done_val, (int, float)) and done_val == 0:
            return True
    except Exception:
        pass
    return False


def merge_tasks_with_status_templates(tool_doc: dict) -> List[Tuple[Union[int, Tuple[str, str]], dict]]:
    """Merge pending tasks from ``tool_doc`` with status templates."""

    if not isinstance(tool_doc, dict):
        return []
    tasks: List[Tuple[Union[int, Tuple[str, str]], dict]] = []
    existing = tool_doc.get("zadania")
    if not isinstance(existing, list):
        existing = []
    pending_titles = set()
    for idx, raw_task in enumerate(existing):
        task = ensure_task_shape(raw_task if isinstance(raw_task, dict) else {})
        if not task:
            continue
        title = task.get("tytul") or task.get("title")
        if title:
            pending_titles.add(title)
        tasks.append((idx, task))
    templates = status_tasks_for(tool_doc.get("typ"), tool_doc.get("status"))
    for title in templates:
        if title in pending_titles:
            continue
        template_task = ensure_task_shape({
            "tytul": title,
            "done": False,
            "assigned_to": None,
            "source": "status",
        })
        tasks.append((("T", title), template_task))
    return tasks


def assign_task(doc: dict, index: int, login: str) -> bool:
    """Set ``assigned_to`` for a task in ``doc['zadania'][index]``."""

    if not isinstance(doc, dict):
        return False
    tasks = doc.get("zadania")
    if not isinstance(tasks, list):
        return False
    if index < 0 or index >= len(tasks):
        return False
    task = ensure_task_shape(tasks[index])
    task["assigned_to"] = login
    task["source"] = task.get("source") or "own"
    tasks[index] = task
    doc["zadania"] = tasks
    return True


def assign_task_any(tool_doc: dict, key: Union[int, Tuple[str, str]], login: str) -> Tuple[bool, Optional[int]]:
    """Assign an existing task or instantiate a status template for ``login``."""

    if not isinstance(tool_doc, dict):
        return False, None
    tasks = tool_doc.get("zadania")
    if not isinstance(tasks, list):
        tasks = []
    if isinstance(key, int):
        if key < 0 or key >= len(tasks):
            return False, None
        task = ensure_task_shape(tasks[key])
        task["assigned_to"] = login
        tasks[key] = task
        tool_doc["zadania"] = tasks
        return True, key
    if isinstance(key, tuple) and len(key) == 2 and key[0] == "T":
        title = key[1]
        new_task = {
            "tytul": title,
            "done": False,
            "assigned_to": login,
            "source": "status",
            "status": "active",
            "state": "active",
            "date_added": _now_iso(),
            "date_done": "",
        }
        tasks.append(new_task)
        tool_doc["zadania"] = tasks
        return True, len(tasks) - 1
    return False, None


def save_tool_json(path: Path, doc: dict):
    """Persist ``doc`` through the guarded tool JSON writer."""

    if not safe_write_json(str(path), doc):
        raise OSError(f"Nie udało się zapisać narzędzia: {path}")
