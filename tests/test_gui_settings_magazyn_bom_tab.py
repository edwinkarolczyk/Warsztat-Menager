import tkinter as tk

import pytest

import gui_settings
from gui_magazyn_bom import MagazynBOM
from test_config_manager import make_manager


def test_magazyn_bom_tab_present(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "a", "type": "int", "default": 1, "group": "Ogólne"}
        ],
    }
    defaults = {"a": 1}
    make_manager(defaults=defaults, schema=schema)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(root)
    texts = [panel.nb.tab(t, "text") for t in panel.nb.tabs()]
    assert "Magazyn/BOM" in texts
    for tab_id in panel.nb.tabs():
        if panel.nb.tab(tab_id, "text") == "Magazyn/BOM":
            widget = panel.nb.nametowidget(tab_id)
            assert isinstance(widget, MagazynBOM)
            break
    root.destroy()

