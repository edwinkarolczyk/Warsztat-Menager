import json
import tkinter as tk
import types

import pytest

import config_manager as cm
import gui_settings
import gui_logowanie
from test_config_manager import make_manager  # noqa: F401
from test_gui_logowanie import (
    DummyElements,
    DummyLabel,
    DummyRoot,
    DummyWidget,
)


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


def _setup_dummy_login(monkeypatch):
    elements = DummyElements()
    buttons = []

    def fake_label(master=None, **kwargs):
        lbl = DummyLabel(**kwargs)
        elements.append(lbl)
        return lbl

    def fake_button(master=None, **kwargs):
        btn = DummyWidget(**kwargs)
        buttons.append(btn)
        return btn

    fake_ttk = types.SimpleNamespace(
        Frame=DummyWidget,
        Label=fake_label,
        Entry=DummyWidget,
        Button=fake_button,
        Style=DummyWidget,
    )
    fake_tk = types.SimpleNamespace(Canvas=DummyWidget, Label=DummyLabel)

    monkeypatch.setattr(gui_logowanie, "ttk", fake_ttk)
    monkeypatch.setattr(gui_logowanie, "tk", fake_tk)
    monkeypatch.setattr(gui_logowanie, "apply_theme", lambda root: None)
    monkeypatch.setattr(
        gui_logowanie.gui_panel,
        "_shift_progress",
        lambda now: (0, False),
    )
    monkeypatch.setattr(
        gui_logowanie.gui_panel,
        "_shift_bounds",
        lambda now: (now, now),
    )

    elements.buttons = buttons
    return elements


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


def test_enable_pinless_login_from_settings(cfg_env, monkeypatch):
    root = _make_root()
    panel = gui_settings.SettingsPanel(root)
    panel.vars["auth.pinless_brygadzista"].set(True)
    panel.save()
    root.destroy()

    with open(cm.GLOBAL_PATH, encoding="utf-8") as f:
        stored = json.load(f)
    assert stored["auth"]["pinless_brygadzista"] is True

    cm.ConfigManager.refresh()

    elements = _setup_dummy_login(monkeypatch)
    login_root = DummyRoot()
    gui_logowanie.ekran_logowania(root=login_root)

    assert any(
        btn.kwargs.get("text") == "Logowanie bez PIN"
        for btn in elements.buttons
    )
