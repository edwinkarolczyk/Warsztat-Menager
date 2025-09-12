import types

import gui_magazyn as gm


def test_format_row_handles_optional_fields():
    item = {
        "typ": "",
        "nazwa": "Elem",
        "stan": "5",
        "jednostka": "kg",
        "zadania": ["cut", " weld ", ""],
    }
    row = gm._format_row("ID1", item)
    assert row == ("ID1", "-", "-", "Elem", "5 kg", "cut, weld")


def test_open_panel_magazyn_passes_parent_config(monkeypatch):
    called = {}
    fake_container = object()

    class DummyFrame:
        def __init__(self, master, config=None):
            called["args"] = (master, config)
            called["frame"] = self

        def pack(self, *a, **kw):
            called["packed"] = True

    monkeypatch.setattr(gm, "MagazynFrame", DummyFrame)
    monkeypatch.setattr(
        gm, "_resolve_container", lambda parent, notebook=None, container=None: fake_container
    )

    parent = types.SimpleNamespace(config={"x": 1})
    frame = gm.open_panel_magazyn(parent)
    assert called["args"] == (fake_container, {"x": 1})
    assert frame is called["frame"]


def test_load_data_prefers_io(monkeypatch):
    class DummyIO:
        @staticmethod
        def load():
            return {"items": {"A": {"nazwa": "A"}}, "meta": {"order": ["A"]}}

    monkeypatch.setattr(gm, "magazyn_io", DummyIO)
    monkeypatch.setattr(gm, "HAVE_MAG_IO", True)
    items, order = gm._load_data()
    assert items == {"A": {"nazwa": "A"}}
    assert order == ["A"]

