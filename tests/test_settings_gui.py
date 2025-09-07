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
    make_manager(defaults=defaults, schema=schema)
    backup_dir = tmp_path / "backup_wersji"
    monkeypatch.setattr(cm, "BACKUP_DIR", str(backup_dir))
    cm.ConfigManager.refresh()
    return backup_dir


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    return root


def test_switch_tabs(cfg_env, capsys):
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    tabs = panel.nb.tabs()
    assert len(tabs) >= 7
    for tab in tabs[:7]:
        panel.nb.select(tab)
        root.update_idletasks()
    print("[WM-DBG] switched tabs")
    out = capsys.readouterr().out
    assert "[WM-DBG]" in out
    root.destroy()


def test_change_and_close_warn(cfg_env, monkeypatch, capsys):
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["ui.theme"].set("light")
    called = {"asked": False}

    def fake_askyesno(*_a, **_k):
        called["asked"] = True
        return True

    monkeypatch.setattr(gui_settings.messagebox, "askyesno", fake_askyesno)
    panel.on_close()
    assert called["asked"] is True
    print("[WM-DBG] close warn")
    out = capsys.readouterr().out
    assert "[WM-DBG]" in out


def test_save_creates_backup(cfg_env, capsys):
    backup_dir = cfg_env
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    panel.save()
    assert any(backup_dir.iterdir())
    print("[WM-DBG] saved config")
    out = capsys.readouterr().out
    assert "[WM-DBG]" in out
    root.destroy()


def test_save_admin_pin(cfg_env):
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["secrets.admin_pin"].set("4321")
    panel.save()
    with open(cm.GLOBAL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data["secrets"]["admin_pin"] == "4321"
    root.destroy()
