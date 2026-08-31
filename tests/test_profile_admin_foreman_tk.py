# version: 1.0
import tkinter as tk

import gui_profile  # noqa: F401 - instaluje runtime panelu brygadzisty
import ustawienia_uzytkownicy as users_settings
from gui_profile_foreman import ForemanProfilePanel


def _texts(notebook):
    return [str(notebook.tab(tab_id, "text")) for tab_id in notebook.tabs()]


def test_foreman_profile_tab_uses_unified_admin_notebook(monkeypatch):
    monkeypatch.setattr(users_settings, "_load_users", lambda: [])
    monkeypatch.setattr(ForemanProfilePanel, "refresh_data", lambda self: None)

    root = tk.Tk()
    try:
        panel = ForemanProfilePanel(root)
        panel.pack(fill="both", expand=True)
        root.update_idletasks()

        assert "Profile" in panel._tabs
        admin = panel._wm_profile_admin
        assert _texts(admin.nb) == ["Użytkownicy", "Profile", "Rangi"]
        assert panel._tabs["Profile"] is not admin
    finally:
        root.destroy()
