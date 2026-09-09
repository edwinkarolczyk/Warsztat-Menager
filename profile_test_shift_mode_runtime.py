# version: 1.1
"""Dopina do TESTOWEJ tryb zmiany bez gubienia istniejących nagłówków."""
from __future__ import annotations

from datetime import date
from tkinter import ttk
from typing import Any

from config_manager import ConfigManager
from grafiki.shifts_schedule import _normalize_mode
from services import workforce_profile_service

_INSTALLED = False
_ABSENCE_CODES = {"UR", "?UR", "L4", "NN", "ŚW", "UB", "UŻ"}


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _configured_shift_mode(login: str) -> str:
    login = str(login or "").strip()
    if not login:
        return "—"

    user = workforce_profile_service.get_user(login) or {}
    user_id = str(user.get("user_id") or user.get("id") or "").strip()

    try:
        raw_modes = ConfigManager().get("shifts.modes", {})
    except Exception:
        raw_modes = {}
    modes = raw_modes if isinstance(raw_modes, dict) else {}
    folded_modes = {_key(key): value for key, value in modes.items()}

    raw_mode = (
        modes.get(user_id)
        or modes.get(login)
        or folded_modes.get(_key(user_id))
        or folded_modes.get(_key(login))
        or user.get("tryb_zmian")
        or user.get("zmiana_plan")
        or user.get("shift_mode")
        or "111"
    )
    return _normalize_mode(raw_mode)


def _today_absence_by_login() -> dict[str, str]:
    """Zwróć wyłącznie stan nieobecności na dzisiaj, nie saldo urlopu."""
    try:
        import profile_calendar_team_runtime as team_runtime

        rows = team_runtime._team_day_rows(date.today())
    except Exception:
        return {}

    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        login = _key(row.get("login"))
        if not login:
            continue
        code = str(row.get("status_code") or "").strip().upper()
        out[login] = code if code in _ABSENCE_CODES else "—"
    return out


def _walk(widget):
    out = []
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        out.append(child)
        out.extend(_walk(child))
    return out


def _decorate_shift_mode_column(panel) -> None:
    parent = getattr(panel, "_tabs", {}).get("TESTOWA")
    if parent is None:
        return

    absences = _today_absence_by_login()

    for tree in _walk(parent):
        if not isinstance(tree, ttk.Treeview):
            continue
        try:
            columns = list(tree.cget("columns") or ())
        except Exception:
            continue
        if "work" not in columns or "login" not in columns:
            continue
        if "shift_mode" in columns:
            continue

        # Tkinter potrafi zgubić tekst nagłówków po zmianie listy columns.
        # Zachowujemy je przed dopięciem nowej kolumny i odtwarzamy po configure().
        headings: dict[str, str] = {}
        for column in columns:
            try:
                headings[column] = str(tree.heading(column, "text") or "")
            except Exception:
                headings[column] = ""

        new_columns = list(columns)
        new_columns.insert(new_columns.index("work") + 1, "shift_mode")
        try:
            tree.configure(columns=new_columns, displaycolumns=new_columns)
            for column in columns:
                tree.heading(column, text=headings.get(column, ""))
            if "leave" in columns:
                tree.heading("leave", text="Nieobecność")
            tree.heading("shift_mode", text="Tryb zmiany")
            tree.column(
                "shift_mode",
                width=82,
                minwidth=70,
                anchor="center",
                stretch=False,
            )
        except Exception:
            continue

        login_index = columns.index("login")
        leave_index = columns.index("leave") if "leave" in columns else -1
        insert_index = new_columns.index("shift_mode")
        for iid in tree.get_children(""):
            try:
                values = list(tree.item(iid, "values") or ())
                if len(values) != len(columns):
                    continue
                login = str(values[login_index] or "").strip()
                if leave_index >= 0:
                    values[leave_index] = absences.get(_key(login), "—")
                values.insert(insert_index, _configured_shift_mode(login))
                tree.item(iid, values=values)
            except Exception:
                continue


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import profile_foreman_test_workspace_runtime as test_runtime

    if getattr(test_runtime, "_wm_shift_mode_column_v1", False):
        _INSTALLED = True
        return

    original_render = test_runtime._render_test_workspace

    def render(panel) -> None:
        original_render(panel)
        _decorate_shift_mode_column(panel)

    test_runtime._render_test_workspace = render
    test_runtime._wm_shift_mode_column_v1 = True
    _INSTALLED = True


__all__ = ["install"]
