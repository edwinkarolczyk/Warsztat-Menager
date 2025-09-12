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

    def fake_open_window(parent, config, *args, **kwargs):
        called["args"] = (parent, config)

    monkeypatch.setattr(gm, "open_window", fake_open_window)
    parent = types.SimpleNamespace(config={"x": 1})
    gm.open_panel_magazyn(parent)
    assert called["args"] == (parent, {"x": 1})


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

