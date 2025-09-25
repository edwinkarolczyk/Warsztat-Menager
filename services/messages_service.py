# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

BASE_DIR = os.path.join("data", "messages")
os.makedirs(BASE_DIR, exist_ok=True)
MAX_LINES = 10_000  # rotacja po 10k lini


def _path(login: str) -> str:
    return os.path.join(BASE_DIR, f"{login}.jsonl")


def _count_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


def _rotate_if_needed(path: str) -> None:
    if not os.path.exists(path):
        return
    if _count_lines(path) < MAX_LINES:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    archive = path.replace(".jsonl", f".{timestamp}.jsonl")
    try:
        os.replace(path, archive)
    except Exception:
        pass


def _append(login: str, rec: dict) -> None:
    path = _path(login)
    _rotate_if_needed(path)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_all(login: str) -> list[dict]:
    path = _path(login)
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def send_message(
    sender: str,
    to: str,
    subject: str,
    body: str,
    refs: Optional[list[dict]] = None,
) -> dict:
    """Zapisuje wiadomość do skrzynki nadawcy i odbiorcy (obie kopie)."""

    msg = {
        "id": str(uuid.uuid4()),
        "ts": _now_iso(),
        "from": sender,
        "to": to,
        "subject": subject or "",
        "body": body or "",
        "refs": refs or [],
        "read": False,
    }
    _append(sender, dict(msg, folder="sent"))
    _append(to, dict(msg, folder="inbox"))
    _append(to, {"folder": "_last_marker", "ts": msg["ts"]})
    return msg


def list_inbox(login: str, *, q: Optional[str] = None) -> list[dict]:
    rows = [m for m in _read_all(login) if m.get("folder") == "inbox"]
    if q:
        query = q.lower()
        rows = [
            m
            for m in rows
            if query in (
                (m.get("subject", "") + m.get("from", "") + m.get("body", ""))
            ).lower()
        ]
    rows.sort(key=lambda m: m.get("ts", ""), reverse=True)
    return rows


def list_sent(login: str, *, q: Optional[str] = None) -> list[dict]:
    rows = [m for m in _read_all(login) if m.get("folder") == "sent"]
    if q:
        query = q.lower()
        rows = [
            m
            for m in rows
            if query in (
                (m.get("subject", "") + m.get("to", "") + m.get("body", ""))
            ).lower()
        ]
    rows.sort(key=lambda m: m.get("ts", ""), reverse=True)
    return rows


def last_inbox_ts(login: str) -> str | None:
    """Zwraca timestamp ostatniego markera _last_marker (na końcu pliku)."""

    path = _path(login)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            back = min(size, 8192)
            fh.seek(-back, os.SEEK_END)
            tail = fh.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(tail):
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if record.get("folder") == "_last_marker":
                    return record.get("ts")
    except Exception:
        return None
    return None


def mark_read(login: str, msg_id: str, read: bool = True) -> bool:
    path = _path(login)
    arr = _read_all(login)
    changed = False
    for message in arr:
        if message.get("id") == msg_id and message.get("folder") == "inbox":
            message["read"] = bool(read)
            changed = True
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for message in arr:
            fh.write(json.dumps(message, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return changed
