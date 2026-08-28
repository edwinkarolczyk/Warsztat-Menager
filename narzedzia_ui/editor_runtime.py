# version: 1.0
# Zmiany 1.0:
# - Edytor NN/SN nie pokazuje starego automatycznego pytania o przeniesienie do SN.
# - Numer istniejącego narzędzia pozostaje stały także przy NN -> SN.
# - Anuluj, Esc, Ctrl+W i X ostrzegają o niezapisanych zmianach.
# - Powrót do statusu bazowego bez otwartej wizyty nie tworzy sztucznej wizyty 0 min.
"""Drobne poprawki zachowania głównego edytora Narzędzi bez zmiany modelu danych."""

from __future__ import annotations

import sys
import weakref
from copy import deepcopy
from typing import Any

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}
_EDITORS: "weakref.WeakSet[tk.Toplevel]" = weakref.WeakSet()
_SAVE_COUNTER = 0


def _alive(widget: tk.Misc | None) -> bool:
    try:
        return widget is not None and bool(int(widget.winfo_exists()))
    except Exception:
        return False


def _tool_module():
    return sys.modules.get("gui_narzedzia")


def _walk(widget: tk.Misc):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _walk(child)


def _button_texts(parent: tk.Misc) -> set[str]:
    result: set[str] = set()
    try:
        children = parent.winfo_children()
    except Exception:
        return result
    for child in children:
        try:
            if isinstance(child, ttk.Button):
                result.add(str(child.cget("text") or "").strip())
        except Exception:
            continue
    return result


def _editor_snapshot(dlg: tk.Toplevel) -> tuple:
    """Migawka wartości widocznych w edytorze, bez geometrii i zaznaczeń."""
    state: list[tuple[Any, ...]] = []
    for widget in _walk(dlg):
        path = str(widget)
        try:
            if isinstance(widget, ttk.Entry):
                state.append(("entry", path, widget.get()))
                continue
            if isinstance(widget, ttk.Combobox):
                state.append(("combo", path, widget.get()))
                continue
            if isinstance(widget, tk.Text):
                state.append(("text", path, widget.get("1.0", "end-1c")))
                continue
            if isinstance(widget, ttk.Treeview):
                rows = []
                for iid in widget.get_children(""):
                    rows.append(
                        (
                            str(iid),
                            tuple(widget.item(iid, "values") or ()),
                            tuple(widget.item(iid, "tags") or ()),
                        )
                    )
                state.append(("tree", path, tuple(rows)))
                continue
            if isinstance(widget, tk.Listbox):
                state.append(("list", path, tuple(widget.get(0, "end"))))
                continue
            if isinstance(widget, ttk.Checkbutton):
                text = str(widget.cget("text") or "").strip()
                if text.startswith("Numer stały"):
                    continue
                variable = str(widget.cget("variable") or "")
                value = widget.tk.globalgetvar(variable) if variable else ""
                state.append(("check", path, text, str(value)))
                continue
            if isinstance(widget, ttk.Radiobutton):
                text = str(widget.cget("text") or "").strip()
                variable = str(widget.cget("variable") or "")
                value = widget.tk.globalgetvar(variable) if variable else ""
                state.append(("radio", path, text, str(value)))
                continue
            if isinstance(widget, ttk.Label):
                # Etykiety obrazu/DXF zmieniają się wraz ze stanem formularza.
                text = str(widget.cget("text") or "")
                parent_buttons = _button_texts(widget.master)
                if parent_buttons.intersection({"Wybierz...", "Wyczyść"}):
                    state.append(("media-label", path, text))
        except Exception:
            continue
    return tuple(state)


def _find_editor_number(dlg: tk.Toplevel) -> str:
    """Odczytaj numer z wiersza formularza oznaczonego etykietą „Numer”."""
    for widget in _walk(dlg):
        try:
            if not isinstance(widget, ttk.Label):
                continue
            label = str(widget.cget("text") or "").strip().rstrip(":")
            if label.lower() != "numer":
                continue
            info = widget.grid_info()
            row = info.get("row")
            parent = widget.master
            for candidate in parent.winfo_children():
                if not isinstance(candidate, ttk.Entry):
                    continue
                cinfo = candidate.grid_info()
                if cinfo.get("row") != row:
                    continue
                raw = str(candidate.get() or "").strip()
                if raw.isdigit():
                    return raw.zfill(3)
        except Exception:
            continue

    for widget in _walk(dlg):
        try:
            if not isinstance(widget, ttk.Entry):
                continue
            raw = str(widget.get() or "").strip()
            if raw.isdigit() and len(raw) <= 3:
                return raw.zfill(3)
        except Exception:
            continue
    return ""


