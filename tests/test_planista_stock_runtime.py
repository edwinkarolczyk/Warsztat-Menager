# version: 1.0
from pathlib import Path

import planista_stock_runtime as PSR


class _FakeLM:
    saved = None

    @classmethod
    def save_magazyn(cls, data):
        cls.saved = data


def test_legacy_planista_stock_moves_to_missing_physical_card(monkeypatch):
    definitions = {
        "SUR-006": {
            "kod": "SUR-006",
            "nazwa": "Drut - 6",
            "rodzaj": "Drut",
            "rozmiar": "6",
            "stan": 6000,
            "liczba_sztang": 2,
            "dlugosc_sztangi_mm": 3000,
            "jednostka": "mm",
        }
    }
    items = {}
    data = {"items": items, "meta": {}}
    saved_defs = {}

    monkeypatch.setattr(
        PSR, "_load_raw_definitions", lambda: (Path("surowce.json"), definitions)
    )
    monkeypatch.setattr(PSR, "_physical_items", lambda: (_FakeLM, data, items))
    monkeypatch.setattr(
        PSR,
        "_save_raw_definitions",
        lambda _path, records: saved_defs.update(records),
    )

    PSR.sync_raw_material_cards()

    assert items["SUR-006"]["stan"] == 6000
    assert items["SUR-006"]["jednostka"] == "mm"
    assert items["SUR-006"]["powiazanie_planista"] is True
    assert "stan" not in saved_defs["SUR-006"]
    assert "liczba_sztang" not in saved_defs["SUR-006"]


def test_existing_physical_stock_wins_over_legacy_planista_value(monkeypatch):
    definitions = {
        "SUR-001": {
            "kod": "SUR-001",
            "nazwa": "Drut - 8",
            "rodzaj": "Drut",
            "rozmiar": "8",
            "stan": 99999,
            "liczba_sztang": 99,
            "dlugosc_sztangi_mm": 3000,
            "jednostka": "mm",
        }
    }
    items = {
        "SUR-001": {
            "id": "SUR-001",
            "stan": 1200,
            "rezerwacje": 200,
            "lokalizacja": "Regał A1",
            "jednostka": "mm",
        }
    }
    data = {"items": items, "meta": {}}

    monkeypatch.setattr(
        PSR, "_load_raw_definitions", lambda: (Path("surowce.json"), definitions)
    )
    monkeypatch.setattr(PSR, "_physical_items", lambda: (_FakeLM, data, items))
    monkeypatch.setattr(PSR, "_save_raw_definitions", lambda _path, _records: None)

    PSR.sync_raw_material_cards()

    assert items["SUR-001"]["stan"] == 1200
    assert items["SUR-001"]["rezerwacje"] == 200
    assert items["SUR-001"]["lokalizacja"] == "Regał A1"
    assert items["SUR-001"]["nazwa"] == "Drut - 8"
    assert items["SUR-001"]["rozmiar"] == "8"


def test_planista_stock_view_reads_physical_stock_and_reservations():
    view = PSR._stock_view(
        "SUR-001",
        {"dlugosc_sztangi_mm": 3000, "jednostka": "mm"},
        {
            "SUR-001": {
                "stan": 30000,
                "rezerwacje": 9000,
                "jednostka": "mm",
                "lokalizacja": "Regał B2",
            }
        },
    )

    assert view["linked"] is True
    assert view["stock"] == 30000
    assert view["reserved"] == 9000
    assert view["available"] == 21000
    assert view["bars"] == 10
    assert view["location"] == "Regał B2"


def test_gui_planowanie_installs_stock_runtime():
    source = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "install_planista_stock_runtime" in source
