# version: 1.0
# Moduł: settings_common_runtime
# UI-only i integracja zapisu istniejących ustawień.

from __future__ import annotations

import calendar
import datetime as _dt
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any


_MONTHS_PL = (
    "",
    "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
)

_DYSP_COLOR_KEYS = {
    0: "dyspozycje.ui.closed_foreground",
    1: "dyspozycje.ui.new_foreground",
    2: "dyspozycje.ui.new_blink_foreground",
    3: "dyspozycje.ui.overdue_foreground",
    4: "dyspozycje.ui.overdue_blink_foreground",
    5: "dyspozycje.ui.overdue_blink_background",
}


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _hide(widget: tk.Misc) -> None:
    try:
        if widget.grid_info():
            widget.grid_remove()
            return
    except Exception:
        pass
    try:
        if widget.pack_info():
            widget.pack_forget()
    except Exception:
        pass


def _variable(widget: tk.Misc, option: str, cls: type[tk.Variable] = tk.StringVar):
    try:
        name = str(widget.cget(option) or "").strip()
    except Exception:
        return None
    if not name:
        return None
    try:
        return cls(master=widget, name=name)
    except Exception:
        return None


def _module_tab(panel: Any, title: str) -> tk.Misc | None:
    nb = getattr(panel, "_modules_nb", None)
    if nb is None:
        return None
    wanted = str(title or "").strip().lower()
    for tab_id in nb.tabs():
        try:
            if str(nb.tab(tab_id, "text") or "").strip().lower() == wanted:
                return nb.nametowidget(tab_id)
        except Exception:
            continue
    return None


def _find_text_widget(root: tk.Misc, text: str, classes=(ttk.Label, ttk.Checkbutton, ttk.Button)):
    wanted = str(text or "").strip().rstrip(":").lower()
    for widget in _all_descendants(root):
        if not isinstance(widget, classes):
            continue
        try:
            current = str(widget.cget("text") or "").strip().rstrip(":").lower()
        except Exception:
            continue
        if current == wanted:
            return widget
    return None


def _top_field_row(widget: tk.Misc) -> tk.Misc:
    node = widget
    while getattr(node, "master", None) is not None:
        parent = node.master
        if isinstance(parent, ttk.LabelFrame):
            return node
        node = parent
    return widget


def _select_widget_path(widget: tk.Misc) -> None:
    selections: list[tuple[ttk.Notebook, tk.Misc]] = []
    node: tk.Misc | None = widget
    while node is not None:
        parent = getattr(node, "master", None)
        if isinstance(parent, ttk.Notebook):
            selections.append((parent, node))
        node = parent
    for nb, tab in reversed(selections):
        try:
            nb.select(tab)
        except Exception:
            pass
    try:
        widget.focus_set()
    except Exception:
        pass


