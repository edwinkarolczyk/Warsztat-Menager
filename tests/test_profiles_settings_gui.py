import json
import tkinter as tk
import pytest

import config_manager as cm
import gui_settings
from test_config_manager import make_manager  # noqa: F401


@pytest.fixture
def cfg_env(tmp_path, monkeypatch, make_manager):  # noqa: F811
    with open("settings_schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    with open("config.defaults.json", encoding="utf-8") as f:
        defaults = json.load(f)
    mgr, paths = make_manager(defaults=defaults, schema=schema)
    backup_dir = tmp_path / "backup_wersji"
    monkeypatch.setattr(cm, "BACKUP_DIR", str(backup_dir))
    cm.ConfigManager.refresh()
    return mgr, paths


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    return root


def test_profile_tab_renders_and_saves(cfg_env):
    mgr, paths = cfg_env
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    tab_texts = [panel.nb.tab(t, "text") for t in panel.nb.tabs()]
    assert "Profile" in tab_texts
    keys = [
        "profiles.tab_enabled",
        "profiles.show_name_in_header",
        "profiles.avatar_dir",
        "profiles.fields_visible",
        "profiles.fields_editable_by_user",
        "profiles.allow_pin_change",
        "profiles.task_default_deadline_days",
    ]
    for key in keys:
        assert key in panel.vars

    avatar_dir = str(paths["global"].parent / "avatars")
    panel.vars["profiles.tab_enabled"].set(False)
    panel.vars["profiles.show_name_in_header"].set(False)
    panel.vars["profiles.avatar_dir"].set(avatar_dir)
    panel.vars["profiles.fields_visible"].set("login\nnazwa")
    panel.vars["profiles.fields_editable_by_user"].set("telefon")
    panel.vars["profiles.allow_pin_change"].set(True)
    panel.vars["profiles.task_default_deadline_days"].set(14)
    panel.save()
    root.destroy()

    cm.ConfigManager.refresh()
    cfg = cm.ConfigManager()
    assert cfg.get("profiles.tab_enabled") is False
    assert cfg.get("profiles.show_name_in_header") is False
    assert cfg.get("profiles.avatar_dir") == avatar_dir
    assert cfg.get("profiles.fields_visible") == ["login", "nazwa"]
    assert cfg.get("profiles.fields_editable_by_user") == ["telefon"]
    assert cfg.get("profiles.allow_pin_change") is True
    assert cfg.get("profiles.task_default_deadline_days") == 14
