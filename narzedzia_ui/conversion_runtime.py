# version: 1.0
# Moduł: narzedzia_ui.conversion_runtime
# 1.0:
# - Konwersja NN -> SN pokazuje tylko checkbox „Przenieś do SN przy zapisie”.
# - Ukryto wybór „Zadania po konwersji”.
# - Konwersja zawsze zachowuje bieżącą listę zadań (tryb keep).

from __future__ import annotations

from typing import Any, Callable
import tkinter as tk
from tkinter import ttk


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}


def _closure_value(func: Callable[..., Any], name: str):
    try:
        names = tuple(func.__code__.co_freevars)
        cells = tuple(func.__closure__ or ())
        if name not in names:
            return None
        return cells[names.index(name)].cell_contents
    except Exception:
        return None


def _is_tools_editor(widget: tk.Misc) -> bool:
    try:
        top = widget.winfo_toplevel()
        return str(top.title() or "").strip() in _EDITOR_TITLES
    except Exception:
        return False


def _walk(widget: tk.Misc):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _walk(child)


def _hide_conversion_task_mode(dlg: tk.Toplevel) -> None:
    """Zostaw w wierszu konwersji tylko checkbox przeniesienia NN -> SN."""
    try:
        if str(dlg.title() or "").strip() not in _EDITOR_TITLES:
            return
    except Exception:
        return

    for widget in _walk(dlg):
        if not isinstance(widget, ttk.Checkbutton):
            continue
        try:
            if str(widget.cget("text") or "").strip() != "Przenieś do SN przy zapisie":
                continue
        except Exception:
            continue

        frame = getattr(widget, "master", None)
        if frame is None:
            return
        try:
            siblings = list(frame.winfo_children())
        except Exception:
            siblings = []

        for sibling in siblings:
            if sibling is widget:
                continue
            hide = isinstance(sibling, ttk.Combobox)
            if isinstance(sibling, ttk.Label):
                try:
                    text = str(sibling.cget("text") or "").strip()
                except Exception:
                    text = ""
                hide = hide or text.startswith("Zadania po konwersji")
            if not hide:
                continue
            try:
                sibling.pack_forget()
            except Exception:
                try:
                    sibling.grid_remove()
                except Exception:
                    pass
        return


def _install_save_keep_mode() -> None:
    """Wymuś tryb keep zanim stary kod konwersji rozpocznie zapis."""
    if getattr(ttk.Button, "_wm_tools_conversion_keep_hook", False):
        return

    original_init = ttk.Button.__init__

    def _init(self, master=None, cnf=None, **kw):
        config = {} if cnf is None else dict(cnf)
        config.update(kw)

        command = config.get("command")
        text = str(config.get("text") or "").strip()

        if text == "Zapisz" and callable(command):
            convert_tasks_var = _closure_value(command, "convert_tasks_var")

            if convert_tasks_var is not None:
                original_command = command

                def _keep_tasks_then_save(*args, **kwargs):
                    try:
                        convert_tasks_var.set("keep")
                    except Exception:
                        pass
                    return original_command(*args, **kwargs)

                _keep_tasks_then_save._wm_tools_conversion_keep = True
                _keep_tasks_then_save._wm_tools_conversion_original = original_command
                config["command"] = _keep_tasks_then_save

        original_init(self, master, **config)

    ttk.Button.__init__ = _init
    ttk.Button._wm_tools_conversion_keep_hook = True
    ttk.Button._wm_tools_conversion_keep_original_init = original_init


def _install_editor_ui_hook() -> None:
    if getattr(tk.Toplevel, "_wm_tools_conversion_ui_hook", False):
        return

    original_init = tk.Toplevel.__init__

    def _init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        def _decorate(attempt: int = 0) -> None:
            try:
                if not self.winfo_exists():
                    return
                title = str(self.title() or "").strip()
            except Exception:
                return
            if title not in _EDITOR_TITLES:
                return
            _hide_conversion_task_mode(self)
            if attempt < 3:
                try:
                    self.after(100, lambda: _decorate(attempt + 1))
                except Exception:
                    pass

        try:
            self.after(120, _decorate)
        except Exception:
            pass

    tk.Toplevel.__init__ = _init
    tk.Toplevel._wm_tools_conversion_ui_hook = True
    tk.Toplevel._wm_tools_conversion_ui_original_init = original_init


def install_tools_conversion_runtime() -> None:
    _install_save_keep_mode()
    _install_editor_ui_hook()


__all__ = ["install_tools_conversion_runtime"]