def _search_bar(panel: Any) -> None:
    nb = getattr(panel, "nb", None)
    if nb is None or getattr(panel, "_wm_search_bar", False):
        return
    parent = nb.master
    bar = ttk.Frame(parent)
    try:
        bar.pack(fill="x", padx=2, pady=(0, 6), before=nb)
    except Exception:
        bar.pack(fill="x", padx=2, pady=(0, 6))
    ttk.Label(bar, text="Szukaj ustawienia:").pack(side="left", padx=(4, 6))
    query_var = tk.StringVar(master=bar)
    entry = ttk.Entry(bar, textvariable=query_var)
    entry.pack(side="left", fill="x", expand=True)

    def _build_index():
        rows: list[tuple[str, tk.Misc]] = []
        seen: set[tuple[str, str]] = set()
        for widget in _all_descendants(nb):
            if not isinstance(widget, (ttk.Label, ttk.Checkbutton, ttk.Button, ttk.LabelFrame)):
                continue
            try:
                if not widget.winfo_manager():
                    continue
                text = str(widget.cget("text") or "").strip()
            except Exception:
                continue
            if not text or text in {"?", "Zamknij", "Dodaj", "Usuń", "↑", "↓"}:
                continue
            key = (text.lower(), str(widget))
            if key in seen:
                continue
            seen.add(key)
            rows.append((text, widget))
        return rows

    def _open_results(_event=None) -> None:
        query = str(query_var.get() or "").strip().lower()
        if not query:
            return
        matches = [(text, widget) for text, widget in _build_index() if query in text.lower()]
        win = tk.Toplevel(panel.master.winfo_toplevel())
        win.title(f"Szukaj ustawienia — {query_var.get().strip()}")
        win.geometry("620x390")
        try:
            win.transient(panel.master.winfo_toplevel())
        except Exception:
            pass
        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Wyniki: {len(matches)}").pack(anchor="w", pady=(0, 6))
        lb = tk.Listbox(outer, height=15, exportselection=False)
        lb.pack(fill="both", expand=True)
        for text, _widget in matches:
            lb.insert("end", text)

        def _go(_event=None) -> None:
            sel = lb.curselection()
            if not sel:
                return
            try:
                widget = matches[int(sel[0])][1]
                _select_widget_path(widget)
            finally:
                win.destroy()

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Przejdź", command=_go).pack(side="right")
        ttk.Button(buttons, text="Zamknij", command=win.destroy).pack(side="right", padx=(0, 6))
        lb.bind("<Double-1>", _go)
        win.bind("<Escape>", lambda _e: win.destroy())
        if matches:
            lb.selection_set(0)
            lb.focus_set()

    ttk.Button(bar, text="Szukaj", command=_open_results).pack(side="left", padx=(6, 2))
    entry.bind("<Return>", _open_results)
    setattr(panel, "_wm_search_bar", True)


def _deepest_selected_scope(panel: Any) -> tk.Misc | None:
    nb = getattr(panel, "nb", None)
    if nb is None:
        return None
    try:
        scope = nb.nametowidget(nb.select())
    except Exception:
        return None

    while True:
        selected_child = None
        for child in scope.winfo_children():
            if not isinstance(child, ttk.Notebook):
                continue
            try:
                if not child.winfo_manager() or not child.tabs():
                    continue
                selected_child = child.nametowidget(child.select())
                break
            except Exception:
                continue
        if selected_child is None:
            return scope
        scope = selected_child


def _reset_current_view_button(panel: Any) -> None:
    btns = getattr(panel, "btns", None)
    if btns is None or getattr(panel, "_wm_section_defaults_button", False):
        return
    left = None
    for child in btns.winfo_children():
        try:
            if child.pack_info().get("side") == "left":
                left = child
                break
        except Exception:
            continue
    if left is None:
        left = btns

    def _reset() -> None:
        scope = _deepest_selected_scope(panel)
        if scope is None:
            return
        var_names: set[str] = set()
        for widget in [scope, *_all_descendants(scope)]:
            for option in ("textvariable", "variable"):
                try:
                    name = str(widget.cget(option) or "").strip()
                except Exception:
                    continue
                if name:
                    var_names.add(name)

        targets: list[tuple[str, tk.Variable]] = []
        for key, var in getattr(panel, "vars", {}).items():
            if str(var) in var_names and key in getattr(panel, "_defaults", {}):
                targets.append((key, var))

        if not targets:
            messagebox.showinfo(
                "Domyślne dla sekcji",
                "Ta sekcja nie ma ustawień możliwych do przywrócenia.",
                parent=panel.master,
            )
            return
        if not messagebox.askyesno(
            "Domyślne dla sekcji",
            f"Przywrócić wartości domyślne w bieżącej sekcji?\n\nPola: {len(targets)}",
            parent=panel.master,
        ):
            return
        for key, var in targets:
            default = getattr(panel, "_defaults", {}).get(key)
            opt = getattr(panel, "_options", {}).get(key, {})
            try:
                value = panel._coerce_default_for_var(opt, default)
            except Exception:
                value = default
            try:
                var.set(value)
            except Exception:
                pass
        try:
            panel._mark_dirty()
            panel._status("Przywrócono domyślne dla bieżącej sekcji")
        except Exception:
            pass

    ttk.Button(left, text="Domyślne dla sekcji", command=_reset).pack(side="left", padx=5)
    setattr(panel, "_wm_section_defaults_button", True)


