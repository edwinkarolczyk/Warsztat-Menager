# version: 1.1
"""Ujednolica listę trybów grafiku w dodawaniu i edycji profilu pracownika."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from ui_context_help import add_help_button

_INSTALLED = False

SHIFT_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("111", "111 — I / I / I (stała I zmiana)"),
    ("112", "112 — I / I / II (cykl 3 tygodnie)"),
    ("222", "222 — II / II / II (stała II zmiana)"),
    ("121", "121 — I / II / I (cykl 3 tygodnie)"),
    ("212", "212 — II / I / II (cykl 3 tygodnie)"),
)

_MODE_TO_LABEL = dict(SHIFT_MODE_OPTIONS)
_LABEL_TO_MODE = {label: mode for mode, label in SHIFT_MODE_OPTIONS}
_MODE_CODES = tuple(mode for mode, _label in SHIFT_MODE_OPTIONS)


def _mode_code(value: Any) -> str:
    """Zamień kod lub etykietę UI na kanoniczny kod grafiku."""
    text = str(value or "").strip()
    if text in _MODE_CODES:
        return text
    if text in _LABEL_TO_MODE:
        return _LABEL_TO_MODE[text]
    prefix = text.split("—", 1)[0].strip()
    if prefix in _MODE_CODES:
        return prefix
    return text


def _mode_label(value: Any) -> str:
    """Zwróć czytelną etykietę dla kodu grafiku."""
    code = _mode_code(value)
    return _MODE_TO_LABEL.get(code, str(value or "").strip())


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


def _all_toplevels(root) -> set[tk.Toplevel]:
    return {widget for widget in _walk(root) if isinstance(widget, tk.Toplevel)}


def _find_tab(win: tk.Toplevel, title: str):
    notebook = next((w for w in _walk(win) if isinstance(w, ttk.Notebook)), None)
    if notebook is None:
        return None
    try:
        for tab_id in notebook.tabs():
            if str(notebook.tab(tab_id, "text")) == title:
                return win.nametowidget(tab_id)
    except Exception:
        return None
    return None


def _fit_employee_window(win: tk.Toplevel) -> None:
    """Daj Profilowi pracownika więcej wysokości, nie wychodząc poza ekran."""
    try:
        win.update_idletasks()
        screen_w = max(1, int(win.winfo_screenwidth()))
        screen_h = max(1, int(win.winfo_screenheight()))

        width = min(980, max(760, screen_w - 80))
        height = min(900, max(760, screen_h - 140))
        height = min(height, max(650, screen_h - 80))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.minsize(min(900, width), min(650, height))
    except Exception:
        try:
            win.geometry("980x760")
        except Exception:
            pass


def _replace_mode_help(schedule) -> None:
    for widget in list(schedule.winfo_children()):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == 0 and int(info.get("column", -1)) == 2:
                widget.destroy()
        except Exception:
            continue
    add_help_button(
        schedule,
        "Wybierz wzorzec grafiku: 111, 112, 222, 121 albo 212. Cyfry oznaczają kolejne tygodnie: I lub II zmianę; po trzecim tygodniu cykl zaczyna się od początku.",
        row=0,
        column=2,
        padx=(6, 0),
        sticky="w",
    )


def _decorate_employee_window(win: tk.Toplevel) -> None:
    _fit_employee_window(win)
    if getattr(win, "_wm_shift_modes_synced_v1", False):
        return
    schedule = _find_tab(win, "Grafik")
    if schedule is None:
        return

    combo = next((w for w in _walk(schedule) if isinstance(w, ttk.Combobox)), None)
    save_button = next(
        (
            w
            for w in _walk(schedule)
            if isinstance(w, ttk.Button) and str(w.cget("text")) == "Zapisz grafik"
        ),
        None,
    )
    if combo is None or save_button is None:
        return

    try:
        var_name = str(combo.cget("textvariable") or "")
        if not var_name:
            return
        current = win.getvar(var_name)
        combo.configure(values=tuple(label for _mode, label in SHIFT_MODE_OPTIONS), state="readonly")
        win.setvar(var_name, _mode_label(current))
    except Exception:
        return

    original_command = str(save_button.cget("command") or "")
    if not original_command:
        return

    def save_with_code() -> None:
        selected = win.getvar(var_name)
        code = _mode_code(selected)
        win.setvar(var_name, code)
        try:
            save_button.tk.call(original_command)
        finally:
            try:
                if win.winfo_exists():
                    win.setvar(var_name, _mode_label(code))
            except Exception:
                pass

    save_button.configure(command=save_with_code)
    _replace_mode_help(schedule)
    win._wm_shift_modes_synced_v1 = True


def _patch_add_profile_dialog() -> None:
    """Nowy profil i edycja pracownika korzystają z dokładnie tej samej listy."""
    try:
        import ustawienia_uzytkownicy as profiles
    except Exception:
        return
    profiles.ProfileEditDialog.SHIFT_MODES = list(SHIFT_MODE_OPTIONS)


def install() -> None:
    global _INSTALLED
    _patch_add_profile_dialog()

    try:
        import profile_foreman_edit_runtime as edit_runtime
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] shift mode sync import failed: {exc!r}")
        return

    if getattr(edit_runtime, "_wm_shift_mode_sync_v1", False):
        _INSTALLED = True
        return

    original_open = edit_runtime.open_employee_editor

    def open_employee_editor(owner, login: str, *args, **kwargs):
        try:
            root = owner.winfo_toplevel()
            before = _all_toplevels(root)
        except Exception:
            root = None
            before = set()

        result = original_open(owner, login, *args, **kwargs)

        if root is not None:
            try:
                root.update_idletasks()
                created = _all_toplevels(root) - before
                candidates = created or _all_toplevels(root)
                for win in candidates:
                    try:
                        if str(win.title()).startswith("Profil pracownika —"):
                            _decorate_employee_window(win)
                    except Exception:
                        continue
            except Exception:
                pass
        return result

    edit_runtime.open_employee_editor = open_employee_editor
    edit_runtime._wm_shift_mode_sync_v1 = True
    _INSTALLED = True


__all__ = ["SHIFT_MODE_OPTIONS", "_mode_code", "_mode_label", "install"]