def _persisted_open_visit_for_editor(dlg: tk.Toplevel) -> bool | None:
    module = _tool_module()
    reader = getattr(module, "_read_tool", None) if module is not None else None
    if not callable(reader):
        return None
    number = _find_editor_number(dlg)
    if not number:
        return None
    try:
        data = reader(number) or {}
    except Exception:
        return None
    visits = data.get("wizyty") if isinstance(data, dict) else None
    if not isinstance(visits, list):
        visits = []
    return any(
        isinstance(item, dict)
        and item.get("start_ts")
        and not item.get("end_ts")
        for item in visits
    )


def _active_editor() -> tk.Toplevel | None:
    candidates = [dlg for dlg in list(_EDITORS) if _alive(dlg)]
    if not candidates:
        return None
    for dlg in reversed(candidates):
        try:
            focused = dlg.focus_displayof()
            if focused is not None and focused.winfo_toplevel() == dlg:
                return dlg
        except Exception:
            continue
    return candidates[-1]


def _install_legacy_transfer_prompt_guard() -> None:
    """Usuń wyłącznie stare pytanie „Przenieść do SN?” z reakcji na status."""
    if getattr(messagebox, "_wm_tools_transfer_prompt_guard", False):
        return

    original = messagebox.askyesno

    def _askyesno(title, message, *args, **kwargs):
        if (
            str(title or "").strip() == "Przenieść"
            and str(message or "").strip() == "Przenieść do SN?"
        ):
            return False
        return original(title, message, *args, **kwargs)

    messagebox.askyesno = _askyesno
    messagebox._wm_tools_transfer_prompt_guard = True


def _install_visit_comment_guard() -> None:
    """Nie pytaj o komentarz, jeśli nie ma realnie otwartej wizyty."""
    if getattr(simpledialog, "_wm_tools_visit_comment_guard", False):
        return

    original = simpledialog.askstring

    def _askstring(title, prompt, *args, **kwargs):
        if str(title or "").strip() == "Komentarz wizyty":
            dlg = _active_editor()
            if dlg is not None:
                open_visit = _persisted_open_visit_for_editor(dlg)
                if open_visit is False:
                    return ""
        return original(title, prompt, *args, **kwargs)

    simpledialog.askstring = _askstring
    simpledialog._wm_tools_visit_comment_guard = True


def _remove_synthetic_closed_visit(data: dict[str, Any]) -> bool:
    """
    Usuń wyłącznie wizytę domkniętą w bieżącym zapisie, gdy przed zapisem
    nie było żadnej otwartej wizyty. Zachowaj zadania skopiowane do tego
    sztucznego wpisu, bo lokalny kod edytora zdążył już je wyczyścić.
    """
    module = _tool_module()
    reader = getattr(module, "_read_tool", None) if module is not None else None
    if not callable(reader) or not isinstance(data, dict):
        return False

    number = str(data.get("numer") or data.get("nr") or data.get("id") or "").strip()
    if number.isdigit():
        number = number.zfill(3)
    if not number:
        return False

    try:
        before = reader(number) or {}
    except Exception:
        return False
    if not isinstance(before, dict):
        return False

    old_visits = before.get("wizyty")
    if not isinstance(old_visits, list):
        old_visits = []

    if any(
        isinstance(item, dict)
        and item.get("start_ts")
        and not item.get("end_ts")
        for item in old_visits
    ):
        return False

    visits = data.get("wizyty")
    if not isinstance(visits, list) or len(visits) <= len(old_visits):
        return False

    extras = visits[len(old_visits):]
    synthetic = None
    for item in reversed(extras):
        if isinstance(item, dict) and item.get("start_ts") and item.get("end_ts"):
            synthetic = item
            break
    if synthetic is None:
        return False

    restored_tasks = deepcopy(synthetic.get("zadania") or [])
    visits.remove(synthetic)

    current_tasks = data.get("zadania")
    if isinstance(current_tasks, list):
        current_tasks[:] = restored_tasks
    else:
        data["zadania"] = restored_tasks

    history = data.get("historia")
    if isinstance(history, list):
        for idx in range(len(history) - 1, -1, -1):
            item = history[idx]
            if not isinstance(item, dict):
                continue
            if item.get("action") == "visit" and item.get("typ") == "cycle_closed":
                history.pop(idx)
                break

    try:
        print(
            "[WM-DBG][TOOLS_VISIT] pominięto sztuczne zamknięcie wizyty "
            f"bez otwartego startu: {number}"
        )
    except Exception:
        pass
    return True


def _install_save_guard() -> None:
    """Podłącz ochronę wizyt dokładnie przed fizycznym zapisem narzędzia."""
    module = _tool_module()
    if module is None:
        return
    current = getattr(module, "_save_tool", None)
    if not callable(current):
        return
    if getattr(current, "_wm_tools_editor_guard", False):
        return

    original = current

    def _save_tool_guarded(data):
        global _SAVE_COUNTER
        if isinstance(data, dict):
            _remove_synthetic_closed_visit(data)
        result = original(data)
        _SAVE_COUNTER += 1
        return result

    _save_tool_guarded._wm_tools_editor_guard = True
    _save_tool_guarded._wm_tools_editor_original = original
    module._save_tool = _save_tool_guarded


