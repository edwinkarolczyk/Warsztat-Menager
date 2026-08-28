# version: 1.0
# Zmiany 1.0:
# - START wizyty nie czyści bieżącej listy zadań.
# - Zadania dodane przed startem (także jeszcze niezapisane osobno) przechodzą do rozpoczętej wizyty.
# - STOP prawidłowo otwartej wizyty pozostaje bez zmian: kopia zadań trafia do wizyty, a lista robocza jest czyszczona.
"""Ochrona listy zadań przy rozpoczęciu wizyty narzędzia."""

from __future__ import annotations

import sys
from copy import deepcopy
from typing import Any, Callable

import tkinter as tk
from tkinter import ttk


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}

_PRESAVE_TASKS: list[dict[str, Any]] | None = None
_RESTORE_AFTER_START = False


def _tool_module():
    return sys.modules.get("gui_narzedzia")


def _closure_value(func: Callable[..., Any], name: str):
    """Zwróć wartość wskazanej zmiennej z domknięcia funkcji edytora."""
    try:
        names = tuple(func.__code__.co_freevars)
        cells = tuple(func.__closure__ or ())
        if name not in names:
            return None
        return cells[names.index(name)].cell_contents
    except Exception:
        return None


def _tool_number(data: dict[str, Any]) -> str:
    raw = str(data.get("numer") or data.get("nr") or data.get("id") or "").strip()
    if raw.isdigit():
        return raw.zfill(3)
    return raw


def _open_visit_tokens(visits: Any) -> set[str]:
    if not isinstance(visits, list):
        return set()
    tokens: set[str] = set()
    for item in visits:
        if not isinstance(item, dict):
            continue
        start_ts = str(item.get("start_ts") or "").strip()
        if start_ts and not item.get("end_ts"):
            tokens.add(start_ts)
    return tokens


def _read_persisted_tool(number: str) -> dict[str, Any]:
    module = _tool_module()
    reader = getattr(module, "_read_tool", None) if module is not None else None
    if not callable(reader) or not number:
        return {}
    try:
        value = reader(number) or {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _restore_tasks_for_new_visit(data: dict[str, Any]) -> bool:
    """
    Bazowy edytor zeruje ``tasks`` przy START wizyty. Rozpoznaj wyłącznie
    rzeczywisty nowy START i przywróć listę sprzed kliknięcia Zapisz.
    """
    global _RESTORE_AFTER_START

    number = _tool_number(data)
    before = _read_persisted_tool(number)

    old_open = _open_visit_tokens(before.get("wizyty"))
    new_open = _open_visit_tokens(data.get("wizyty"))
    started_now = bool(new_open - old_open)
    if not started_now:
        return False

    source = _PRESAVE_TASKS
    if source is None:
        old_tasks = before.get("zadania")
        source = old_tasks if isinstance(old_tasks, list) else []

    data["zadania"] = deepcopy(source)
    _RESTORE_AFTER_START = True
    try:
        print(
            "[WM-DBG][TOOLS_VISIT] START wizyty zachował listę zadań: "
            f"{number} (zadań={len(source)})"
        )
    except Exception:
        pass
    return True


def _install_save_guard() -> None:
    """Podłącz zachowanie zadań tuż przed fizycznym zapisem JSON."""
    module = _tool_module()
    if module is None:
        return
    current = getattr(module, "_save_tool", None)
    if not callable(current):
        return
    if getattr(current, "_wm_visit_tasks_guard", False):
        return

    original = current

    def _save_tool_guarded(data):
        if isinstance(data, dict):
            _restore_tasks_for_new_visit(data)
        return original(data)

    _save_tool_guarded._wm_visit_tasks_guard = True
    _save_tool_guarded._wm_visit_tasks_original = original
    module._save_tool = _save_tool_guarded


def _is_tools_editor(widget: tk.Misc) -> bool:
    try:
        top = widget.winfo_toplevel()
        return str(top.title() or "").strip() in _EDITOR_TITLES
    except Exception:
        return False


def _wrap_editor_save(command: Callable[..., Any], button: ttk.Button):
    """Zachowaj pełną lokalną listę ``tasks`` zanim stary kod zdąży ją wyczyścić."""
    if getattr(command, "_wm_visit_tasks_command", False):
        return command

    tasks_ref = _closure_value(command, "tasks")
    tool_ref = _closure_value(command, "tool")
    start_ref = _closure_value(command, "start")

    def _wrapped(*args, **kwargs):
        global _PRESAVE_TASKS, _RESTORE_AFTER_START

        snapshot = deepcopy(tasks_ref) if isinstance(tasks_ref, list) else None
        _PRESAVE_TASKS = snapshot
        _RESTORE_AFTER_START = False
        _install_save_guard()

        try:
            return command(*args, **kwargs)
        finally:
            restore = _RESTORE_AFTER_START
            if restore and snapshot is not None:
                if isinstance(tasks_ref, list):
                    tasks_ref[:] = deepcopy(snapshot)
                if isinstance(tool_ref, dict):
                    tool_ref["zadania"] = deepcopy(snapshot)
                if isinstance(start_ref, dict):
                    start_ref["zadania"] = deepcopy(snapshot)
                try:
                    top = button.winfo_toplevel()
                    top.after(0, lambda: top.event_generate("<F5>"))
                except Exception:
                    pass

            _PRESAVE_TASKS = None
            _RESTORE_AFTER_START = False

    _wrapped._wm_visit_tasks_command = True
    _wrapped._wm_visit_tasks_original = command
    return _wrapped


def _install_button_hook() -> None:
    """Przechwyć wyłącznie przycisk Zapisz w głównym edytorze Narzędzi."""
    if getattr(ttk.Button, "_wm_visit_tasks_hook", False):
        return

    original_init = ttk.Button.__init__

    def _init(self, master=None, cnf=None, **kw):
        config = {} if cnf is None else dict(cnf)
        config.update(kw)
        command = config.get("command")
        text = str(config.get("text") or "").strip()

        original_init(self, master, **config)

        if text != "Zapisz" or not callable(command):
            return
        if not _is_tools_editor(self):
            return

        try:
            wrapped = _wrap_editor_save(command, self)
            self.configure(command=wrapped)
            self._wm_visit_tasks_wrapped = True
        except Exception:
            pass

    ttk.Button.__init__ = _init
    ttk.Button._wm_visit_tasks_hook = True
    ttk.Button._wm_visit_tasks_original_init = original_init


def install_visit_tasks_runtime() -> None:
    """Zainstaluj idempotentnie ochronę zadań START/STOP wizyty."""
    _install_button_hook()


__all__ = ["install_visit_tasks_runtime"]
