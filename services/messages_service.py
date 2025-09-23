"""Utilities for handling private messages (PW)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List

MESSAGES_FILE = os.path.join("data", "messages_pw.json")


def _load_messages(path: str = MESSAGES_FILE) -> List[Dict[str, Any]]:
    """Load messages list from ``path``."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [msg for msg in data if isinstance(msg, dict)]


def _save_messages(messages: Iterable[Dict[str, Any]], path: str = MESSAGES_FILE) -> None:
    """Persist messages iterable to ``path``."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(list(messages), fh, ensure_ascii=False, indent=2)


def _next_id(messages: Iterable[Dict[str, Any]]) -> int:
    max_id = 0
    for msg in messages:
        try:
            max_id = max(max_id, int(msg.get("id", 0)))
        except Exception:
            continue
    return max_id + 1


def _normalize_login(value: str | None) -> str:
    return (value or "").strip().lower()


def _sort_messages(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _key(msg: Dict[str, Any]) -> tuple:
        ts = msg.get("ts")
        if isinstance(ts, str):
            try:
                parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
        else:
            parsed = None
        try:
            ident = int(msg.get("id", 0))
        except Exception:
            ident = 0
        return (
            parsed or datetime.min,
            ident,
        )

    return sorted(messages, key=_key, reverse=True)


def send_message(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    refs: Iterable[str] | None = None,
    storage_path: str = MESSAGES_FILE,
) -> Dict[str, Any]:
    """Store new private message and return its record."""

    messages = _load_messages(storage_path)
    next_id = _next_id(messages)
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry: Dict[str, Any] = {
        "id": next_id,
        "from": sender,
        "to": to,
        "subject": subject or "Bez tematu",
        "body": body or "",
        "refs": list(refs or []),
        "ts": timestamp,
        "read": False,
    }
    messages.append(entry)
    _save_messages(messages, storage_path)
    return entry


def _filter_messages(
    login: str,
    predicate: str,
    storage_path: str = MESSAGES_FILE,
) -> List[Dict[str, Any]]:
    messages = _load_messages(storage_path)
    login_norm = _normalize_login(login)
    filtered = [
        msg
        for msg in messages
        if _normalize_login(msg.get(predicate)) == login_norm
    ]
    return _sort_messages(filtered)


def list_inbox(login: str, storage_path: str = MESSAGES_FILE) -> List[Dict[str, Any]]:
    """Return messages received by ``login`` (most recent first)."""

    return _filter_messages(login, "to", storage_path)


def list_sent(login: str, storage_path: str = MESSAGES_FILE) -> List[Dict[str, Any]]:
    """Return messages sent by ``login`` (most recent first)."""

    return _filter_messages(login, "from", storage_path)


__all__ = [
    "send_message",
    "list_inbox",
    "list_sent",
]
