import tkinter as tk
from tkinter import ttk

import pytest

import config_manager as cm
import ustawienia_systemu
from test_config_manager import make_manager


def test_settings_single_prompt(make_manager, monkeypatch):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "auth.session_timeout_min", "type": "int"},
            {"key": "auth.pin_length", "type": "int"},
        ],
    }
    defaults = {"auth": {"session_timeout_min": 30, "pin_length": 4}}
    make_manager(defaults=defaults, schema=schema)

    monkeypatch.setattr(ustawienia_systemu, "apply_theme", lambda *a, **k: None)
    calls = {"count": 0}

    def fake_askyesno(title, message):
        calls["count"] += 1
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
    sp_pin = [
        w
        for w in frm_auth.winfo_children()
        if w.winfo_class() == "TSpinbox" and w.grid_info().get("row") == 2
    ][0]
    var_timeout = sp_timeout.cget("textvariable")
    var_pin = sp_pin.cget("textvariable")

    root.setvar(var_timeout, 99)
    root.setvar(var_pin, 7)
    root.update_idletasks()

    close_cmd = root.tk.call("wm", "protocol", root._w, "WM_DELETE_WINDOW")
    root.tk.call(close_cmd)

    assert calls["count"] == 1
    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("auth.session_timeout_min") == 99
    assert reloaded.get("auth.pin_length") == 7

