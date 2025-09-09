"""Utilities for tool history tracking."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ACTIONS = {
    "create",
    "edit",
    "status_change",
    "task_autocheck",
    "assign",
    "qr_issue",
    "qr_return",
    "qr_fault",
}

TOOL_HISTORY_DIR = Path("data") / "narzedzia_historia"


def append_tool_history(tool_id: str, user: str, action: str, **kwargs: Any) -> None:
    """Append an entry to the tool history log.

    Parameters:
        tool_id: Identifier of the tool.
        user: User performing the action.
        action: Allowed action type.
        **kwargs: Additional data stored in the entry.

    The entry is appended as a JSON line with a UTC timestamp.
    """
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "action": action,
        **kwargs,
    }

    dest_dir = TOOL_HISTORY_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{tool_id}.jsonl"

    line = json.dumps(entry, ensure_ascii=False)
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(line + "\n")
