# version: 1.0
from __future__ import annotations

import tkinter as tk

import dyspozycje_permissions_runtime as runtime
import ustawienia_uzytkownicy as settings


def _texts(widget):
    out = []
    for child in widget.winfo_children():
        try:
            text = str(child.cget("text") or "")
        except Exception:
            text = ""
        if text:
            out.append(text)
        out.extend(_texts(child))
    return out


def test_roles_tab_shows_dyspozycje_action_permissions(monkeypatch):
    monkeypatch.setattr(settings, "_load_users", lambda: [])
    runtime._INSTALLED = False
    runtime.install()

    root = tk.Tk()
    root.withdraw()
    try:
        panel = settings.SettingsProfilesTab(root)
        panel.pack(fill="both", expand=True)
        root.update_idletasks()
        texts = _texts(panel)
        assert "Akcje Dyspozycji" in texts
        assert "Dodawanie Dyspozycji" in texts
        assert "Edycja Dyspozycji" in texts
        panel.destroy()
    finally:
        root.destroy()


def test_runtime_uses_one_active_creator_for_old_wizard_entry():
    runtime._INSTALLED = False
    runtime.install()

    import wm.dyspo_wizard as old_wizard

    assert callable(old_wizard.open_dyspo_wizard)
    assert old_wizard.open_dyspo_wizard.__module__ == "dyspozycje_permissions_runtime"