def _calendar_popup(owner: tk.Misc, target_var: tk.StringVar) -> None:
    today = _dt.date.today()
    try:
        initial = _dt.date.fromisoformat(str(target_var.get() or ""))
    except Exception:
        initial = today
    state = {"year": initial.year, "month": initial.month}

    win = tk.Toplevel(owner.winfo_toplevel())
    win.title("Wybierz datę")
    win.resizable(False, False)
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill="both", expand=True)
    head = ttk.Frame(outer)
    head.pack(fill="x", pady=(0, 6))
    title_var = tk.StringVar(master=head)
    ttk.Button(head, text="◀", width=3, command=lambda: _move(-1)).pack(side="left")
    ttk.Label(head, textvariable=title_var, anchor="center").pack(side="left", fill="x", expand=True)
    ttk.Button(head, text="▶", width=3, command=lambda: _move(1)).pack(side="right")

    grid = ttk.Frame(outer)
    grid.pack(fill="both", expand=True)
    for col, name in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):
        ttk.Label(grid, text=name, anchor="center", width=4).grid(row=0, column=col, padx=1, pady=1)

    cal = calendar.Calendar(firstweekday=0)

    def _select(day: int) -> None:
        target_var.set(f"{state['year']:04d}-{state['month']:02d}-{day:02d}")
        win.destroy()

    def _render() -> None:
        for child in list(grid.winfo_children()):
            try:
                if int(child.grid_info().get("row", 0)) > 0:
                    child.destroy()
            except Exception:
                pass
        title_var.set(f"{_MONTHS_PL[state['month']]} {state['year']}")
        weeks = cal.monthdayscalendar(state["year"], state["month"])
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day:
                    ttk.Button(grid, text=str(day), width=4, command=lambda d=day: _select(d)).grid(row=r, column=c, padx=1, pady=1)

    def _move(delta: int) -> None:
        month = state["month"] + delta
        year = state["year"]
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        state["year"], state["month"] = year, month
        _render()

    bottom = ttk.Frame(outer)
    bottom.pack(fill="x", pady=(8, 0))
    ttk.Button(bottom, text="Dzisiaj", command=lambda: _select(today.day) if (state.update(year=today.year, month=today.month) is None) else None).pack(side="left")
    ttk.Button(bottom, text="Zamknij", command=win.destroy).pack(side="right")
    _render()
    win.bind("<Escape>", lambda _e: win.destroy())
    try:
        win.grab_set()
    except Exception:
        pass


def _date_rotation_picker(panel: Any) -> None:
    root = getattr(panel, "_general_container", None)
    var = getattr(panel, "var_attendance_rotation_start", None)
    if root is None or var is None or getattr(root, "_wm_rotation_date_picker", False):
        return
    label = _find_text_widget(root, "Data startu rotacji (YYYY-MM-DD)", classes=(ttk.Label,))
    if label is None:
        return
    parent = label.master
    old_entry = None
    for child in parent.winfo_children():
        if not isinstance(child, ttk.Entry):
            continue
        try:
            if str(child.cget("textvariable") or "") == str(var):
                old_entry = child
                break
        except Exception:
            continue
    _hide(label)
    if old_entry is not None:
        _hide(old_entry)

    row = ttk.Frame(parent)
    try:
        row.pack(fill="x", padx=4, pady=(8, 4))
    except Exception:
        return
    ttk.Label(row, text="Data startu rotacji zmian:").pack(side="left", padx=(0, 8))
    ttk.Entry(row, textvariable=var, width=14, state="readonly").pack(side="left")
    ttk.Button(row, text="📅", width=3, command=lambda: _calendar_popup(row, var)).pack(side="left", padx=(5, 0))
    setattr(root, "_wm_rotation_date_picker", True)


