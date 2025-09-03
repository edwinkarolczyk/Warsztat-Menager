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
    nb = frame.winfo_children()[0]
    tab1 = nb.winfo_children()[1]
    frm = tab1.winfo_children()[0]

    label_row = None
    for child in frm.winfo_children():
        if isinstance(child, ttk.Label) and child.cget("text") == "Gałąź git push:":
            label_row = child.grid_info()["row"]
            break
    assert label_row is not None
    push_entry = frm.grid_slaves(row=label_row, column=1)[0]
    push_entry.delete(0, "end")
    push_entry.insert(0, "feature-branch")

    save_btn = None
    for child in frm.winfo_children():
        if isinstance(child, ttk.Button) and child.cget("text") == "Zapisz":
            save_btn = child
            break
    assert save_btn is not None
    save_btn.invoke()
    root.destroy()

    reloaded = cm.ConfigManager.refresh()
    assert reloaded.get("updates.push_branch") == "feature-branch"
