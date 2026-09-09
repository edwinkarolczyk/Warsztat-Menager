# version: 1.0
"""Drobne poprawki UI urlopów bez przebudowy istniejących okien."""
from __future__ import annotations

from tkinter import messagebox

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        import gui_profile_calendar as calendar_ui
        from services.leave_workflow_service import approve_request as real_approve
    except Exception:
        return

    if getattr(calendar_ui, "_wm_leave_balance_override", False):
        _INSTALLED = True
        return

    def approve_with_explicit_override(request_id: str, actor_login: str):
        try:
            return real_approve(request_id, actor_login, allow_over_balance=False)
        except ValueError as exc:
            text = str(exc)
            if "przekracza dostępny urlop" not in text:
                raise
            if not messagebox.askyesno(
                "Przekroczenie salda urlopu",
                f"{text}\n\nCzy mimo to zaakceptować wniosek?",
            ):
                raise ValueError("Akceptacja anulowana przez brygadzistę.")
            return real_approve(request_id, actor_login, allow_over_balance=True)

    # _open_requests_dialog odczytuje tę nazwę globalną dopiero przy kliknięciu.
    calendar_ui.approve_request = approve_with_explicit_override
    calendar_ui._wm_leave_balance_override = True
    _INSTALLED = True


__all__ = ["install"]
