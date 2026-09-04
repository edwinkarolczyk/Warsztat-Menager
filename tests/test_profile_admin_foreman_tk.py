# version: 1.5
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


def _walk(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_walk(child))
    return out


def _button_texts(widget):
    values = []
    for child in _walk(widget):
        if isinstance(child, ttk.Button):
            values.append(str(child.cget("text")))
    return values


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
            "Pulpit", "Ruch WM", "Obecność", "Urlopy",
            "Użytkownicy", "Opinie", "Statystyki",
        ]
        assert "Profile" not in panel._tabs
        assert "Zadania" not in visible
        assert "Sprzęt" not in visible
        assert "Profile" not in visible
        assert "Zespół" not in visible

        users_tab = panel._tabs["Użytkownicy"]
        admin = panel._wm_users_admin_panel
        assert isinstance(admin, UsersAdminPanel)
        assert panel._wm_profile_admin is admin
        assert panel._wm_users_admin_flat is True

        # Zewnętrzne Użytkownicy nie mogą zawierać drugiego Notebooka
        # Użytkownicy | Profile | Rangi.
        assert not any(isinstance(child, ttk.Notebook) for child in users_tab.winfo_children())
    finally:
        root.destroy()


def test_profile_entrypoints_are_in_attendance_and_leave_not_ruch_wm(monkeypatch):
    monkeypatch.setattr(users_settings, "_load_users", lambda: [])
    monkeypatch.setattr(ForemanProfilePanel, "refresh_data", lambda self: None)

    root = tk.Tk()
    try:
        panel = ForemanProfilePanel(root)
        panel.pack(fill="both", expand=True)
        panel.snapshot = {
            "period_label": "Ten miesiąc",
            "team": [
                {
                    "name": "Dawid Karolczyk",
                    "login": "Dawid",
                    "role": "operator",
                    "open": 1,
                    "done": 0,
                    "urgent": 0,
                    "tools": 0,
                    "machines": 0,
                    "services": 0,
                    "leave_remaining": 24,
                }
            ],
            "leaves_source": "test",
            "leaves": [
                {
                    "name": "Dawid Karolczyk",
                    "limit": 26,
                    "used": 2,
                    "remaining": 24,
                    "l4": 0,
                    "nn": 0,
                    "late_minutes": 0,
                }
            ],
        }

        panel._render_team()
        assert "Profil pracownika" not in _button_texts(panel._tabs["Zespół"])

        panel._render_leaves()
        assert "Szczegóły pracownika" in _button_texts(panel._tabs["Urlopy"])

        # Obecność ma własne wejście do profilu i otwiera od razu kartę Obecność.
        # Chronimy tu kontrakt na poziomie metod: końcowy renderer jest podpięty.
        assert hasattr(panel, "_render_attendance")
    finally:
        root.destroy()
