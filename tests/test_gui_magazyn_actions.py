import tkinter as tk

import pytest

from gui_magazyn import PanelMagazyn
import gui_magazyn_add
import gui_magazyn_pz


def _dummy_open(parent):
    win = tk.Toplevel(parent)
    parent.after(50, win.destroy)
    return win


def _count_toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def test_act_dodaj_spawns_toplevel(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = PanelMagazyn(root)
    monkeypatch.setattr(gui_magazyn_add, "open_window", _dummy_open)
    panel._act_dodaj()
    root.update()
    assert _count_toplevels(root)
    root.destroy()


def test_act_przyjecie_spawns_toplevel(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    root.withdraw()
    panel = PanelMagazyn(root)
    monkeypatch.setattr(gui_magazyn_pz, "open_window", _dummy_open)
    panel._act_przyjecie()
    root.update()
    assert _count_toplevels(root)
    root.destroy()
