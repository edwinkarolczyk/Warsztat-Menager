import pytest
import tkinter as tk
from tkinter import ttk

import config_manager as cm
import ustawienia_systemu
from test_config_manager import make_manager


def test_push_branch_config_value(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "updates.push_branch", "type": "string"}
        ],
    }
    defaults = {"updates": {"push_branch": "git-push"}}
    mgr, _ = make_manager(defaults=defaults, schema=schema)
    assert isinstance(mgr.get("updates.push_branch"), str)


def test_push_branch_ui_saves_value(make_manager):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "updates.push_branch", "type": "string"}
        ],
    }
    defaults = {"updates": {"push_branch": "git-push"}}
    make_manager(defaults=defaults, schema=schema)

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    frame = tk.Frame(root)
    frame.pack()

    ustawienia_systemu.panel_ustawien(root, frame)
    def _find_widget(widget, cls, text):
        for child in widget.winfo_children():
            if isinstance(child, cls) and child.cget("text") == text:
                return child
            result = _find_widget(child, cls, text)
            if result is not None:
                return result
        return None

    label = _find_widget(frame, ttk.Label, "Gałąź do wysyłki")
    assert label is not None
    row = label.grid_info()["row"]
    push_entry = label.master.grid_slaves(row=row, column=1)[0]
    push_entry.delete(0, "end")
    push_entry.insert(0, "feature-branch")

    save_btn = _find_widget(frame, ttk.Button, "Zapisz")
    assert save_btn is not None
    save_btn.invoke()
    root.destroy()

    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("updates.push_branch") == "feature-branch"
