# version: 1.3
import tkinter as tk
from tkinter import ttk

import gui_profile  # noqa: F401 - instaluje runtime panelu brygadzisty
import ustawienia_uzytkownicy as users_settings
from gui_profile_foreman import ForemanProfilePanel
from profile_admin_ui import UsersAdminPanel


def _visible_texts(notebook):
    return [
        str(notebook.tab(tab_id, "text"))
        for tab_id in notebook.tabs()
        if str(notebook.tab(tab_id, "state")) != "hidden"
    ]


def test_foreman_users_tab_is_flat_without_nested_admin_notebook(monkeypatch):
    monkeypatch.setattr(users_settings, "_load_users", lambda: [])
    monkeypatch.setattr(ForemanProfilePanel, "refresh_data", lambda self: None)

    root = tk.Tk()
    try:
        panel = ForemanProfilePanel(root)
        panel.pack(fill="both", expand=True)
        root.update_idletasks()

        visible = _visible_texts(panel.notebook)
        assert visible == [
            "Pulpit", "Zespół", "Obecność", "Urlopy",
            "Użytkownicy", "Opinie", "Statystyki",
        ]
        assert "Profile" not in panel._tabs
        assert "Zadania" not in visible
        assert "Sprzęt" not in visible
        assert "Profile" not in visible

        users_tab = panel._tabs["Użytkownicy"]
        admin = panel._wm_users_admin_panel
        assert isinstance(admin, UsersAdminPanel)
        assert panel._wm_profile_admin is admin
        assert panel._wm_users_admin_flat is True

        # Najważniejsza regresja ze screena: zewnętrzne Użytkownicy nie mogą
        # zawierać drugiego Notebooka Użytkownicy | Profile | Rangi.
        assert not any(isinstance(child, ttk.Notebook) for child in users_tab.winfo_children())
    finally:
        root.destroy()
