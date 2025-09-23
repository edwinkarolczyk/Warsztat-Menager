# -*- coding: utf-8 -*-
# services/messages_service.py
from __future__ import annotations
import os, json, uuid
from datetime import datetime, timezone
from typing import Iterable

BASE_DIR = os.path.join("data", "messages")
os.makedirs(BASE_DIR, exist_ok=True)

def _path(login: str) -> str:
    return os.path.join(BASE_DIR, f"{login}.jsonl")

def _append(login: str, rec: dict) -> None:
    p = _path(login)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _read_all(login: str) -> list[dict]:
    p = _path(login)
    if not os.path.exists(p):
        return []
    out: list[dict] = []
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

def send_message(sender: str, to: str, subject: str, body: str, refs: list[dict] | None = None) -> dict:
    """Zapisuje wiadomość do skrzynki nadawcy i odbiorcy."""
    msg = {
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

def list_inbox(login: str) -> list[dict]:
    return [m for m in _read_all(login) if m.get("folder") == "inbox"]

def list_sent(login: str) -> list[dict]:
    return [m for m in _read_all(login) if m.get("folder") == "sent"]

def mark_read(login: str, msg_id: str, read: bool = True) -> bool:
    """Prosta implementacja: przepisuje plik ustawiając read dla danego id."""
    p = _path(login); arr = _read_all(login)
    changed = False
    for m in arr:
        if m.get("id") == msg_id and m.get("folder") == "inbox":
            m["read"] = bool(read); changed = True
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for m in arr:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    os.replace(tmp, p)
    return changed
