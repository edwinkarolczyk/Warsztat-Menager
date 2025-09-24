# -*- coding: utf-8 -*-
# services/messages_service.py
from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

BASE_DIR = os.path.join("data", "messages")
os.makedirs(BASE_DIR, exist_ok=True)

def _path(login: str) -> str:
    return os.path.join(BASE_DIR, f"{login}.jsonl")

def _append(login: str, rec: Dict[str, Any]) -> None:
    p = _path(login)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _read_all(login: str) -> List[Dict[str, Any]]:
    p = _path(login)
    if not os.path.exists(p):
        return []
    out: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def send_message(
    sender: str,
    to: str,
    subject: str,
    body: str,
    refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Zapisuje wiadomość do skrzynki nadawcy i odbiorcy."""
    msg: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "from": sender,
        "to": to,
        "subject": subject or "",
        "body": body or "",
        "refs": refs or [],
        "read": False,
    }
    _append(sender, dict(msg, folder="sent"))
    _append(to, dict(msg, folder="inbox"))
    return msg

def _matches_query(message: Dict[str, Any], query: Optional[str]) -> bool:
    if not query:
        return True
    text = str(query).strip().lower()
    if not text:
        return True
    for key in ("subject", "body", "from", "to"):
        value = str(message.get(key, "")).lower()
        if text in value:
            return True
    return False

def _filter_messages(messages: Iterable[Dict[str, Any]], query: Optional[str]) -> List[Dict[str, Any]]:
    return [m for m in messages if _matches_query(m, query)]


def list_inbox(login: str, q: Optional[str] = None) -> List[Dict[str, Any]]:
    messages = (m for m in _read_all(login) if m.get("folder") == "inbox")
    return _filter_messages(messages, q)


def list_sent(login: str, q: Optional[str] = None) -> List[Dict[str, Any]]:
    messages = (m for m in _read_all(login) if m.get("folder") == "sent")
    return _filter_messages(messages, q)

def mark_read(login: str, msg_id: str, read: bool = True) -> bool:
    """Prosta implementacja: przepisuje plik ustawiając 'read' dla danego id w Inbox."""
    p = _path(login)
    arr = _read_all(login)
    changed = False
    for m in arr:
        if m.get("id") == msg_id and m.get("folder") == "inbox":
            m["read"] = bool(read)
            changed = True
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for m in arr:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    os.replace(tmp, p)
    return changed


def last_inbox_ts(login: str) -> Optional[str]:
    """Return timestamp of the newest inbox message for ``login``."""

    latest: Optional[str] = None
    for message in _read_all(login):
        if message.get("folder") != "inbox":
            continue
        ts = message.get("ts")
        if not isinstance(ts, str):
            continue
        if latest is None or str(ts) > str(latest):
            latest = str(ts)
    return latest
