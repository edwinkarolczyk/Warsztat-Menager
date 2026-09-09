# version: 1.0
from __future__ import annotations

import tkinter as tk

import gui_dyspozycje_creator as creator


def test_dyspozycje_creator_opens_for_add(monkeypatch):
    monkeypatch.setattr(creator, "load_tool_choices", lambda: [("001", "001 - Test")])
    monkeypatch.setattr(creator, "_load_user_logins", lambda: ["brygadzista"])

    root = tk.Tk()
    root.withdraw()
    try:
        win = creator.open_dyspozycje_creator(
            root,
            autor="brygadzista",
            context={"modul_zrodlowy": "test", "typ_dyspozycji": "narzedzie"},
        )
        root.update_idletasks()
        assert win.winfo_exists()
        assert "Dyspozycj" in win.title()
        win.destroy()
    finally:
        root.destroy()


def test_dyspozycje_creator_opens_for_edit(monkeypatch):
    monkeypatch.setattr(creator, "load_machine_choices", lambda: [("42", "42 - Test")])
    monkeypatch.setattr(creator, "_load_user_logins", lambda: ["brygadzista"])
    monkeypatch.setattr(creator, "_find_machine_preview", lambda _mid: {"ID": "42"})
    monkeypatch.setattr(creator, "_find_recent_dyspozycje_for_object", lambda *a, **k: [])

    root = tk.Tk()
    root.withdraw()
    try:
        win = creator.open_dyspozycje_creator(
            root,
            autor="brygadzista",
            context={
                "id": "D-test",
                "edit_mode": True,
                "typ_dyspozycji": "maszyna",
                "obiekt_id": "42",
                "opis": "Test",
            },
        )
        root.update_idletasks()
        assert win.winfo_exists()
        assert "Edytuj" in win.title()
        win.destroy()
    finally:
        root.destroy()
