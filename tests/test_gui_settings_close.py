import tkinter as tk
from tkinter import ttk

import pytest

import ustawienia_systemu


def test_settings_window_closes_cleanly(monkeypatch):
    monkeypatch.setattr(ustawienia_systemu, "apply_theme", lambda *a, **k: None)

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()

    frame = ttk.Frame(root)
    frame.pack()

    ustawienia_systemu.panel_ustawien(root, frame)

    frame.destroy()
    root.update_idletasks()
    root.destroy()

    assert not root.winfo_exists()
