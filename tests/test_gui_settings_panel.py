import tkinter as tk

import pytest

import config_manager as cm
import gui_settings_legacy as gui_settings
from test_config_manager import make_manager


def test_restore_defaults(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "a", "type": "int", "default": 1},
            {"key": "b", "type": "string", "default": "x"},
        ],
    }
    defaults = {"a": 1, "b": "x"}
    make_manager(defaults=defaults, schema=schema)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["a"].set(5)
    panel.vars["b"].set("y")
    panel.restore_defaults()
    assert panel.vars["a"].get() == 1
    assert panel.vars["b"].get() == "x"
    root.destroy()


def test_close_prompts_on_change(monkeypatch, make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "a", "type": "int", "default": 1}],
    }
    defaults = {"a": 1}
    make_manager(defaults=defaults, schema=schema)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["a"].set(2)
    called = {"asked": False}

    def fake_askyesno(*_args, **_kwargs):
        called["asked"] = True
        return False

    monkeypatch.setattr(gui_settings.messagebox, "askyesno", fake_askyesno)
    panel.on_close()
    assert called["asked"] is True
    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("a") == 1
