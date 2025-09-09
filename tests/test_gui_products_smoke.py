import tkinter as tk
from tkinter import ttk, filedialog

import pytest

import gui_settings
from tools import patcher


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def _find_widget(widget, cls, text=None):
    for w in widget.winfo_children():
        if isinstance(w, cls) and (text is None or w.cget("text") == text):
            return w
        try:
            found = _find_widget(w, cls, text)
            if found:
                return found
        except AssertionError:
            pass
    raise AssertionError(f"Widget {cls} not found")


def test_products_tab_headers(root):
    panel = gui_settings.SettingsPanel(root)
    panel.nb.select(panel.products_tab)
    root.update_idletasks()

    products_cols = [
        panel.products_tab.products_tree.heading(c)["text"]
        for c in panel.products_tab.products_tree["columns"]
    ]
    assert products_cols == ["Symbol", "Nazwa", "Polprodukty", "Czynnosci"]

    pol_cols = [
        panel.products_tab.pol_tree.heading(c)["text"]
        for c in panel.products_tab.pol_tree["columns"]
    ]
    assert pol_cols == [
        "ID",
        "Nazwa",
        "Rodzaj",
        "Surowce (#)",
        "Czynności (#)",
    ]

    mat_cols = [
        panel.products_tab.mat_tree.heading(c)["text"]
        for c in panel.products_tab.mat_tree["columns"]
    ]
    assert mat_cols == [
        "ID",
        "Typ",
        "Rozmiar",
        "Długość",
        "Jednostka",
        "Stan",
    ]


def test_patch_tab_dry_run(monkeypatch, root):
    called = {}

    def fake_apply(path, dry_run):
        called["path"] = path
        called["dry_run"] = dry_run

    monkeypatch.setattr(patcher, "apply_patch", fake_apply)
    monkeypatch.setattr(patcher, "get_commits", lambda: [])
    monkeypatch.setattr(patcher, "rollback_to", lambda *_a, **_k: None)
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **_k: "dummy.patch")

    panel = gui_settings.SettingsPanel(root)
    tab_frame = None
    for tab in panel.nb.tabs():
        if panel.nb.tab(tab, "text") == "Aktualizacje & Kopie":
            panel.nb.select(tab)
            tab_frame = panel.nb.nametowidget(tab)
            break
    assert tab_frame is not None

    btn = _find_widget(tab_frame, ttk.Button, "Sprawdź patch (dry-run)")
    btn.invoke()
    assert called.get("dry_run") is True
