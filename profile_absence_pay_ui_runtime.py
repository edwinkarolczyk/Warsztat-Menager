# version: 1.0
"""Minimalne UI rodzajów płatnych dni w Profilach.

Nie tworzy nowej zakładki. Dokłada dwa przyciski do istniejącego bloku
L4/NN w edytorze pracownika oraz czytelne oznaczenia w kalendarzu.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ui_context_help import add_help_button

_INSTALLED = False


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


def _find_tab(notebook: ttk.Notebook, text: str):
    try:
        for tab_id in notebook.tabs():
            if str(notebook.tab(tab_id, "text")) == text:
                return notebook.nametowidget(tab_id)
    except Exception:
        pass
    return None


def _entry_at_row(frame, row: int):
    for child in frame.winfo_children():
        if not isinstance(child, ttk.Entry):
            continue
        try:
            if int(child.grid_info().get("row", -1)) == row:
                return child
        except Exception:
            continue
    return None


def _actions_at_row(frame, row: int):
    for child in frame.winfo_children():
        if not isinstance(child, ttk.Frame):
            continue
        try:
            if int(child.grid_info().get("row", -1)) == row:
                return child
        except Exception:
            continue
    return None


def _decorate_employee_window(owner, login: str, win: tk.Toplevel, on_saved=None) -> None:
    notebook = next((child for child in win.winfo_children() if isinstance(child, ttk.Notebook)), None)
    if notebook is None:
        return
    leaves = _find_tab(notebook, "Urlopy")
    if leaves is None or getattr(leaves, "_wm_pay_absence_ui", False):
        return

    start_entry = _entry_at_row(leaves, 6)
    end_entry = _entry_at_row(leaves, 7)
    note_entry = _entry_at_row(leaves, 8)
    actions = _actions_at_row(leaves, 9)
    if start_entry is None or end_entry is None or actions is None:
        return

    def add_kind(kind: str) -> None:
        start = str(start_entry.get() or "").strip()
        end = str(end_entry.get() or "").strip()
        note = str(note_entry.get() or "").strip() if note_entry is not None else ""
        try:
            from services import leave_workflow_service as lw
            days = lw.dates_from_range(start, end, include_sundays=True)
            if kind == "ŚW":
                count = lw.add_force_majeure(login, days, str(getattr(owner, "login", "") or ""), note)
                label = "Siła wyższa 50%"
            else:
                count = lw.add_unpaid_leave(login, days, str(getattr(owner, "login", "") or ""), note)
                label = "Urlop bezpłatny 0%"
        except Exception:
            # Edytor ma własny, poprawny resolver aktywnego Brygadzisty.
            try:
                import profile_foreman_edit_runtime as edit_runtime
                from services import leave_workflow_service as lw
                actor = edit_runtime._actor_or_error(owner)
                days = lw.dates_from_range(start, end, include_sundays=True)
                if kind == "ŚW":
                    count = lw.add_force_majeure(login, days, actor, note)
                    label = "Siła wyższa 50%"
                else:
                    count = lw.add_unpaid_leave(login, days, actor, note)
                    label = "Urlop bezpłatny 0%"
            except Exception as exc:
                messagebox.showerror("Nieobecność", f"Nie udało się zapisać:\n{exc}", parent=win)
                return
        messagebox.showinfo("Nieobecność", f"Zapisano: {label} — {count} dni.", parent=win)
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass

    ttk.Button(actions, text="Siła wyższa 50%", command=lambda: add_kind("ŚW")).pack(side="left", padx=(6, 0))
    add_help_button(
        actions,
        "Zapisuje nieobecność „Siła wyższa” z domyślną płatnością 50%. Procent jest zapisany jako dane źródłowe pod przyszły kalkulator sugerowanej wypłaty.",
    ).pack(side="left", padx=(4, 0))
    ttk.Button(actions, text="Bezpłatny 0%", command=lambda: add_kind("UB")).pack(side="left", padx=(6, 0))

    info = ttk.Label(
        leaves,
        text="Płatność domyślna: UR 100%  •  UŻ 100%  •  L4 80%  •  ŚW 50%  •  NN 0%  •  UB 0%",
    )
    info.grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0))
    add_help_button(
        leaves,
        "To są wartości domyślne zapisane przy rodzaju dnia. Nie są jeszcze naliczaniem wynagrodzenia i później będzie można je konfigurować.",
        row=11,
        column=0,
        sticky="w",
        pady=(4, 0),
    )
    leaves._wm_pay_absence_ui = True


def _patch_employee_editor() -> None:
    import profile_foreman_edit_runtime as edit_runtime

    if getattr(edit_runtime, "_wm_pay_absence_ui", False):
        return
    original = edit_runtime.open_employee_editor

    def open_employee_editor(owner, login: str, *, initial_tab: str = "Dane", on_saved=None) -> None:
        root = owner.winfo_toplevel()
        before = set(root.winfo_children())
        original(owner, login, initial_tab=initial_tab, on_saved=on_saved)
        after = [child for child in root.winfo_children() if child not in before and isinstance(child, tk.Toplevel)]
        if after:
            _decorate_employee_window(owner, login, after[-1], on_saved=on_saved)

    edit_runtime.open_employee_editor = open_employee_editor
    edit_runtime._wm_pay_absence_ui = True


def _patch_calendar_marks() -> None:
    import gui_profile_calendar as calendar_ui

    cls = calendar_ui.ProfileCalendarPanel
    if getattr(cls, "_wm_pay_day_marks", False):
        return
    original = cls._day_marks

    def _day_marks(self, snapshot):
        marks = original(self, snapshot)
        for row in snapshot.get("leaves") or []:
            day = str(row.get("date") or "")[:10]
            kind = str(row.get("type") or "").strip().casefold()
            if kind in {"sila_wyzsza", "siła_wyższa", "force_majeure"}:
                marks[day] = {"label": "ŚW 50%", "bg": calendar_ui.WM_WARN}
            elif kind in {"urlop_bezplatny", "urlop_bezpłatny", "unpaid"}:
                marks[day] = {"label": "UB 0%", "bg": calendar_ui.WM_BAD}
        return marks

    cls._day_marks = _day_marks
    cls._wm_pay_day_marks = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_employee_editor()
    _patch_calendar_marks()
    _INSTALLED = True


__all__ = ["install"]