def _move_updates_to_advanced(panel: Any) -> None:
    advanced = getattr(panel, "_advanced_container", None)
    if advanced is None or getattr(advanced, "_wm_updates_moved", False):
        return
    rows: list[tuple[str, tk.Variable]] = []
    for key, label in (
        ("ui.auto_check_updates", "Sprawdzaj dostępność aktualizacji przy starcie"),
        ("updates.auto_pull", "Automatycznie pobieraj zmiany przy starcie"),
    ):
        var = getattr(panel, "vars", {}).get(key)
        if var is None:
            continue
        rows.append((label, var))
        source = _find_text_widget(getattr(panel, "_content_area", advanced),
                                   "Sprawdzaj aktualizacje przy starcie" if key == "ui.auto_check_updates" else "Pobieraj zmiany przy starcie",
                                   classes=(ttk.Checkbutton, ttk.Label))
        if source is not None:
            _hide(_top_field_row(source))

    if rows:
        box = ttk.LabelFrame(advanced, text="Aktualizacje — automatyczne")
        box.pack(fill="x", padx=8, pady=8)
        for text, var in rows:
            ttk.Checkbutton(box, text=text, variable=var).pack(anchor="w", padx=8, pady=4)
        ttk.Label(box, text="Opcje techniczne uruchamiane przy starcie programu.").pack(anchor="w", padx=8, pady=(2, 8))
    setattr(advanced, "_wm_updates_moved", True)


