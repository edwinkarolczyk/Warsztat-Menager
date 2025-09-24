"""Utilities for recording and reading lightweight activity streams."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

ACTIVITY_FILE = os.path.join("data", "activity_log.jsonl")
os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 10:
        text = f"{text}T00:00:00"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _iter_records() -> Iterable[Dict[str, Any]]:
    if not os.path.exists(ACTIVITY_FILE):
        return []
    with open(ACTIVITY_FILE, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            if isinstance(data, dict):
                yield data


def log_activity(
    login: str,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Append ``(login, event, payload)`` entry to the activity log."""

    login_text = str(login or "").strip()
    event_text = str(event or "").strip()
    if not login_text or not event_text:
        return

    payload_data: Dict[str, Any] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            safe_key = str(key)
            try:
                json.dumps(value, ensure_ascii=False)
                payload_data[safe_key] = value
            except TypeError:
                payload_data[safe_key] = str(value)

    record = {
        "ts": _now_ts(),
        "login": login_text,
        "event": event_text,
        "payload": payload_data,
    }
    with open(ACTIVITY_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_activity_filtered(
    login: str,
    *,
    ev_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Return activities for ``login`` filtered by optional criteria."""

    login_norm = str(login or "").strip().lower()
    type_norm = str(ev_type or "").strip()
    start_ts = _parse_ts(date_from) if date_from else None
    end_ts = _parse_ts(date_to) if date_to else None

    matched: List[Dict[str, Any]] = []
    for record in _iter_records():
        rec_login = str(record.get("login", "")).strip().lower()
        if login_norm and rec_login != login_norm:
            continue
        rec_type = str(record.get("event", "")).strip()
        if type_norm and rec_type != type_norm:
            continue
        ts_value = _parse_ts(record.get("ts"))
        if start_ts and (ts_value is None or ts_value < start_ts):
            continue
        if end_ts and (ts_value is None or ts_value > end_ts):
            continue
        matched.append(dict(record))

    matched.sort(
        key=lambda item: _parse_ts(item.get("ts")) or datetime.min,
        reverse=True,
    )
    if limit >= 0:
        return matched[:limit]
    return matched


__all__ = ["log_activity", "list_activity_filtered"]

