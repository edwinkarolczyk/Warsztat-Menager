# version: 1.0
"""Spłaszcza administrację użytkowników w panelu Brygadzisty.

Zewnętrzna karta „Użytkownicy” pokazuje bezpośrednio listę kont. Ustawienia
Profilu i uprawnienia Rang pozostają dostępne jako osobne okna, bez drugiego
Notebooka „Użytkownicy | Profile | Rangi”.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from profile_admin_ui import ProfileSettingsPanel, RolesAdminPanel, UsersAdminPanel
from ui_context_help import add_help_button

_INSTALLED = False


def _open_admin_window(owner, title: str, panel_cls) -> None:
    win = tk.Toplevel(owner)
    win.title(title)
    win.geometry("920x620")
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass

    body = ttk.Frame(win, padding=10)
    body.pack(fill="both", expand=True)
    panel = panel_cls(body)
    panel.pack(fill="both", expand=True)

    bottom = ttk.Frame(win)
    bottom.pack(fill="x", padx=10, pady=(0, 10))
    ttk.Button(bottom, text="Zamknij", command=win.destroy).pack(side="right")


def _flatten_users_tab(panel) -> None:
    tabs = getattr(panel, "_tabs", {})
    users_tab = tabs.get("Użytkownicy") if isinstance(tabs, dict) else None
    if users_tab is None:
        return

    # profile_workforce_runtime wcześniej montował tu cały ProfileAdminNotebook.
    # Usuwamy wyłącznie jego widżety; sama zewnętrzna karta Użytkownicy zostaje.
    for child in list(users_tab.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    header = ttk.Frame(users_tab, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 2))
    ttk.Label(
        header,
        text="Konta użytkowników",
        style="WM.Muted.TLabel",
    ).pack(side="left")

    ttk.Button(
        header,
        text="Ustawienia profilu",
        command=lambda: _open_admin_window(panel, "Ustawienia profilu", ProfileSettingsPanel),
    ).pack(side="right", padx=(6, 0))
    add_help_button(
        header,
        "Otwiera ustawienia wspólne dla wszystkich profili. Nie tworzy kolejnej zakładki w panelu Brygadzisty.",
    ).pack(side="right", padx=(4, 0))

    ttk.Button(
        header,
        text="Rangi / role",
        command=lambda: _open_admin_window(panel, "Rangi / role", RolesAdminPanel),
    ).pack(side="right", padx=(6, 0))
    add_help_button(
        header,
        "Otwiera uprawnienia rang i ról. Uprawnienia konkretnego pracownika nadal edytujesz przez Edytuj przy jego koncie.",
    ).pack(side="right", padx=(4, 0))

    users_panel = UsersAdminPanel(users_tab)
    users_panel.pack(fill="both", expand=True)
    panel._wm_users_admin_panel = users_panel
    # Kompatybilność dla kodu, który sprawdza, czy administracja została zbudowana.
    panel._wm_profile_admin = users_panel
    panel._wm_users_admin_built = True
    panel._wm_users_admin_flat = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        import gui_profile_foreman as foreman
        cls = foreman.ForemanProfilePanel
    except Exception:
        return

    if getattr(cls, "_wm_flat_users_runtime", False):
        _INSTALLED = True
        return

    original_build = cls._build

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        _flatten_users_tab(self)
        return result

    cls._build = build
    cls._wm_flat_users_runtime = True
    _INSTALLED = True


__all__ = ["install"]
