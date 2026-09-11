# version: 1.3
"""Ujednolica listę trybów grafiku w dodawaniu i edycji profilu pracownika."""
from __future__ import annotations

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk
from typing import Any

from calendar_ui_runtime import open_date_picker
from grafiki import shifts_schedule
from ui_context_help import add_help_button

_INSTALLED = False


def _build_mode_label(mode: Any) -> str:
    """Zbuduj etykietę UI bez utrzymywania osobnej listy kodów grafiku."""
    code = str(mode or "").strip()
    sequence = tuple(
        "I" if digit == "1" else "II" if digit == "2" else digit
        for digit in code
    )
    if not sequence:
        return code
    if len(set(sequence)) == 1:
        suffix = f"(stała {sequence[0]} zmiana)"
    else:
        suffix = f"(cykl {len(sequence)} tygodnie)"
    return f"{code} — {' / '.join(sequence)} {suffix}"


def _build_shift_mode_options() -> tuple[tuple[str, str], ...]:
    """Zwróć opcje UI bezpośrednio z kanonicznego ``shifts_schedule.TRYBY``."""
    return tuple(
        (str(mode), _build_mode_label(mode))
        for mode in shifts_schedule.TRYBY
    )


SHIFT_MODE_OPTIONS: tuple[tuple[str, str], ...] = _build_shift_mode_options()

_MODE_TO_LABEL = dict(SHIFT_MODE_OPTIONS)
_LABEL_TO_MODE = {label: mode for mode, label in SHIFT_MODE_OPTIONS}
_MODE_CODES = tuple(mode for mode, _label in SHIFT_MODE_OPTIONS)


def _mode_code(value: Any) -> str:
    """Zamień kod, etykietę lub stary alias na kanoniczny kod grafiku."""
    text = str(value or "").strip()
    if text in _MODE_CODES:
        return text
    if text in _LABEL_TO_MODE:
        return _LABEL_TO_MODE[text]
    prefix = text.split("—", 1)[0].strip()
    if prefix in _MODE_CODES:
        return prefix
    aliases = getattr(shifts_schedule, "_LEGACY_MODE_ALIASES", {})
    normalized = aliases.get(prefix.upper(), prefix)
    if normalized in _MODE_CODES:
        return normalized
    return text


def _mode_label(value: Any) -> str:
    """Zwróć czytelną etykietę dla kodu grafiku."""
    code = _mode_code(value)
    return _MODE_TO_LABEL.get(code, str(value or "").strip())


def _anchor_monday_iso(value: Any) -> str:
    """Zwróć poniedziałek tygodnia wskazanej daty w formacie ISO."""
    if isinstance(value, date):
        picked = value
    else:
        try:
            picked = date.fromisoformat(str(value or "").strip()[:10])
        except Exception:
            picked = date.today()
    return (picked - timedelta(days=picked.weekday())).isoformat()


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
    available = ", ".join(_MODE_CODES)
    add_help_button(
        schedule,
        f"Wybierz wzorzec grafiku: {available}. 12 oznacza I → II → I → II, a 21 oznacza II → I → II → I; cykl powtarza się co dwa tygodnie.",
        row=0,
        column=2,
        padx=(6, 0),
        sticky="w",
    )


def _install_anchor_calendar(schedule, win: tk.Toplevel) -> None:
    """Dodaj wspólny kalendarz do pola Tydzień bazowy w edytorze pracownika."""
    if getattr(schedule, "_wm_anchor_calendar_v1", False):
        return

    anchor_entry = None
    for widget in schedule.winfo_children():
        if not isinstance(widget, ttk.Entry):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == 1 and int(info.get("column", -1)) == 1:
                anchor_entry = widget
                break
        except Exception:
            continue
    if anchor_entry is None:
        return

    var_name = str(anchor_entry.cget("textvariable") or "")
    if not var_name:
        return

    try:
        anchor_entry.configure(state="readonly")
    except Exception:
        pass

    def _pick_anchor() -> None:
        try:
            initial = date.fromisoformat(str(win.getvar(var_name) or "")[:10])
        except Exception:
            initial = date.today()

        def _selected(picked: date) -> None:
            win.setvar(var_name, _anchor_monday_iso(picked))

        open_date_picker(
            win,
            initial=initial,
            on_select=_selected,
            title="Tydzień bazowy — tydzień 1",
        )

    try:
        anchor_entry.bind("<Button-1>", lambda _event: _pick_anchor(), add="+")
    except Exception:
        pass

    ttk.Button(schedule, text="📅", width=3, command=_pick_anchor).grid(
        row=1,
        column=3,
        padx=(4, 0),
        sticky="w",
    )
    schedule._wm_anchor_calendar_v1 = True


def _decorate_employee_window(win: tk.Toplevel) -> None:
    _fit_employee_window(win)
    if getattr(win, "_wm_shift_modes_synced_v1", False):
        return
    schedule = _find_tab(win, "Grafik")
    if schedule is None:
        return

    _install_anchor_calendar(schedule, win)

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
    profiles.ProfileEditDialog.LEGACY_SHIFT_ALIASES = dict(
        getattr(shifts_schedule, "_LEGACY_MODE_ALIASES", {})
    )


def _patch_legacy_users_panel() -> None:
    """Starszy panel Użytkowników także dostaje opcje z kanonicznego Grafiku."""
    try:
        import gui_uzytkownicy as users_ui
    except Exception:
        return

    users_ui.SHIFT_MODE_CHOICES = {
        label: mode for mode, label in SHIFT_MODE_OPTIONS
    }

    def label_from_code(code: str | None) -> str:
        normalized = _mode_code(code)
        if normalized in _MODE_TO_LABEL:
            return _MODE_TO_LABEL[normalized]
        if _MODE_CODES:
            return _MODE_TO_LABEL[_MODE_CODES[0]]
        return ""

    users_ui._shift_mode_label_from_code = label_from_code


def install() -> None:
    global _INSTALLED
    _patch_add_profile_dialog()
    _patch_legacy_users_panel()

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


__all__ = [
    "SHIFT_MODE_OPTIONS",
    "_mode_code",
    "_mode_label",
    "_anchor_monday_iso",
    "install",
]
