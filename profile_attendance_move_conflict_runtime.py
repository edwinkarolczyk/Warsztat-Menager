# version: 1.0
"""Naprawa konfliktu przy przenoszeniu korekty Obecności między zmianami.

Dotyczy wyłącznie edytora:
Profil pracownika -> Obecność -> Edycja zaznaczonego dnia.

Jeżeli brygadzista usuwa blokującą nieobecność z docelowej zmiany, runtime
pozwala usunąć pozostały po niej pusty rekord techniczny przed przeniesieniem
realnego wpisu z drugiej zmiany. Rekord z faktyczną aktywnością nadal blokuje
przeniesienie, więc ochrona przed prawdziwym duplikatem pozostaje bez zmian.
"""
from __future__ import annotations

from typing import Any

_INSTALLED = False


def _has_overtime(rec: dict[str, Any]) -> bool:
    overtime = rec.get("overtime")
    if not isinstance(overtime, dict):
        return False
    try:
        hours = float(overtime.get("hours") or 0.0)
    except Exception:
        hours = 0.0
    return bool(hours > 0 or str(overtime.get("status") or "").strip())


def _has_login(rec: dict[str, Any]) -> bool:
    return any(
        str(rec.get(key) or "").strip()
        for key in ("first_login_ts", "logged_ts", "last_login_ts")
    )


def _day_value(rec: dict[str, Any]) -> float:
    try:
        return float(rec.get("day_value") or 0.0)
    except Exception:
        return 0.0


def _source_has_movable_activity(rec: dict[str, Any], attendance_service) -> bool:
    status = str(rec.get("status") or "").strip()
    return bool(
        _has_login(rec)
        or _day_value(rec) > 0
        or _has_overtime(rec)
        or status
        in {
            attendance_service.STATUS_PRESENT,
            attendance_service.STATUS_PENDING_LATE,
            attendance_service.STATUS_SATURDAY,
        }
    )


def _is_residual_absence_target(rec: dict[str, Any], attendance_service) -> bool:
    """Tylko pusty ślad po zdjętej nieobecności może zostać automatycznie usunięty."""
    if str(rec.get("status") or "").strip() != attendance_service.STATUS_MISSING:
        return False
    if str(rec.get("reason") or "").strip():
        return False
    if _has_login(rec) or _day_value(rec) > 0 or _has_overtime(rec):
        return False
    return True


def _clear_residual_target_before_move(
    attendance_service,
    *,
    date_ymd: str,
    target_slot: str,
    source_slot: str,
    login: str,
    actor: str,
    note: str,
) -> bool:
    target_slot = str(target_slot or "").strip().upper()
    source_slot = str(source_slot or "").strip().upper()
    if (
        target_slot == source_slot
        or target_slot not in attendance_service.VALID_SLOTS
        or source_slot not in attendance_service.VALID_SLOTS
    ):
        return False

    login_n = str(login or "").strip().casefold()
    doc = attendance_service._read(attendance_service.data_path(), {})
    day = doc.get(str(date_ymd), {}) if isinstance(doc, dict) else {}
    if not isinstance(day, dict):
        return False

    target_map = day.get(target_slot)
    source_map = day.get(source_slot)
    if not isinstance(target_map, dict) or not isinstance(source_map, dict):
        return False

    target_key, target_rec = attendance_service._matching_record(target_map, login_n)
    _source_key, source_rec = attendance_service._matching_record(source_map, login_n)
    if not isinstance(target_rec, dict) or target_key is None:
        return False
    if not isinstance(source_rec, dict):
        return False

    # Bez realnego wpisu do przeniesienia niczego na zmianie docelowej nie usuwamy.
    if not _source_has_movable_activity(source_rec, attendance_service):
        return False

    # Prawdziwy wpis docelowy nadal ma blokować operację w set_manual_day().
    if not _is_residual_absence_target(target_rec, attendance_service):
        return False

    before = dict(target_rec)
    target_map.pop(target_key, None)
    attendance_service._write(attendance_service.data_path(), doc)
    attendance_service._audit(
        action="manual_move_clear_residual_absence",
        login=login_n,
        date_ymd=str(date_ymd),
        slot=target_slot,
        actor=str(actor or ""),
        before=before,
        after={},
        note=(
            f"Usunięto pusty rekord {target_slot} po zdjęciu nieobecności "
            f"przed przeniesieniem wpisu {source_slot} -> {target_slot}. "
            f"{str(note or '').strip()}"
        ).strip(),
    )
    return True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        import profile_foreman_workspace_runtime as workspace
    except Exception:
        return

    current = getattr(workspace, "_save_attendance_edit", None)
    if current is None:
        return
    if getattr(current, "_wm_move_residual_fix_v1", False):
        _INSTALLED = True
        return

    original = current

    def wrapped(
        login: str,
        payload: dict[str, Any],
        *,
        source_slot: str,
        original_first_login: str,
        actor: str,
        note: str,
    ) -> None:
        attendance_service = workspace.attendance_service
        original_set_manual_day = attendance_service.set_manual_day

        def set_manual_day_proxy(
            date_ymd,
            slot,
            login_value,
            value,
            actor_value,
            note_value="",
            **kwargs,
        ):
            source = str(kwargs.get("original_slot") or slot).strip().upper()
            target = str(slot or "").strip().upper()
            _clear_residual_target_before_move(
                attendance_service,
                date_ymd=str(date_ymd),
                target_slot=target,
                source_slot=source,
                login=str(login_value or ""),
                actor=str(actor_value or ""),
                note=str(note_value or ""),
            )
            return original_set_manual_day(
                date_ymd,
                slot,
                login_value,
                value,
                actor_value,
                note_value,
                **kwargs,
            )

        attendance_service.set_manual_day = set_manual_day_proxy
        try:
            return original(
                login,
                payload,
                source_slot=source_slot,
                original_first_login=original_first_login,
                actor=actor,
                note=note,
            )
        finally:
            attendance_service.set_manual_day = original_set_manual_day

    setattr(wrapped, "_wm_move_residual_fix_v1", True)
    setattr(wrapped, "_wm_move_residual_fix_original", original)
    workspace._save_attendance_edit = wrapped
    _INSTALLED = True


__all__ = [
    "install",
    "_clear_residual_target_before_move",
    "_is_residual_absence_target",
]
