import tkinter as tk
from tkinter import ttk

import pytest

import ustawienia_systemu
import gui_settings
import config_manager as cm
from test_config_manager import make_manager


def _setup_schema(make_manager, monkeypatch, options=None, tabs=None):
    if tabs is not None:
        schema = {"config_version": 1, "tabs": tabs}

        def collect_defaults(tab_list):
            for tab in tab_list:
                for group in tab.get("groups", []):
                    for field in group.get("fields", []):
                        defaults[field["key"]] = field.get("default")
                collect_defaults(tab.get("subtabs", []))

        defaults: dict[str, object] = {}
        collect_defaults(tabs)
    else:
        assert options is not None
        schema = {"config_version": 1, "options": options}
        defaults = {opt["key"]: opt.get("default") for opt in options}
    _, paths = make_manager(defaults=defaults, schema=schema)
    monkeypatch.setattr(ustawienia_systemu, "SCHEMA_PATH", paths["schema"])
    return paths
def test_open_and_switch_tabs(make_manager, monkeypatch):
    tabs = [
        {
            "id": f"t{i}",
            "title": f"Tab{i}",
            "groups": [
                {
                    "label": "G",
                    "fields": [
                        {"key": f"k{i}", "type": "int", "default": i}
                    ],
                }
            ],
        }
        for i in range(7)
    ]
    _setup_schema(make_manager, monkeypatch, tabs=tabs)
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
    tabs = [
        {
            "id": "t",
            "title": "Tab",
            "groups": [
                {"label": "G", "fields": [{"key": "a", "type": "int", "default": 1}]}
            ],
        }
    ]
    _setup_schema(make_manager, monkeypatch, tabs=tabs)
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
    tabs = [
        {
            "id": "t",
            "title": "Tab",
            "groups": [
                {"label": "G", "fields": [{"key": "a", "type": "int", "default": 1}]}
            ],
        }
    ]
    _setup_schema(make_manager, monkeypatch, tabs=tabs)
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


def test_open_and_switch_subtabs(make_manager, monkeypatch):
    tabs = [
        {
            "id": "t0",
            "title": "Main",
            "subtabs": [
                {
                    "id": "s0",
                    "title": "S0",
                    "groups": [
                        {
                            "label": "G1",
                            "fields": [{"key": "a", "type": "int", "default": 1}],
                        }
                    ],
                },
                {
                    "id": "s1",
                    "title": "S1",
                    "groups": [
                        {
                            "label": "G2",
                            "fields": [{"key": "b", "type": "int", "default": 2}],
                        }
                    ],
                },
            ],
        }
    ]
    _setup_schema(make_manager, monkeypatch, tabs=tabs)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    frame = ttk.Frame(root)
    frame.pack()
    ustawienia_systemu.panel_ustawien(root, frame)
    nb_outer = frame.winfo_children()[0]
    outer_tabs = nb_outer.tabs()
    assert len(outer_tabs) == 1
    outer_frame = root.nametowidget(outer_tabs[0])
    inner_nb = [child for child in outer_frame.winfo_children() if isinstance(child, ttk.Notebook)][0]
    inner_tabs = inner_nb.tabs()
    assert len(inner_tabs) == 2
    for t in inner_tabs:
        inner_nb.select(t)
        root.update_idletasks()
    root.destroy()


def test_magazyn_tab_has_subtabs(make_manager, monkeypatch):
    tabs = [
        {
            "id": "magazyn",
            "title": "Magazyn",
            "groups": [
                {
                    "label": "G",
                    "fields": [{"key": "a", "type": "int", "default": 1}],
                }
            ],
        }
    ]
    paths = _setup_schema(make_manager, monkeypatch, tabs=tabs)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(
        root, config_path=paths["config"], schema_path=paths["schema"]
    )
    nb = panel.nb
    tab_id = nb.tabs()[0]
    nb.select(tab_id)
    nb.event_generate("<<NotebookTabChanged>>")
    root.update_idletasks()
    mag_frame = root.nametowidget(tab_id)
    inner_nb = [
        child for child in mag_frame.winfo_children() if isinstance(child, ttk.Notebook)
    ][0]
    titles = [inner_nb.tab(t, "text") for t in inner_nb.tabs()]
    assert titles == ["Ustawienia magazynu", "Produkty (BOM)"]
    root.destroy()


def test_deprecated_not_rendered(make_manager, monkeypatch, capsys):
    tabs = [
        {
            "id": "t",
            "title": "T",
            "groups": [
                {
                    "label": "Old",
                    "deprecated": True,
                    "fields": [
                        {"key": "a", "type": "int", "default": 1}
                    ],
                },
                {
                    "label": "New",
                    "fields": [
                        {"key": "b", "type": "int", "default": 2, "deprecated": True},
                        {"key": "c", "type": "int", "default": 3},
                    ],
                },
            ],
        }
    ]
    paths = _setup_schema(make_manager, monkeypatch, tabs=tabs)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = gui_settings.SettingsPanel(
        root, config_path=paths["config"], schema_path=paths["schema"]
    )
    assert "a" not in panel.vars
    assert "b" not in panel.vars
    assert "c" in panel.vars
    out = capsys.readouterr().out
    assert out.count("[WM-DBG][SETTINGS] pomijam deprecated") == 2
    root.destroy()

