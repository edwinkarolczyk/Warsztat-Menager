# version: 1.0
"""Drobne poprawki UI przeglądów/serwisów Maszyn.

Zakres:
- pole „Sugerowani” w dialogu dodawania przeglądu korzysta z listy użytkowników WM,
- zachowany jest dotychczasowy zapis ``suggested_workers`` jako lista loginów,
- okno Użytkowanie maszyny jest powiązane z panelem Maszyn, z którego je otwarto;
  po przebudowie/usunięciu panelu stare okno jest zamykane, żeby callbacki nie
  próbowały odświeżać zniszczonego Treeview.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

_DIALOG_TITLE = "Dodaj przegląd / serwis"
_USAGE_TITLE_PREFIX = "Użytkowanie maszyny"
_MAIN_MACHINE_COLUMNS = (
    "id",
    "nazwa",
    "typ",
    "status",
    "przeglad",
    "przeglad_status",
    "dni",
)
_INSTALLED = False


def _safe_title(widget: Any) -> str:
    try:
        return str(widget.winfo_toplevel().title() or "")
    except Exception:
        return ""


def _walk_widgets(root: Any):
    try:
        children = list(root.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk_widgets(child)


def _entry_text(entry: Any) -> str:
    try:
        return str(entry.get() or "").strip()
    except Exception:
        return ""


def _set_entry_text(entry: Any, value: str) -> None:
    try:
        entry.delete(0, "end")
        entry.insert(0, value)
        return
    except Exception:
        pass
    try:
        variable = str(entry.cget("textvariable") or "").strip()
        if variable:
            entry.setvar(variable, value)
    except Exception:
        pass


def _split_people(value: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in str(value or "").split(","):
        login = raw.strip()
        if not login:
            continue
        key = login.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(login)
    return out


def _load_wm_user_logins() -> list[str]:
    """Użyj tego samego źródła użytkowników co moduł Maszyny."""
    values: list[str] = []
    try:
        import gui_maszyny as _machines

        loader = getattr(_machines, "_load_wm_user_logins", None)
        if callable(loader):
            values = [str(x).strip() for x in (loader() or []) if str(x).strip()]
    except Exception:
        values = []

    if not values:
        try:
            from services.profile_service import get_all_users

            raw = get_all_users()
            if isinstance(raw, dict):
                raw = raw.get("users") or raw.get("profiles") or list(raw.values())
            for row in raw or []:
                if isinstance(row, str):
                    login = row.strip()
                elif isinstance(row, dict):
                    login = str(
                        row.get("login") or row.get("user") or row.get("name") or ""
                    ).strip()
                else:
                    login = ""
                if login:
                    values.append(login)
        except Exception:
            pass

    out: list[str] = []
    seen: set[str] = set()
    for login in values:
        key = login.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(login)
    return out


def _is_suggested_entry(entry: Any) -> bool:
    if _safe_title(entry) != _DIALOG_TITLE:
        return False
    try:
        info = dict(entry.grid_info())
        row = str(info.get("row"))
        for sibling in entry.master.winfo_children():
            if sibling is entry:
                continue
            try:
                text = str(sibling.cget("text") or "").strip()
            except Exception:
                continue
            if text != "Sugerowani:":
                continue
            try:
                sibling_row = str(sibling.grid_info().get("row"))
            except Exception:
                sibling_row = ""
            if sibling_row == row:
                return True
    except Exception:
        return False
    return False


def _selection_summary(selected: list[str]) -> str:
    return ", ".join(selected) if selected else "Nie wybrano"


def _decorate_suggested_entry(entry: Any) -> None:
    try:
        if getattr(entry, "_wm_machine_suggested_selector", None) is not None:
            return
        if not _is_suggested_entry(entry):
            return

        info = dict(entry.grid_info())
        parent = entry.master
        row = int(info.get("row", 2))
        column = int(info.get("column", 1))
        current = _split_people(_entry_text(entry))

        holder = ttk.Frame(parent)
        holder.columnconfigure(0, weight=1)
        holder.grid(
            row=row,
            column=column,
            columnspan=int(info.get("columnspan", 1) or 1),
            rowspan=int(info.get("rowspan", 1) or 1),
            sticky=info.get("sticky", "ew") or "ew",
            padx=info.get("padx", 4) or 4,
            pady=info.get("pady", 4) or 4,
        )
        try:
            entry.grid_remove()
        except Exception:
            pass

        summary_var = tk.StringVar(master=parent, value=_selection_summary(current))
        summary = ttk.Entry(holder, textvariable=summary_var, state="readonly")
        summary.grid(row=0, column=0, sticky="ew")
        choose_button = ttk.Button(holder, text="Wybierz…")
        choose_button.grid(row=0, column=1, padx=(6, 0))

        def _open_selector() -> None:
            users = _load_wm_user_logins()
            if not users:
                messagebox.showinfo(
                    "Sugerowani",
                    "Brak użytkowników WM do wyboru.",
                    parent=entry.winfo_toplevel(),
                )
                return

            selected_now = {
                login.casefold(): login for login in _split_people(_entry_text(entry))
            }
            selector = tk.Toplevel(entry.winfo_toplevel())
            selector.title("Wybierz sugerowanych użytkowników")
            selector.resizable(False, True)
            try:
                selector.transient(entry.winfo_toplevel())
                selector.grab_set()
            except Exception:
                pass

            outer = ttk.Frame(selector, padding=12)
            outer.pack(fill="both", expand=True)
            ttk.Label(
                outer,
                text="Zaznacz osoby sugerowane do tego przeglądu / serwisu:",
            ).pack(anchor="w", pady=(0, 8))

            people = ttk.Frame(outer)
            people.pack(fill="both", expand=True)
            variables: dict[str, tk.BooleanVar] = {}
            for login in users:
                var = tk.BooleanVar(
                    master=selector,
                    value=login.casefold() in selected_now,
                )
                variables[login] = var
                ttk.Checkbutton(people, text=login, variable=var).pack(
                    anchor="w", fill="x", pady=2
                )

            actions = ttk.Frame(outer)
            actions.pack(fill="x", pady=(10, 0))

            def _select_all(value: bool) -> None:
                for var in variables.values():
                    var.set(value)

            def _apply() -> None:
                chosen = [
                    login
                    for login in users
                    if bool(variables.get(login) and variables[login].get())
                ]
                _set_entry_text(entry, ", ".join(chosen))
                summary_var.set(_selection_summary(chosen))
                selector.destroy()

            ttk.Button(
                actions, text="Wszyscy", command=lambda: _select_all(True)
            ).pack(side="left")
            ttk.Button(
                actions, text="Wyczyść", command=lambda: _select_all(False)
            ).pack(side="left", padx=(6, 0))
            ttk.Button(actions, text="Zapisz wybór", command=_apply).pack(
                side="right"
            )
            ttk.Button(actions, text="Anuluj", command=selector.destroy).pack(
                side="right", padx=(0, 6)
            )

        choose_button.configure(command=_open_selector)
        entry._wm_machine_suggested_selector = holder
        entry._wm_machine_suggested_summary = summary_var
    except Exception as exc:
        print(f"[WM-DBG][MASZYNY][SUGGESTED][WARN] selector setup failed: {exc}")


def _tree_columns(tree: Any) -> tuple[str, ...]:
    try:
        raw = tree.cget("columns")
        if isinstance(raw, (tuple, list)):
            return tuple(str(x) for x in raw)
        return tuple(str(x) for x in tree.tk.splitlist(raw))
    except Exception:
        return ()


def _is_main_machine_tree(tree: Any) -> bool:
    try:
        if not isinstance(tree, ttk.Treeview):
            return False
        if _safe_title(tree).startswith(_USAGE_TITLE_PREFIX):
            return False
        return _tree_columns(tree) == _MAIN_MACHINE_COLUMNS
    except Exception:
        return False


def _find_source_machine_tree(win: Any) -> Any | None:
    try:
        root = win._root()
    except Exception:
        return None

    candidates: list[Any] = []
    for widget in _walk_widgets(root):
        if not _is_main_machine_tree(widget):
            continue
        try:
            if not widget.winfo_exists():
                continue
        except Exception:
            continue
        candidates.append(widget)

    if not candidates:
        return None

    mapped: list[Any] = []
    for widget in candidates:
        try:
            if widget.winfo_ismapped():
                mapped.append(widget)
        except Exception:
            pass
    return (mapped or candidates)[-1]


def _bind_usage_window_lifecycle(win: Any) -> None:
    try:
        if getattr(win, "_wm_machine_source_tree", None) is not None:
            return
        if not str(win.title() or "").startswith(_USAGE_TITLE_PREFIX):
            return
    except Exception:
        return

    source = _find_source_machine_tree(win)
    if source is None:
        if not getattr(win, "_wm_machine_source_tree_retry", False):
            win._wm_machine_source_tree_retry = True
            try:
                win.after_idle(lambda: _bind_usage_window_lifecycle(win))
            except Exception:
                pass
        return

    win._wm_machine_source_tree = source
    binding_id: str | None = None

    def _source_destroyed(event=None) -> None:
        try:
            if event is not None and getattr(event, "widget", None) is not source:
                return
            if not win.winfo_exists():
                return
            print(
                "[WM-DBG][MASZYNY][USAGE] source panel destroyed; "
                "closing stale usage window"
            )
            win.destroy()
        except Exception:
            pass

    try:
        binding_id = source.bind("<Destroy>", _source_destroyed, add="+")
    except Exception:
        binding_id = None

    def _cleanup(event=None) -> None:
        try:
            if event is not None and getattr(event, "widget", None) is not win:
                return
            if binding_id and source.winfo_exists():
                source.unbind("<Destroy>", binding_id)
        except Exception:
            pass

    try:
        win.bind("<Destroy>", _cleanup, add="+")
    except Exception:
        pass


def install() -> None:
    """Zainstaluj poprawki raz, bez zmiany modeli danych Maszyn."""
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        original_entry_grid = ttk.Entry.grid
        if not getattr(original_entry_grid, "_wm_machine_review_runtime", False):
            def _entry_grid(self, *args, **kwargs):
                result = original_entry_grid(self, *args, **kwargs)
                _decorate_suggested_entry(self)
                return result

            _entry_grid._wm_machine_review_runtime = True
            ttk.Entry.grid = _entry_grid
    except Exception as exc:
        print(f"[WM-DBG][MASZYNY][SUGGESTED][WARN] grid patch failed: {exc}")

    try:
        original_title = tk.Toplevel.title
        if not getattr(original_title, "_wm_machine_review_runtime", False):
            def _title(self, string=None):
                if string is None:
                    return original_title(self)
                result = original_title(self, string)
                if str(string or "").startswith(_USAGE_TITLE_PREFIX):
                    try:
                        self.after_idle(lambda: _bind_usage_window_lifecycle(self))
                    except Exception:
                        pass
                return result

            _title._wm_machine_review_runtime = True
            tk.Toplevel.title = _title
    except Exception as exc:
        print(f"[WM-DBG][MASZYNY][USAGE][WARN] lifecycle patch failed: {exc}")

    _INSTALLED = True
    print("[WM-DBG][MASZYNY] suggested users + stale usage guard aktywne")


__all__ = ["install"]
