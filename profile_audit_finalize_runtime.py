# version: 1.1
"""Końcowa polityka audytu Profili i ostatnie uporządkowanie panelu Brygadzisty."""
from __future__ import annotations

from datetime import datetime


def install() -> None:
    # Ta warstwa jest instalowana jako ostatnia w Profili, więc tutaj montujemy
    # również końcowy układ Administracji po wszystkich wcześniejszych runtime'ach.
    try:
        from profile_foreman_admin_group_runtime import install as install_admin_group
        install_admin_group()
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] admin group runtime install failed: {exc!r}")

    import profile_foreman_edit_runtime as edit_runtime
    from services import workforce_profile_service

    if getattr(edit_runtime, "_wm_full_audit_history", False):
        return

    def _audit(login: str, action: str, actor: str, *, before=None, after=None, note: str = "") -> None:
        rows = edit_runtime._read_json(edit_runtime._audit_path(), [])
        if not isinstance(rows, list):
            rows = []
        user = workforce_profile_service.get_user(login) or {}
        rows.append({
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "user_id": str(user.get("user_id") or ""),
            "login": str(login or ""),
            "action": str(action or ""),
            "actor": str(actor or ""),
            "before": before,
            "after": after,
            "note": str(note or "").strip(),
        })
        edit_runtime._write_json(edit_runtime._audit_path(), rows)

    edit_runtime._audit = _audit
    edit_runtime._wm_full_audit_history = True


__all__ = ["install"]
