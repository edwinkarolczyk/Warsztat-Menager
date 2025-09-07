import tkinter as tk
from tkinter import ttk

import pytest

import ustawienia_systemu
import gui_settings
import config_manager as cm
from test_config_manager import make_manager


def _setup_schema(make_manager, monkeypatch, options):
    schema = {"config_version": 1, "options": options}
    defaults = {opt["key"]: opt.get("default") for opt in options}
    _, paths = make_manager(defaults=defaults, schema=schema)
    monkeypatch.setattr(ustawienia_systemu, "SCHEMA_PATH", paths["schema"])


def test_open_and_switch_tabs(make_manager, monkeypatch):
    options = [
        {"key": f"k{i}", "type": "int", "default": i, "group": f"Tab{i}"}
        for i in range(7)
    ]
    _setup_schema(make_manager, monkeypatch, options)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    frame = ttk.Frame(root)
    frame.pack()
    ustawienia_systemu.panel_ustawien(root, frame)
    nb = frame.winfo_children()[0]
    tabs = nb.tabs()
    assert len(tabs) == 7
    for tab in tabs:
        nb.select(tab)
        root.update_idletasks()
    root.destroy()


def test_unsaved_changes_warning(make_manager, monkeypatch):
    options = [
        {"key": "a", "type": "int", "default": 1, "group": "Tab"}
    ]
    _setup_schema(make_manager, monkeypatch, options)
    calls = {"asked": 0}

    def fake_askyesno(*_args, **_kwargs):
        calls["asked"] += 1
        return False

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
    tab = root.nametowidget(nb.tabs()[0])
    field = tab.winfo_children()[0]
    widget = field.winfo_children()[1]
    var_name = widget.cget("textvariable")
    root.setvar(var_name, 2)
    root.update_idletasks()
    close_cmd = root.tk.call("wm", "protocol", root._w, "WM_DELETE_WINDOW")
    root.tk.call(close_cmd)
    assert calls["asked"] == 1
    root.destroy()


def test_save_creates_backup(make_manager, tmp_path, monkeypatch):
    options = [
        {"key": "a", "type": "int", "default": 1, "group": "Tab"}
    ]
    _setup_schema(make_manager, monkeypatch, options)
    backup_dir = tmp_path / "backup_wersji"
    monkeypatch.setattr(cm, "BACKUP_DIR", str(backup_dir))
    cm.ConfigManager.refresh()

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["a"].set(2)
    panel.save()
    files = list(backup_dir.glob("config_*.json"))
    assert files
    root.destroy()

