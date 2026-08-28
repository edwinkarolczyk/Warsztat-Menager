# version: 1.0
# Moduł: settings_structure_runtime
# UI-only: porządkowanie widoku Ustawień bez zmiany kluczy konfiguracji.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


_TIMEOUT_CHOICES = [
    (5, "5 min"),
    (10, "10 min"),
    (15, "15 min"),
    (30, "30 min"),
    (60, "60 min"),
    (240, "4 h"),
]


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _frame_with_label(root: tk.Misc, text: str) -> tk.Misc | None:
    wanted = str(text).strip()
    for child in _all_descendants(root):
        if not isinstance(child, ttk.Label):
            continue
        try:
            if str(child.cget("text") or "").strip() == wanted:
                return child.master
        except Exception:
            continue
    return None


def _remove_jarvis_from_modules(panel: Any) -> None:
    nb = getattr(panel, "_modules_nb", None)
    if nb is None:
        return
    for tab_id in list(nb.tabs()):
        try:
            title = str(nb.tab(tab_id, "text") or "").strip().lower()
        except Exception:
            continue
        if title == "jarvis":
            nb.forget(tab_id)
            break


def _ensure_modules_general_tab(panel: Any) -> None:
    nb = getattr(panel, "_modules_nb", None)
    if nb is None:
        return

    for tab_id in nb.tabs():
        try:
            if str(nb.tab(tab_id, "text") or "").strip().lower() == "główne":
                return
        except Exception:
            continue

    frame = ttk.Frame(nb)
    try:
        nb.insert(0, frame, text="Główne")
    except Exception:
        nb.add(frame, text="Główne")

    logic = ttk.LabelFrame(frame, text="Logika wspólna modułów")
    logic.pack(fill="x", padx=10, pady=(10, 6))
    ttk.Label(
        logic,
        text=(
            "Tu trafiają wyłącznie ustawienia używane przez więcej niż jeden moduł. "
            "Ustawienia własne Maszyn, Narzędzi, Dyspozycji itd. pozostają w ich zakładkach."
        ),
        wraplength=900,
        justify="left",
    ).pack(anchor="w", padx=10, pady=10)

    hint = ttk.LabelFrame(frame, text="Zasada")
    hint.pack(fill="x", padx=10, pady=6)
    ttk.Label(
        hint,
        text="Wygląd = tylko prezentacja.  Logika = zmienia zachowanie programu.",
    ).pack(anchor="w", padx=10, pady=10)


def _rename_dispatches_sections(panel: Any) -> None:
    parent = getattr(panel, "_dispatches_container", None)
    if parent is None:
        return
    try:
        parent.configure(text="Dyspozycje")
    except Exception:
        pass

    mapping = {
        "kolory": "Wygląd — kolory",
        "miganie": "Wygląd — miganie",
        "automatyzacja przeglądów maszyn": "Logika — automatyzacja przeglądów maszyn",
    }
    for child in parent.winfo_children():
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            old = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if old in mapping:
            try:
                child.configure(text=mapping[old])
            except Exception:
                pass


def _polish_only_language(panel: Any) -> None:
    root = getattr(panel, "_general_container", None)
    if root is None:
        return
    frame = _frame_with_label(root, "Język")
    if frame is None:
        return

    lang_var = getattr(panel, "vars", {}).get("ui.language")
    if lang_var is not None:
        try:
            lang_var.set("pl")
        except Exception:
            pass

    for child in _all_descendants(frame):
        if not isinstance(child, ttk.Combobox):
            continue
        try:
            child.configure(values=("Polski",), state="readonly")
            child.set("Polski")
        except Exception:
            pass
        break


def _replace_session_timeout_with_choice(panel: Any) -> None:
    root = getattr(panel, "_general_container", None)
    if root is None:
        return
    frame = _frame_with_label(root, "Timeout sesji (min)")
    if frame is None or getattr(frame, "_wm_timeout_choice_done", False):
        return

    source_var = getattr(panel, "vars", {}).get("auth.session_timeout_min")
    if source_var is None:
        return

    old_widget = None
    for child in _all_descendants(frame):
        if isinstance(child, ttk.Spinbox):
            old_widget = child
            break
    if old_widget is None:
        return

    try:
        grid = old_widget.grid_info()
    except Exception:
        return

    display_var = tk.StringVar(master=frame)
    labels = [label for _value, label in _TIMEOUT_CHOICES]
    values_by_label = {label: value for value, label in _TIMEOUT_CHOICES}
    labels_by_value = {value: label for value, label in _TIMEOUT_CHOICES}

    def _sync_from_value(*_args: Any) -> None:
        try:
            current = int(source_var.get())
        except Exception:
            current = 30
        display_var.set(labels_by_value.get(current, f"{current} min"))

    def _apply_choice(_event=None) -> None:
        label = str(display_var.get() or "").strip()
        value = values_by_label.get(label)
        if value is not None:
            source_var.set(value)

    combo = ttk.Combobox(
        frame,
        textvariable=display_var,
        values=labels,
        state="readonly",
        width=12,
    )
    combo.grid(
        row=grid.get("row", 0),
        column=grid.get("column", 1),
        rowspan=grid.get("rowspan", 1),
        columnspan=grid.get("columnspan", 1),
        sticky=grid.get("sticky", "w"),
        padx=grid.get("padx", 5),
        pady=grid.get("pady", 5),
    )
    combo.bind("<<ComboboxSelected>>", _apply_choice)
    try:
        old_widget.grid_remove()
    except Exception:
        pass

    _sync_from_value()
    try:
        source_var.trace_add("write", _sync_from_value)
    except Exception:
        pass

    setattr(frame, "_wm_timeout_choice_done", True)


def _decorate(panel: Any) -> None:
    for action in (
        _remove_jarvis_from_modules,
        _ensure_modules_general_tab,
        _rename_dispatches_sections,
        _polish_only_language,
        _replace_session_timeout_with_choice,
    ):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_structure_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_structure_runtime", False):
        return

    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original_build_ui):
        return

    def _build_ui_with_structure(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_structure
    settings_panel_cls._wm_settings_structure_runtime = True
