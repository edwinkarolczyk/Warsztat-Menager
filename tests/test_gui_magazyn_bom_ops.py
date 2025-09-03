import json
import tkinter as tk

import pytest

import gui_magazyn_bom as gmb


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def _find_widget(root, cls, text=None):
    for w in root.winfo_children():
        if isinstance(w, cls) and (text is None or w.cget("text") == text):
            return w
    raise AssertionError(f"Widget {cls} not found")


def test_loads_and_saves_operations(tmp_path, monkeypatch, root):
    ops = [
        "Cięcie",
        "Gwintowanie",
        "Wiercenie",
        "Gięcie",
        "Spawanie",
        "Malowanie",
    ]

    class DummyCfg:
        def get(self, key, default=None):
            assert key == "czynnosci_technologiczne"
            return ops

    monkeypatch.setattr(gmb, "ConfigManager", lambda: DummyCfg())
    monkeypatch.setattr(gmb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(gmb.messagebox, "showinfo", lambda *a, **k: None)

    frame = gmb.make_window(root)
    lb = _find_widget(frame, tk.Listbox)
    assert lb.get(0, tk.END) == tuple(ops)

    entry = _find_widget(frame, tk.Entry)
    entry.insert(0, "PPX")
    lb.selection_set(1, 4)
    save_btn = _find_widget(frame, tk.Button, text="Zapisz")
    save_btn.invoke()

    data = json.loads((tmp_path / "PPX.json").read_text(encoding="utf-8"))
    assert data == {"kod": "PPX", "czynnosci": [ops[1], ops[4]]}
