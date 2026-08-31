# version: 1.1
# Moduł: settings_users_runtime
# UI-only: porządkowanie Ustawienia → Użytkownicy / Profile.

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


def _mark_dirty(panel: Any) -> None:
    marker = getattr(panel, "_mark_dirty", None)
    if callable(marker):
        try:
            marker()
            return
        except Exception:
            pass
    try:
        panel._dirty = True
        panel._unsaved = True
    except Exception:
        pass


def _rename_tabs(panel: Any) -> None:
    """Nazwij główne podzakładki sekcji Użytkownicy jednoznacznie."""
    nb = getattr(panel, "_users_notebook", None)
    if nb is None:
        return

    profile_widget = None
    users_widget = None
    for tab_id in nb.tabs():
        try:
            text = str(nb.tab(tab_id, "text") or "").strip()
        except Exception:
            continue
        if text in {"Lista i edycja", "Użytkownicy"}:
            nb.tab(tab_id, text="Użytkownicy")
            try:
                users_widget = nb.nametowidget(tab_id)
            except Exception:
                users_widget = None
        elif text in {"Profil użytkownika", "Profil", "Profile"}:
            nb.tab(tab_id, text="Profile")
            try:
                profile_widget = nb.nametowidget(tab_id)
            except Exception:
                profile_widget = None

    register = getattr(panel, "_register_nested_tab", None)
    top = getattr(panel, "tab_users", None)
    if callable(register) and top is not None:
        if users_widget is not None:
            try:
                register("Użytkownicy", top, nb, users_widget)
            except Exception:
                pass
        if profile_widget is not None:
            for alias in ("Profile", "Profil"):
                try:
                    register(alias, top, nb, profile_widget)
                except Exception:
                    pass


def _cleanup_embedded_profile_manager(panel: Any) -> None:
    """Usuń martwą, trzecią zakładkę Profil z menedżera kont.

    Rzeczywiste ustawienia Profilu są w sąsiedniej zakładce ``Profile``.
    W menedżerze kont zostają tylko ``Użytkownicy`` oraz ``Rangi``.
    """
    root = getattr(panel, "_users_container", None)
    if root is None:
        return
    try:
        from ustawienia_uzytkownicy import SettingsProfilesTab
    except Exception:
        return

    for widget in _all_descendants(root):
        if not isinstance(widget, SettingsProfilesTab):
            continue
        nb = getattr(widget, "nb", None)
        if nb is None or getattr(widget, "_wm_profile_manager_clean", False):
            continue
        for tab_id in list(nb.tabs()):
            try:
                text = str(nb.tab(tab_id, "text") or "").strip()
            except Exception:
                continue
            if text == "Lista i edycja":
                nb.tab(tab_id, text="Użytkownicy")
            elif text == "Profil użytkownika":
                try:
                    nb.forget(tab_id)
                except Exception:
                    pass
        setattr(widget, "_wm_profile_manager_clean", True)


def _profile_settings_frame(panel: Any):
    root = getattr(panel, "_users_container", None)
    if root is None:
        return None
    for widget in _all_descendants(root):
        if not isinstance(widget, ttk.LabelFrame):
            continue
        try:
            text = str(widget.cget("text") or "").strip()
        except Exception:
            continue
        if text in {"Ustawienia profilu użytkownika", "Profil — wygląd i edycja", "Profile — ustawienia"}:
            return widget
    return None


