import tkinter as tk
import pytest

import gui_narzedzia


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter not available")
    r.withdraw()
    yield r
    r.destroy()


def _setup(monkeypatch):
    monkeypatch.setattr(
        gui_narzedzia.LZ, "get_collections", lambda: [{"id": "c1", "name": "C1"}]
    )
    monkeypatch.setattr(gui_narzedzia.LZ, "get_default_collection", lambda: "")
    monkeypatch.setattr(gui_narzedzia.LZ, "should_autocheck", lambda *a, **k: False)


def test_on_collection_change_handles_missing_data(monkeypatch, root):
    _setup(monkeypatch)
    data = gui_narzedzia.build_task_template(root)
    data["cb_type"].config(values=["T1"])
    data["cb_status"].config(values=["S1"])
    data["listbox"].insert(tk.END, "X")
    data["tasks_state"].append({"text": "X"})

    def boom(*args, **kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(gui_narzedzia.LZ, "get_tool_types", boom)
    calls = []
    monkeypatch.setattr(gui_narzedzia.messagebox, "showwarning", lambda *a, **k: calls.append(a))

    data["on_collection_change"]()

    assert data["cb_type"].cget("values") == ()
    assert data["cb_status"].cget("values") == ()
    assert data["listbox"].size() == 0
    assert data["tasks_state"] == []
    assert calls


def test_on_type_change_handles_missing_data(monkeypatch, root):
    _setup(monkeypatch)
    monkeypatch.setattr(
        gui_narzedzia.LZ,
        "get_tool_types",
        lambda collection=None: [{"id": "t1", "name": "T1"}],
    )
    data = gui_narzedzia.build_task_template(root)
    data["cb_collection"].set("C1")
    data["on_collection_change"]()

    data["cb_status"].config(values=["S1"])
    data["listbox"].insert(tk.END, "X")
    data["tasks_state"].append({"text": "X"})

    def boom(*args, **kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(gui_narzedzia.LZ, "get_statuses", boom)
    calls = []
    monkeypatch.setattr(gui_narzedzia.messagebox, "showwarning", lambda *a, **k: calls.append(a))

    data["cb_type"].set("T1")
    data["on_type_change"]()

    assert data["cb_status"].cget("values") == ()
    assert data["listbox"].size() == 0
    assert data["tasks_state"] == []
    assert calls


def test_on_status_change_handles_missing_data(monkeypatch, root):
    _setup(monkeypatch)
    monkeypatch.setattr(
        gui_narzedzia.LZ,
        "get_tool_types",
        lambda collection=None: [{"id": "t1", "name": "T1"}],
    )
    monkeypatch.setattr(
        gui_narzedzia.LZ,
        "get_statuses",
        lambda tid=None, collection=None: [{"id": "s1", "name": "S1"}],
    )
    data = gui_narzedzia.build_task_template(root)
    data["cb_collection"].set("C1")
    data["on_collection_change"]()
    data["cb_type"].set("T1")
    data["on_type_change"]()

    data["listbox"].insert(tk.END, "X")
    data["tasks_state"].append({"text": "X"})

    def boom(*args, **kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(gui_narzedzia.LZ, "get_tasks", boom)
    calls = []
    monkeypatch.setattr(gui_narzedzia.messagebox, "showwarning", lambda *a, **k: calls.append(a))

    data["cb_status"].set("S1")
    data["on_status_change"]()

    assert data["listbox"].size() == 0
    assert data["tasks_state"] == []
    assert calls
