# version: 1.0
"""Obsługa opinii użytkowników WM z zachowaniem starego formatu danych."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None

from services.workforce_profile_service import get_user

STATUSES = ("nowa", "zaplanowana", "w_realizacji", "wykonana", "odrzucona")
STATUS_LABELS = {
    "nowa": "🔴 Nowa",
    "zaplanowana": "🟡 Zaplanowana",
    "w_realizacji": "🟠 W realizacji",
    "wykonana": "🟢 Wykonana",
    "odrzucona": "⚪ Odrzucona",
}


def feedback_path() -> Path:
    if root_paths is not None:
        try:
            return root_paths.get_data_root() / "opinie.json"
        except Exception:
            pass
    return Path("data") / "opinie.json"


def _read(default: Any) -> Any:
    try:
        with feedback_path().open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write(data: Any) -> None:
    path = feedback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip().casefold().replace(" ", "_")
    aliases = {
        "new": "nowa", "nowy": "nowa", "nowe": "nowa",
        "planned": "zaplanowana", "plan": "zaplanowana",
        "w_toku": "w_realizacji", "realizacja": "w_realizacji", "in_progress": "w_realizacji",
        "done": "wykonana", "zrobiona": "wykonana", "wykonane": "wykonana",
        "rejected": "odrzucona", "odrzucone": "odrzucona",
    }
    status = aliases.get(raw, raw)
    return status if status in STATUSES else "nowa"


def _normalize(row: dict, index: int = 0) -> dict:
    out = dict(row)
    login = str(out.get("login") or out.get("author") or "Gość").strip() or "Gość"
    if not str(out.get("id") or "").strip():
        stamp = str(out.get("ts") or out.get("created_at") or "")
        token = uuid.uuid5(uuid.NAMESPACE_URL, f"wm-feedback:{index}:{login}:{stamp}:{out.get('message','')}").hex[:10]
        out["id"] = f"OPN-{token.upper()}"
    user = get_user(login) or {}
    out.setdefault("user_id", str(user.get("user_id") or ""))
    out["login"] = login
    out.setdefault("login_snapshot", login)
    out.setdefault("rola_snapshot", str(out.get("rola") or user.get("rola") or ""))
    out["created_at"] = str(out.get("created_at") or out.get("ts") or "")
    out["ts"] = out["created_at"]
    out["message"] = str(out.get("message") or "").strip()
    out["module"] = str(out.get("module") or out.get("modul") or "Inne").strip() or "Inne"
    out["status"] = _normalize_status(out.get("status"))
    out.setdefault("handled_by", "")
    out.setdefault("handled_at", "")
    out.setdefault("decision_note", "")
    return out


def list_feedback(*, login: str | None = None, status: str | None = None) -> list[dict]:
    raw = _read([])
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("opinie") or list(raw.values())
    if not isinstance(raw, list):
        raw = []
    login_key = str(login or "").strip().casefold()
    status_key = _normalize_status(status) if status else ""
    rows: list[dict] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        row = _normalize(item, index)
        if login_key and str(row.get("login") or "").strip().casefold() != login_key:
            continue
        if status_key and row.get("status") != status_key:
            continue
        rows.append(row)
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows


def counts() -> dict[str, int]:
    out = {status: 0 for status in STATUSES}
    for row in list_feedback():
        out[row["status"]] = out.get(row["status"], 0) + 1
    return out


def update_feedback(feedback_id: str, *, status: str | None = None, module: str | None = None,
                    actor: str = "", decision_note: str | None = None) -> dict:
    raw = _read([])
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("opinie") or list(raw.values())
    if not isinstance(raw, list):
        raw = []
    normalized = [_normalize(item, idx) for idx, item in enumerate(raw) if isinstance(item, dict)]
    wanted = str(feedback_id or "").strip()
    target = None
    for row in normalized:
        if str(row.get("id") or "").strip() == wanted:
            target = row
            break
    if target is None:
        raise KeyError("Nie znaleziono opinii.")
    if status is not None:
        target["status"] = _normalize_status(status)
    if module is not None:
        target["module"] = str(module or "Inne").strip() or "Inne"
    if decision_note is not None:
        target["decision_note"] = str(decision_note or "").strip()
    if actor:
        target["handled_by"] = str(actor)
        target["handled_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write(normalized)
    return dict(target)


def status_label(status: str) -> str:
    return STATUS_LABELS.get(_normalize_status(status), "🔴 Nowa")


__all__ = ["STATUSES", "STATUS_LABELS", "feedback_path", "list_feedback", "counts", "update_feedback", "status_label"]