def _rebuild_profile_settings(panel: Any) -> None:
    """Podziel ustawienia Profilu na czytelne grupy bez zmiany danych."""
    frame = _profile_settings_frame(panel)
    if frame is None or getattr(frame, "_wm_profile_settings_clean", False):
        return

    required = (
        "var_profile_enabled",
        "var_profile_header",
        "var_profile_avatar",
        "var_profile_pin_change",
        "var_profile_editable_fields",
    )
    if any(not hasattr(panel, name) for name in required):
        return

    for child in list(frame.winfo_children()):
        _hide(child)

    frame.configure(text="Profile — ustawienia")
    try:
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
    except Exception:
        pass

    ttk.Label(
        frame,
        text="Tu ustawiasz wygląd Profilu i zakres danych, które użytkownik może zmieniać samodzielnie.",
        style="WM.Muted.TLabel",
        wraplength=760,
        justify="left",
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 10))

    visibility = ttk.LabelFrame(frame, text="Widoczność profilu")
    visibility.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
    ttk.Checkbutton(
        visibility,
        text="Włącz kartę Profil",
        variable=panel.var_profile_enabled,
        command=lambda: _mark_dirty(panel),
    ).pack(anchor="w", padx=10, pady=(8, 4))
    ttk.Checkbutton(
        visibility,
        text="Pokazuj imię w nagłówku",
        variable=panel.var_profile_header,
        command=lambda: _mark_dirty(panel),
    ).pack(anchor="w", padx=10, pady=4)
    ttk.Checkbutton(
        visibility,
        text="Włącz avatar",
        variable=panel.var_profile_avatar,
        command=lambda: _mark_dirty(panel),
    ).pack(anchor="w", padx=10, pady=(4, 8))

    edit = ttk.LabelFrame(frame, text="Edycja własnego profilu")
    edit.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
    ttk.Checkbutton(
        edit,
        text="Zezwól użytkownikowi na zmianę PIN",
        variable=panel.var_profile_pin_change,
        command=lambda: _mark_dirty(panel),
    ).pack(anchor="w", padx=10, pady=(8, 6))
    ttk.Label(
        edit,
        text="Pola, które użytkownik może edytować:",
        style="WM.Muted.TLabel",
    ).pack(anchor="w", padx=10, pady=(2, 4))

    try:
        raw = str(panel.var_profile_editable_fields.get() or "")
    except Exception:
        raw = ""
    current = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    known = {key for key, _label in _FIELDS}
    extras = [x for x in current if x not in known]
    vars_by_key: dict[str, tk.BooleanVar] = {}

    fields = ttk.Frame(edit)
    fields.pack(fill="x", padx=8, pady=(0, 8))

    def _sync_fields() -> None:
        values = [key for key, _label in _FIELDS if vars_by_key[key].get()]
        values.extend(x for x in extras if x not in values)
        panel.var_profile_editable_fields.set(", ".join(values))
        _mark_dirty(panel)

    for idx, (key, label) in enumerate(_FIELDS):
        var = tk.BooleanVar(master=fields, value=key in current)
        vars_by_key[key] = var
        ttk.Checkbutton(fields, text=label, variable=var, command=_sync_fields).grid(
            row=idx // 2,
            column=idx % 2,
            sticky="w",
            padx=(2, 14),
            pady=3,
        )

    if extras:
        ttk.Label(
            edit,
            text="Pozostałe zapisane pola: " + ", ".join(extras),
            style="WM.Muted.TLabel",
        ).pack(anchor="w", padx=10, pady=(0, 8))

    ttk.Label(
        frame,
        text="Konta, role i uprawnienia znajdują się w zakładce Użytkownicy / Rangi.",
        style="WM.Muted.TLabel",
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

    frame._wm_profile_field_vars = vars_by_key
    setattr(frame, "_wm_profile_settings_clean", True)


def _open_requested_profile_tab(panel: Any) -> None:
    """Obsłuż przejście Profil → Ustawienia → Profile."""
    try:
        root = panel.winfo_toplevel()
    except Exception:
        return
    target = str(getattr(root, "_wm_settings_target_tab", "") or "").strip().casefold()
    if target not in {"profil", "profile", "profiles"}:
        return
    opener = getattr(panel, "open_tab", None)
    if callable(opener):
        try:
            opener("Profile")
        except Exception:
            pass
    try:
        delattr(root, "_wm_settings_target_tab")
    except Exception:
        pass


def _decorate(panel: Any) -> None:
    for action in (
        _rename_tabs,
        _cleanup_embedded_profile_manager,
        _rebuild_profile_settings,
        _open_requested_profile_tab,
    ):
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


__all__ = [
    "_cleanup_embedded_profile_manager",
    "_open_requested_profile_tab",
    "_rebuild_profile_settings",
    "install_settings_users_runtime",
]
