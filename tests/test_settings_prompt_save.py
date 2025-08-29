import tkinter as tk
from tkinter import ttk

import pytest

import config_manager as cm
import ustawienia_systemu
from test_config_manager import make_manager


def test_auth_timeout_save_prompt(make_manager, monkeypatch):
    schema = {
        "config_version": 1,
        "options": [{"key": "auth.session_timeout_min", "type": "int"}],
    }
    defaults = {"auth": {"session_timeout_min": 30}}
    make_manager(defaults=defaults, schema=schema)

    monkeypatch.setattr(ustawienia_systemu, "apply_theme", lambda *a, **k: None)
    called = {}

    def fake_askyesno(title, message):
        called["asked"] = True
        return True

    monkeypatch.setattr(ustawienia_systemu.messagebox, "askyesno", fake_askyesno)

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    frame = ttk.Frame(root)
    frame.pack()

    ustawienia_systemu.panel_ustawien(root, frame)
    nb = frame.winfo_children()[0]
    tab_auth = root.nametowidget(nb.tabs()[2])
    frm_auth = tab_auth.winfo_children()[0]
    sp_timeout = [
        w
        for w in frm_auth.winfo_children()
        if w.winfo_class() == "TSpinbox" and w.grid_info().get("row") == 1
    ][0]
    var_name = sp_timeout.cget("textvariable")

    root.setvar(var_name, 99)
    root.update_idletasks()
    root.destroy()

    assert called.get("asked") is True
    reloaded = cm.ConfigManager()
    assert reloaded.get("auth.session_timeout_min") == 99

