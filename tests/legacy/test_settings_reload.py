import json
import tkinter as tk
from tkinter import ttk

import pytest

import ustawienia_systemu as us
import config_manager
import gui_settings_legacy

us.SettingsPanel = gui_settings_legacy.SettingsPanel
us.messagebox = gui_settings_legacy.messagebox


def _desc(cfg, key):
    for opt in cfg.schema.get("options", []):
        if opt.get("key") == key:
            return opt.get("description")
    return None


def test_refresh_panel_reload_schema(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    frame = ttk.Frame(root)
    frame.pack()
    # build initial panel
    us.panel_ustawien(root, frame)
    cfg_before = config_manager.ConfigManager()
    before_desc = _desc(cfg_before, "ui.theme")

    # prepare modified schema
    with us.SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    for opt in schema["options"]:
        if opt["key"] == "ui.theme":
            opt["description"] = "Nowy opis"
            break
    new_schema = tmp_path / "settings_schema.json"
    with new_schema.open("w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    monkeypatch.setattr(us, "SCHEMA_PATH", new_schema)
    monkeypatch.setattr(config_manager, "SCHEMA_PATH", str(new_schema))

    us.refresh_panel(root, frame)
    cfg_after = config_manager.ConfigManager()
    after_desc = _desc(cfg_after, "ui.theme")
    assert after_desc == "Nowy opis" and before_desc != after_desc
    root.destroy()
