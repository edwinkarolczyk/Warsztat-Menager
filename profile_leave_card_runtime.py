# version: 1.0
"""Kompaktowy bilans urlopu w istniejącym Profilu bez zmiany jego układu."""
from __future__ import annotations

from datetime import date
from tkinter import ttk

from services.leave_balance_service import get_balance
from ui_context_help import add_help_button

_INSTALLED = False


def _fmt(value) -> str:
    try:
        number = float(value or 0)
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
    except Exception:
        return str(value or "0")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        import gui_profile_core as core
        cls = core.ProfileView
    except Exception:
        return
    if getattr(cls, "_wm_leave_compact_card", False):
        _INSTALLED = True
        return

    original = cls._render_simple_profile

    def wrapped(self, parent, *args, **kwargs):
        result = original(self, parent, *args, **kwargs)
        login = str(getattr(self, "login", "") or "").strip()
        if not login:
            return result
        try:
            bal = get_balance(login, date.today().year)
        except Exception:
            return result
        row = ttk.Frame(parent, style="WM.Container.TFrame")
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(
            row,
            text=(
                f"🏖 Urlop {bal.get('year')}: "
                f"🟡 zaległy {_fmt(bal.get('carryover'))}  |  "
                f"🔵 wykorzystano {_fmt(bal.get('used'))}  |  "
                f"🟠 oczekuje {_fmt(bal.get('pending'))}  |  "
                f"🟢 pozostało {_fmt(bal.get('remaining'))}"
            ),
            style="WM.Muted.TLabel",
        ).pack(side="left")
        add_help_button(
            row,
            "Niewykorzystany urlop przechodzi na kolejny rok. WM wykorzystuje najpierw najstarszy urlop zaległy, a dopiero potem bieżący.",
        ).pack(side="left", padx=(6, 0))
        return result

    cls._render_simple_profile = wrapped
    cls._wm_leave_compact_card = True
    _INSTALLED = True


__all__ = ["install"]
