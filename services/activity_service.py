"""Utilities for storing and querying user activity logs."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Union

BASE_DIR = os.path.join("data", "activity")
os.makedirs(BASE_DIR, exist_ok=True)


def _activity_path(login: str) -> str:
    """Return the path of the JSON lines file for the provided login."""
    return os.path.join(BASE_DIR, f"{login}.jsonl")


def _append(login: str, record: Dict[str, Any]) -> None:
    """Append a single record to the activity log for the login."""
    path = _activity_path(login)
    with open(path, "a", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False)
        file.write("\n")


def _now_iso() -> str:
    """Return the current UTC timestamp encoded in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_activity(login: str, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist information about an activity event for a user."""
    record = {
        "id": str(uuid.uuid4()),
        "ts": _now_iso(),
        "event": event,
        "payload": payload or {},
    }
    _append(login, record)
    return record


def _load_activity(login: str) -> List[Dict[str, Any]]:
    """Load activity rows from newest to oldest."""
    path = _activity_path(login)
    if not os.path.exists(path):
        return []

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.reverse()
    return rows


def list_activity(login: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Return the most recent activity entries for ``login``."""
    try:
        limit_value = max(1, int(limit))
    except (TypeError, ValueError):
        limit_value = 1

    rows = _load_activity(login)
    return rows[:limit_value]


TimestampInput = Union[str, datetime]
EventFilter = Union[str, Iterable[str]]


def _parse_timestamp(value: str) -> Optional[datetime]:
    """Parse an ISO timestamp stored in a log record."""
    if not value:
        return None

    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_filter(value: Optional[TimestampInput]) -> Optional[datetime]:
    """Normalize timestamp filter inputs to aware UTC datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        normalized = value
    else:
        normalized = _parse_timestamp(value)
        if normalized is None:
            return None

    if normalized.tzinfo is None:
        return normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc)


def list_activity_filtered(
    login: str,
    *,
    ev_type: Optional[EventFilter] = None,
    date_from: Optional[TimestampInput] = None,
    date_to: Optional[TimestampInput] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Return user activity entries filtered by event type and date range."""

    try:
        limit_value = max(1, int(limit))
    except (TypeError, ValueError):
        limit_value = 1

    normalized_from = _normalize_filter(date_from)
    normalized_to = _normalize_filter(date_to)
    if ev_type is None:
        normalized_events: Optional[set[str]] = None
    elif isinstance(ev_type, str):
        normalized_events = {ev_type}
    else:
        normalized_events = {
            value for value in ev_type if isinstance(value, str) and value
        }

    rows = _load_activity(login)

    def _matches_filters(row: Dict[str, Any]) -> bool:
        if normalized_events is not None:
            event_name = row.get("event")
            if event_name not in normalized_events:
                return False

        timestamp_str = row.get("ts", "")
        timestamp = _parse_timestamp(timestamp_str)
        if normalized_from or normalized_to:
            if timestamp is None:
                return False
            if normalized_from and timestamp < normalized_from:
                return False
            if normalized_to and timestamp > normalized_to:
                return False
        return True

    filtered = [row for row in rows if _matches_filters(row)]
    return filtered[:limit_value]
