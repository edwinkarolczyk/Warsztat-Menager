# version: 1.0
# Moduł: settings_users_runtime
# UI-only: porządkowanie Ustawienia → Użytkownicy / Profil.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


_FIELDS = (
    ("imie", "Imię"),
    ("nazwisko", "Nazwisko"),
    ("staz", "Staż / data zatrudnienia"),
    ("telefon", "Telefon"),
    ("email", "E-mail"),
)


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


def _rename_tabs(panel: Any) -> None:
    nb = getattr(panel, "_users_notebook", None)
    if nb is None:
        return
    for tab_id in nb.tabs():
        try:
            text = str(nb.tab(tab_id, "text") or "").strip()
        except Exception:
            continue
        if text == "Lista i edycja":
            nb.tab(tab_id, text="Użytkownicy")
        elif text == "Profil użytkownika":
            nb.tab(tab_id, text="Profil")


def _editable_fields_choices(panel: Any) -> None:
    root = getattr(panel, "_users_container", None)
    source_var = getattr(panel, "var_profile_editable_fields", None)
    if root is None or source_var is None or getattr(root, "_wm_profile_fields_choices", False):
        return

    label = None
    entry = None
    hint = None
    for widget in _all_descendants(root):
        if isinstance(widget, ttk.Label):
            try:
                text = str(widget.cget("text") or "").strip()
            except Exception:
                text = ""
            if text.startswith("Pola edytowane przez użytkownika"):
                label = widget
            elif text.startswith("Np.: imie, nazwisko"):
                hint = widget
    if label is None:
        return

    parent = label.master
    for child in parent.winfo_children():
        if isinstance(child, ttk.Entry):
            try:
                if int(child.grid_info().get("row", -1)) == 4:
                    entry = child
                    break
            except Exception:
                continue

    if entry is not None:
        _hide(entry)
    _hide(label)
    if hint is not None:
        _hide(hint)

    try:
        raw = str(source_var.get() or "")
    except Exception:
        raw = ""
    current = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    known = {key for key, _label in _FIELDS}
    extras = [x for x in current if x not in known]

    box = ttk.LabelFrame(parent, text="Pola, które użytkownik może edytować")
    box.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4))

    vars_by_key: dict[str, tk.BooleanVar] = {}

    def _sync() -> None:
        values = [key for key, _label in _FIELDS if vars_by_key[key].get()]
        values.extend(x for x in extras if x not in values)
        source_var.set(", ".join(values))

    for idx, (key, text) in enumerate(_FIELDS):
        var = tk.BooleanVar(master=box, value=key in current)
        vars_by_key[key] = var
        ttk.Checkbutton(box, text=text, variable=var, command=_sync).grid(
            row=idx // 3,
            column=idx % 3,
            sticky="w",
            padx=8,
            pady=5,
        )

    if extras:
        ttk.Label(box, text="Pozostałe zapisane pola: " + ", ".join(extras)).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6)
        )

    setattr(root, "_wm_profile_fields_choices", True)


def _rename_profile_group(panel: Any) -> None:
    root = getattr(panel, "_users_container", None)
    if root is None:
        return
    for widget in _all_descendants(root):
        if not isinstance(widget, ttk.LabelFrame):
            continue
        try:
            text = str(widget.cget("text") or "").strip()
        except Exception:
            continue
        if text == "Ustawienia profilu użytkownika":
            widget.configure(text="Profil — wygląd i edycja")


def _decorate(panel: Any) -> None:
    for action in (_rename_tabs, _rename_profile_group, _editable_fields_choices):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_users_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_users_runtime", False):
        return
    original = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original):
        return

    def _build_ui_with_users(self, *args: Any, **kwargs: Any):
        result = original(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_users
    settings_panel_cls._wm_settings_users_runtime = True
