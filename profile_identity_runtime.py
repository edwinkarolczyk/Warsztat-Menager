# version: 1.0
"""Spójność trwałego user_id przy zmianie loginu pracownika.

Warstwa nie wykonuje hurtowej migracji. Dopiero przed faktyczną zmianą loginu
uzupełnia brakujące ``user_id`` w historycznych rekordach tej jednej osoby,
zachowując stare pola login/login_snapshot jako czytelny snapshot.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_INSTALLED = False


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _matches_login(row: dict, login: str) -> bool:
    wanted = _key(login)
    if not wanted:
        return False
    return wanted in {
        _key(row.get("login")),
        _key(row.get("login_snapshot")),
        _key(row.get("author")),
    }


def _stamp_row(row: dict, login: str, user_id: str) -> bool:
    if not _matches_login(row, login):
        return False
    if str(row.get("user_id") or "").strip():
        return False
    row["user_id"] = str(user_id or "").strip()
    row.setdefault("login_snapshot", str(login or "").strip())
    return True


def _stamp_payload(payload: Any, login: str, user_id: str) -> bool:
    changed = False
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict):
                changed = _stamp_row(row, login, user_id) or changed
        return changed
    if not isinstance(payload, dict):
        return False

    for key in ("items", "requests", "leaves", "opinie"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    changed = _stamp_row(row, login, user_id) or changed
            return changed

    # Historyczne słowniki id -> rekord.
    for row in payload.values():
        if isinstance(row, dict):
            changed = _stamp_row(row, login, user_id) or changed
    return changed


def _backfill_feedback(login: str, user_id: str) -> None:
    from services import feedback_service

    raw = feedback_service._read([])
    if _stamp_payload(raw, login, user_id):
        feedback_service._write(raw)


def _backfill_leaves(login: str, user_id: str) -> None:
    from services import leave_workflow_service as leaves

    for path in (leaves.leaves_path(), leaves.requests_path()):
        raw = leaves._read_json(path, [])
        if _stamp_payload(raw, login, user_id):
            leaves._write_json(path, raw)


def _backfill_attendance(login: str, user_id: str) -> None:
    from services import attendance_service as attendance

    path = attendance.data_path()
    doc = attendance._read(path, {})
    changed = False
    if isinstance(doc, dict):
        wanted = _key(login)
        for day in doc.values():
            if not isinstance(day, dict):
                continue
            for slot_map in day.values():
                if not isinstance(slot_map, dict):
                    continue
                for storage_key, rec in slot_map.items():
                    if not isinstance(rec, dict):
                        continue
                    matches = _key(storage_key) == wanted or _matches_login(rec, login)
                    if matches and not str(rec.get("user_id") or "").strip():
                        rec["user_id"] = str(user_id or "").strip()
                        rec.setdefault("login_snapshot", str(login or "").strip())
                        changed = True
    if changed:
        attendance._write(path, doc)

    audit = attendance._read(attendance.audit_path(), [])
    if _stamp_payload(audit, login, user_id):
        attendance._write(attendance.audit_path(), audit)


def _backfill_profile_audit(login: str, user_id: str) -> None:
    try:
        from core import root_paths
        import json
        import os

        path = Path(root_paths.get_data_root()) / "profile_admin_audit.json"
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            return
        if not _stamp_payload(raw, login, user_id):
            return
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        raise


def backfill_user_identity(login: str, user_id: str) -> None:
    """Uzupełnij user_id tylko dla historycznych rekordów wskazanego loginu."""
    login_text = str(login or "").strip()
    uid = str(user_id or "").strip()
    if not login_text or not uid:
        return
    _backfill_feedback(login_text, uid)
    _backfill_leaves(login_text, uid)
    _backfill_attendance(login_text, uid)
    _backfill_profile_audit(login_text, uid)


def install() -> None:
    """Przed zmianą loginu zabezpiecz stare rekordy trwałym user_id."""
    global _INSTALLED
    from services import workforce_profile_service as workforce

    current = workforce.save_user
    if getattr(current, "_wm_identity_guard_v1", False):
        _INSTALLED = True
        return

    def save_user(user: dict, *args, **kwargs):
        incoming = dict(user or {})
        uid = str(incoming.get("user_id") or "").strip()
        existing = workforce.get_user(uid) if uid else None
        if existing is None:
            existing = workforce.get_user(str(incoming.get("login") or ""))

        if existing:
            old_login = str(existing.get("login") or "").strip()
            new_login = str(incoming.get("login") or old_login).strip()
            stable_uid = str(existing.get("user_id") or uid).strip()
            if old_login and new_login and _key(old_login) != _key(new_login):
                # Jeżeli nie da się zabezpieczyć historii, nie zmieniaj loginu.
                # To jest bezpieczniejsze niż utrata powiązania danych z pracownikiem.
                backfill_user_identity(old_login, stable_uid)

        return current(incoming, *args, **kwargs)

    save_user._wm_identity_guard_v1 = True
    save_user._wm_original = current
    workforce.save_user = save_user
    _INSTALLED = True


__all__ = ["install", "backfill_user_identity"]
