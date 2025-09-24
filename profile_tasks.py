"""Helpers for reading task assignments for user profiles.

The functions defined here read task information from a couple of
well-known JSON files located in the :mod:`data` directory.  The format of
those files is intentionally permissive – both lists and dictionaries are
accepted – so that legacy dumps keep working.

Two public helpers are provided:

``get_tasks_for``
    Return a list of task records assigned to the given user.  Optional
    filters allow narrowing by status and by a deadline.

``workload_for``
    Calculate how many *active* tasks are assigned to each user from the
    provided iterable.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Iterable

from utils.path_utils import cfg_path

# Files checked for task definitions.  The first readable file wins.
_TASK_FILES = [
    os.path.join("data", "zlecenia.json"),
    os.path.join("data", "zadania.json"),
]

# Status names considered as "active" for workload computations.
_ACTIVE_STATUSES = {
    "nowe",
    "w_toku",
    "w toku",
    "otwarte",
    "open",
    "in_progress",
}


def _load_tasks_raw() -> list[dict[str, Any]]:
    """Return the first successfully loaded list of task records.

    The helper walks through :data:`_TASK_FILES` and returns the first JSON
    payload that can be decoded into either a list or a dictionary.  When a
    dictionary is encountered, its values are used as the task records.  Any
    decoding problem results in moving on to the next candidate.
    """

    for relative_path in _TASK_FILES:
        path = cfg_path(relative_path)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # pragma: no cover - defensive tolerance
            continue
        if isinstance(data, dict):
            return list(data.values())
        if isinstance(data, list):
            return data
    return []


def _normalize_login(value: str | None) -> str:
    """Return a canonical representation of a login value."""

    return str(value or "").strip().lower()


def _task_owner(rec: dict[str, Any]) -> str:
    """Extract task owner from a record in a tolerant way."""

    for key in ("owner", "login", "assigned_to"):
        if key in rec and rec[key]:
            return str(rec[key]).strip()
    return ""


def _task_status(rec: dict[str, Any]) -> str:
    """Return the normalised status value for a record."""

    raw = rec.get("status") or rec.get("stan") or ""
    return str(raw).strip().lower()


def _task_deadline(rec: dict[str, Any]) -> datetime | None:
    """Return a :class:`datetime` deadline extracted from ``rec``."""

    raw = rec.get("deadline") or rec.get("termin")
    if not raw:
        return None
    try:
        text = str(raw)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:  # pragma: no cover - tolerance for unexpected formats
        return None


def get_tasks_for(
    login: str,
    *,
    statusy: Iterable[str] | None = None,
    do_deadline: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return tasks assigned to ``login`` with optional filters applied."""

    login_norm = _normalize_login(login)
    if not login_norm:
        return []

    status_filter = (
        {str(s).strip().lower() for s in statusy}
        if statusy is not None
        else None
    )

    matched: list[dict[str, Any]] = []
    for record in _load_tasks_raw():
        if _normalize_login(_task_owner(record)) != login_norm:
            continue
        status = _task_status(record)
        if status_filter is not None and status not in status_filter:
            continue
        if do_deadline:
            deadline = _task_deadline(record)
            if deadline and deadline > do_deadline:
                continue
        matched.append(dict(record))
    return matched


def workload_for(
    users: Iterable[str],
    *,
    do_deadline: datetime | None = None,
) -> list[tuple[str, int]]:
    """Return ``(login, active_task_count)`` tuples for ``users``."""

    user_list = list(users)
    if not user_list:
        return []

    norm_to_original = {
        _normalize_login(login): login for login in user_list
    }
    counts: dict[str, int] = {login: 0 for login in user_list}

    for record in _load_tasks_raw():
        owner_norm = _normalize_login(_task_owner(record))
        original_login = norm_to_original.get(owner_norm)
        if original_login is None:
            continue
        if _task_status(record) not in _ACTIVE_STATUSES:
            continue
        if do_deadline:
            deadline = _task_deadline(record)
            if deadline and deadline > do_deadline:
                continue
        counts[original_login] += 1

    return sorted(counts.items(), key=lambda item: (item[1], item[0]))


__all__ = ["get_tasks_for", "workload_for"]

