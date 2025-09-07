import tkinter as tk
from tkinter import ttk

import pytest

from start import open_settings_window


def test_open_settings_window_has_notebook_tabs():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    try:
        open_settings_window(root)
        root.update_idletasks()
        toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert toplevels, "Settings window not created"
        win = toplevels[0]
        notebooks = [w for w in win.winfo_children() if isinstance(w, ttk.Notebook)]
        assert notebooks, "Notebook not found"
        nb = notebooks[0]
        assert len(nb.tabs()) >= 1, "Notebook should have at least one tab"
    finally:
        root.destroy()
