from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DATA_PATH = Path("data") / "zadania_przypisania.json"


def _load_all() -> List[Dict[str, Any]]:
    """Load all assignment records from the JSON file."""
    if DATA_PATH.exists():
        try:
            with open(DATA_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_all(data: List[Dict[str, Any]]) -> None:
    """Persist assignment records to the JSON file."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def assign(task_id: str, user: str, context: str) -> None:
    """Assign ``task_id`` in ``context`` to ``user``."""
    data = _load_all()
    for rec in data:
        if rec.get("task") == task_id and rec.get("context") == context:
            rec["user"] = user
            _save_all(data)
            return
    data.append({"task": task_id, "user": user, "context": context})
    _save_all(data)


def unassign(task_id: str, context: str) -> None:
    """Remove assignment for ``task_id`` in ``context``."""
    data = [
        rec
        for rec in _load_all()
        if not (rec.get("task") == task_id and rec.get("context") == context)
    ]
    _save_all(data)


def list_for_user(user: str) -> List[Dict[str, Any]]:
    """Return assignments for ``user``."""
    return [rec for rec in _load_all() if rec.get("user") == user]


def list_in_context(context: str) -> List[Dict[str, Any]]:
    """Return assignments belonging to ``context``."""
    return [rec for rec in _load_all() if rec.get("context") == context]


def list_all() -> List[Dict[str, Any]]:
    """Return all assignment records."""
    return _load_all()


__all__ = [
    "assign",
    "unassign",
    "list_for_user",
    "list_in_context",
    "list_all",
]