def _lock_existing_number(dlg: tk.Toplevel) -> None:
    """Istniejący numer jest stały; NN -> SN nigdy go nie przelicza."""
    title = str(dlg.title() or "").strip()
    if not title.startswith("Edytuj – "):
        return

    for widget in _walk(dlg):
        try:
            if not isinstance(widget, ttk.Checkbutton):
                continue
            if str(widget.cget("text") or "").strip() != "Zachowaj numer przy zmianie trybu":
                continue
            variable = str(widget.cget("variable") or "")
            if variable:
                widget.tk.globalsetvar(variable, 1)
            widget.configure(text="Numer stały – nie zmienia się przy NN → SN")
            widget.state(["disabled"])
        except Exception:
            continue


def _request_close(dlg: tk.Toplevel) -> str:
    if not _alive(dlg):
        return "break"
    try:
        saved = getattr(dlg, "_wm_tools_saved_snapshot", None)
        current = _editor_snapshot(dlg)
        changed = saved is not None and current != saved
    except Exception:
        changed = True

    if changed:
        try:
            close_anyway = messagebox.askyesno(
                "Niezapisane zmiany",
                "Masz niezapisane zmiany.\nZamknąć bez zapisywania?",
                parent=dlg,
            )
        except Exception:
            close_anyway = False
        if not close_anyway:
            return "break"

    try:
        dlg.destroy()
    except Exception:
        pass
    return "break"


def _wrap_close_buttons(dlg: tk.Toplevel) -> None:
    for widget in _walk(dlg):
        try:
            if not isinstance(widget, ttk.Button):
                continue
            text = str(widget.cget("text") or "").strip()
            if text in {"Anuluj", "Zamknij okno"}:
                widget.configure(command=lambda d=dlg: _request_close(d))
        except Exception:
            continue

    try:
        dlg.protocol("WM_DELETE_WINDOW", lambda d=dlg: _request_close(d))
    except Exception:
        pass
    try:
        dlg.bind("<Escape>", lambda _event, d=dlg: _request_close(d))
        dlg.bind("<Control-w>", lambda _event, d=dlg: _request_close(d))
    except Exception:
        pass


def _wrap_save_button(dlg: tk.Toplevel) -> None:
    for widget in _walk(dlg):
        try:
            if not isinstance(widget, ttk.Button):
                continue
            if str(widget.cget("text") or "").strip() != "Zapisz":
                continue
            if getattr(widget, "_wm_tools_save_wrapped", False):
                continue
            original_command = str(widget.cget("command") or "").strip()
            if not original_command:
                continue

            def _invoke_original(*, button=widget, command_name=original_command, dialog=dlg):
                before = _SAVE_COUNTER
                try:
                    return button.tk.call(command_name)
                finally:
                    def _refresh_saved_snapshot():
                        if not _alive(dialog):
                            return
                        if _SAVE_COUNTER > before:
                            try:
                                dialog._wm_tools_saved_snapshot = _editor_snapshot(dialog)
                            except Exception:
                                pass
                    try:
                        dialog.after(0, _refresh_saved_snapshot)
                    except Exception:
                        pass

            widget.configure(command=_invoke_original)
            widget._wm_tools_save_wrapped = True

            def _keyboard_save(_event=None, button=widget):
                try:
                    button.invoke()
                finally:
                    return "break"

            dlg.bind("<Return>", _keyboard_save)
            dlg.bind("<Control-s>", _keyboard_save)
            break
        except Exception:
            continue


def _instrument_editor(dlg: tk.Toplevel) -> None:
    if not _alive(dlg):
        return
    try:
        title = str(dlg.title() or "").strip()
    except Exception:
        return
    if title not in _EDITOR_TITLES:
        return
    if getattr(dlg, "_wm_tools_editor_runtime", False):
        return

    _install_save_guard()
    _EDITORS.add(dlg)
    _lock_existing_number(dlg)
    _wrap_close_buttons(dlg)
    _wrap_save_button(dlg)

    try:
        dlg._wm_tools_saved_snapshot = _editor_snapshot(dlg)
        dlg._wm_tools_editor_runtime = True
    except Exception:
        pass


def _install_toplevel_hook() -> None:
    if getattr(tk.Toplevel, "_wm_tools_editor_hook", False):
        return

    original_init = tk.Toplevel.__init__

    def _init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        try:
            self.after(120, lambda: _instrument_editor(self))
        except Exception:
            pass

    tk.Toplevel.__init__ = _init
    tk.Toplevel._wm_tools_editor_hook = True
    tk.Toplevel._wm_tools_editor_original_init = original_init


def install_tools_editor_runtime() -> None:
    """Zainstaluj idempotentnie wyłącznie poprawki edytora Narzędzi."""
    _install_legacy_transfer_prompt_guard()
    _install_visit_comment_guard()
    _install_toplevel_hook()


__all__ = ["install_tools_editor_runtime"]