def _backup_actions(panel: Any) -> None:
    backup = getattr(panel, "_backup_container", None)
    advanced = getattr(panel, "_advanced_container", None)
    if backup is None or getattr(backup, "_wm_backup_actions", False):
        return

    for child in _all_descendants(backup):
        if isinstance(child, ttk.LabelFrame):
            try:
                if str(child.cget("text") or "") == "Parametry kopii zapasowej":
                    child.configure(text="Backup — automatyka")
            except Exception:
                pass

    box = ttk.LabelFrame(backup, text="Backup — operacje")
    box.pack(fill="x", padx=8, pady=8)

    def _open_backup() -> None:
        path = ""
        try:
            path = str(panel.cfg.path_backup())
        except Exception:
            try:
                path = str(panel.cfg.get("paths.backup_dir", "") or "")
            except Exception:
                path = ""
        if not path:
            messagebox.showinfo("Backup", "Nie udało się ustalić folderu backup.", parent=panel.master)
            return
        try:
            os.makedirs(path, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Backup", path, parent=panel.master)
        except Exception as exc:
            messagebox.showerror("Backup", f"Nie udało się otworzyć folderu:\n{exc}", parent=panel.master)

    ttk.Button(box, text="Otwórz folder backup", command=_open_backup).pack(side="left", padx=8, pady=8)

    if advanced is not None:
        for text in ("Wykonaj kopię ZIP", "Przywróć z pliku…"):
            original = _find_text_widget(advanced, text, classes=(ttk.Button,))
            if original is None:
                continue
            ttk.Button(box, text=text, command=original.invoke).pack(side="left", padx=(0, 8), pady=8)
            _hide(original)

    setattr(backup, "_wm_backup_actions", True)


def _dependent_controls(panel: Any) -> None:
    auto_var = getattr(panel, "vars", {}).get("auth.auto_login_enabled")
    profile_var = getattr(panel, "vars", {}).get("auth.auto_login_profile")
    if auto_var is not None and profile_var is not None:
        profile_combo = None
        for widget in _all_descendants(getattr(panel, "_general_container", panel.master)):
            if not isinstance(widget, ttk.Combobox):
                continue
            try:
                if str(widget.cget("textvariable") or "") == str(profile_var):
                    profile_combo = widget
                    break
            except Exception:
                continue
        if profile_combo is not None and not getattr(profile_combo, "_wm_dependency", False):
            def _refresh_auto(*_args: Any) -> None:
                try:
                    profile_combo.configure(state="readonly" if bool(auto_var.get()) else "disabled")
                except Exception:
                    pass
            auto_var.trace_add("write", _refresh_auto)
            _refresh_auto()
            setattr(profile_combo, "_wm_dependency", True)

    dysp = getattr(panel, "_dispatches_container", None)
    if dysp is not None:
        blink_box = None
        for child in dysp.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                try:
                    if str(child.cget("text") or "").strip().lower() in {"miganie", "wygląd — miganie"}:
                        blink_box = child
                        break
                except Exception:
                    pass
        if blink_box is not None and not getattr(blink_box, "_wm_dependency", False):
            chk = _find_text_widget(blink_box, "Włącz miganie dyspozycji", classes=(ttk.Checkbutton,))
            blink_var = _variable(chk, "variable", tk.BooleanVar) if chk is not None else None
            entries = [x for x in blink_box.winfo_children() if isinstance(x, ttk.Entry)]
            if blink_var is not None:
                def _refresh_blink(*_args: Any) -> None:
                    state = "normal" if bool(blink_var.get()) else "disabled"
                    for entry in entries:
                        try:
                            entry.configure(state=state)
                        except Exception:
                            pass
                blink_var.trace_add("write", _refresh_blink)
                _refresh_blink()
            setattr(blink_box, "_wm_dependency", True)


def _integrate_dispatches_save(panel: Any) -> None:
    dysp = getattr(panel, "_dispatches_container", None)
    if dysp is None or getattr(dysp, "_wm_global_save_integrated", False):
        return
    extras: dict[str, tuple[tk.Variable, str]] = {}

    colors_box = None
    blink_box = None
    for child in dysp.winfo_children():
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            title = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if title in {"kolory", "wygląd — kolory"}:
            colors_box = child
        elif title in {"miganie", "wygląd — miganie"}:
            blink_box = child

    if colors_box is not None:
        for entry in colors_box.winfo_children():
            if not isinstance(entry, ttk.Entry):
                continue
            try:
                row = int(entry.grid_info().get("row", -1))
            except Exception:
                continue
            key = _DYSP_COLOR_KEYS.get(row)
            var = _variable(entry, "textvariable")
            if key and var is not None:
                extras[key] = (var, "str")

    if blink_box is not None:
        chk = _find_text_widget(blink_box, "Włącz miganie dyspozycji", classes=(ttk.Checkbutton,))
        var = _variable(chk, "variable", tk.BooleanVar) if chk is not None else None
        if var is not None:
            extras["dyspozycje.ui.blink_enabled"] = (var, "bool")
        for entry in blink_box.winfo_children():
            if not isinstance(entry, ttk.Entry):
                continue
            try:
                row = int(entry.grid_info().get("row", -1))
            except Exception:
                continue
            key = {1: "dyspozycje.ui.new_blink_ms", 2: "dyspozycje.ui.overdue_blink_ms"}.get(row)
            evar = _variable(entry, "textvariable")
            if key and evar is not None:
                extras[key] = (evar, "int")

    for button in _all_descendants(dysp):
        if isinstance(button, ttk.Button):
            try:
                if str(button.cget("text") or "") == "Zapisz ustawienia Dyspozycji":
                    _hide(button)
            except Exception:
                pass

    for var, _kind in extras.values():
        try:
            var.trace_add("write", lambda *_: panel._mark_dirty())
        except Exception:
            pass
    panel._wm_dispatches_extra_vars = extras
    setattr(dysp, "_wm_global_save_integrated", True)


def _decorate_magazyn_after_init(panel: Any) -> None:
    frame = getattr(panel, "_magazyn_frame", None)
    if frame is None:
        return
    for child in _all_descendants(frame):
        if isinstance(child, ttk.LabelFrame):
            try:
                if str(child.cget("text") or "").strip() == "Parametry magazynu":
                    child.configure(text="Logika — stany i rezerwacje")
            except Exception:
                pass

    # Słowniki mają własny zapis pliku; podpinamy go do globalnego „Zapisz wszystko”.
    for button in list(_all_descendants(frame)):
        if not isinstance(button, ttk.Button):
            continue
        try:
            text = str(button.cget("text") or "")
        except Exception:
            continue
        if text == "Zapisz" and isinstance(button.master, tk.Misc):
            extra = getattr(panel, "_wm_extra_save_buttons", [])
            if button not in extra:
                extra.append(button)
                panel._wm_extra_save_buttons = extra
            _hide(button)
        elif text in {"Dodaj", "Usuń", "Góra", "Dół"}:
            try:
                button.bind("<ButtonRelease-1>", lambda _e: panel._mark_dirty(), add="+")
            except Exception:
                pass
    for entry in _all_descendants(frame):
        if isinstance(entry, ttk.Entry):
            try:
                entry.bind("<KeyRelease>", lambda _e: panel._mark_dirty(), add="+")
            except Exception:
                pass

    try:
        from settings_help_runtime import decorate_settings_help
        decorate_settings_help(panel)
    except Exception:
        pass


def _decorate(panel: Any) -> None:
    for action in (
        _search_bar,
        _reset_current_view_button,
        _date_rotation_picker,
        _move_updates_to_advanced,
        _backup_actions,
        _dependent_controls,
        _integrate_dispatches_save,
    ):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_common_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_common_runtime", False):
        return

    # Skróty N/M/P były skrótami samego okna Ustawień i potrafiły kolidować z resztą WM.
    original_shortcuts = getattr(settings_panel_cls, "_bind_global_shortcuts", None)
    if callable(original_shortcuts):
        settings_panel_cls._wm_original_global_shortcuts = original_shortcuts
        settings_panel_cls._bind_global_shortcuts = lambda self: None

    original_build = getattr(settings_panel_cls, "_build_ui", None)
    original_modules_change = getattr(settings_panel_cls, "_on_modules_tab_change", None)
    original_save = getattr(settings_panel_cls, "save", None)
    if not callable(original_build):
        return

    def _build_ui_with_common(self, *args: Any, **kwargs: Any):
        result = original_build(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_common

    if callable(original_modules_change):
        def _modules_change_fixed(self, *args: Any, **kwargs: Any):
            result = original_modules_change(self, *args, **kwargs)
            try:
                frame = getattr(self, "_magazyn_frame", None)
                nb = getattr(self, "_modules_nb", None)
                if frame is not None and nb is not None and not getattr(self, "_magazyn_initialized", False):
                    if nb.select() == str(frame):
                        self._init_magazyn_tab()
                        _decorate_magazyn_after_init(self)
            except Exception:
                pass
            return result
        settings_panel_cls._on_modules_tab_change = _modules_change_fixed

    if callable(original_save):
        def _save_with_integrations(self, *args: Any, **kwargs: Any):
            cfg = getattr(self, "cfg", None)
            if cfg is not None:
                for key, pair in getattr(self, "_wm_dispatches_extra_vars", {}).items():
                    var, kind = pair
                    try:
                        value = var.get()
                        if kind == "bool":
                            value = bool(value)
                        elif kind == "int":
                            value = int(str(value).strip())
                        else:
                            value = str(value).strip()
                        cfg.set(key, value)
                    except Exception:
                        pass
            for button in getattr(self, "_wm_extra_save_buttons", []):
                try:
                    if button.winfo_exists():
                        button.invoke()
                except Exception:
                    pass
            result = original_save(self, *args, **kwargs)
            return result
        settings_panel_cls.save = _save_with_integrations

    settings_panel_cls._wm_settings_common_runtime = True
