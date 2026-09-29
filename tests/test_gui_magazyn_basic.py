# version: 1.0
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
    assert row == (
        "ID1",
        "Elem",
        "-",
        "5",
        "0",
        "5",
        "-",
        "-",
        "kg",
        "-",
        "-",
    )


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



def test_format_row_avoids_scientific_notation_and_shows_bar_data():
    item = {
        "typ": "surowiec",
        "rozmiar": "10",
        "nazwa": "Śruba M10 - 10",
        "stan": 9_999_910,
        "rezerwacje": 2_220,
        "jednostka": "mm",
        "dlugosc_sztangi_mm": 10,
        "zadania": [],
    }

    row = gm._format_row("SUR-015", item)

    assert row[1] == "Śruba M10"
    assert row[3] == "9 999 910"
    assert row[4] == "2 220"
    assert row[5] == "9 997 690"
    assert row[6] == "999 769"
    assert row[7] == "10 mm (0,01 m)"


def test_existing_fi_name_is_presented_with_diameter_symbol():
    row = gm._format_row(
        "SUR-001",
        {
            "typ": "surowiec",
            "nazwa": "Pręt Fi 8",
            "rozmiar": "8",
            "stan": 6000,
            "jednostka": "mm",
            "dlugosc_sztangi_mm": 6000,
        },
    )
    assert row[1] == "Pręt Ø8"
