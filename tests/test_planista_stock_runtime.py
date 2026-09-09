# version: 1.1
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


def test_delete_removes_empty_linked_warehouse_card(tmp_path, monkeypatch):
    definitions_path = tmp_path / "surowce.json"
    definitions_path.write_text('[{"kod": "SUR-001"}]', encoding="utf-8")
    items = {
        "SUR-001": {
            "stan": 0,
            "rezerwacje": 0,
            "powiazanie_planista": True,
        }
    }
    data = {"items": items, "meta": {}}
    _FakeLM.saved = None
    monkeypatch.setattr(PSR, "_raw_file", lambda: definitions_path)
    monkeypatch.setattr(PSR, "_physical_items", lambda: (_FakeLM, data, items))

    called = []
    PSR._delete_linked_raw_card("SUR-001", lambda: called.append("definition"))

    assert called == ["definition"]
    assert "SUR-001" not in items
    assert "SUR-001" not in _FakeLM.saved["items"]


def test_delete_blocks_linked_card_with_stock(tmp_path, monkeypatch):
    definitions_path = tmp_path / "surowce.json"
    definitions_path.write_text('[{"kod": "SUR-001"}]', encoding="utf-8")
    items = {
        "SUR-001": {
            "stan": 6000,
            "rezerwacje": 0,
            "powiazanie_planista": True,
        }
    }
    data = {"items": items, "meta": {}}
    monkeypatch.setattr(PSR, "_raw_file", lambda: definitions_path)
    monkeypatch.setattr(PSR, "_physical_items", lambda: (_FakeLM, data, items))

    called = []
    try:
        PSR._delete_linked_raw_card("SUR-001", lambda: called.append("definition"))
    except ValueError as exc:
        assert "stan 6000" in str(exc)
    else:
        raise AssertionError("Usunięcie surowca ze stanem powinno być zablokowane")
    assert called == []
    assert "SUR-001" in items


def test_delete_rolls_back_definition_when_warehouse_save_fails(tmp_path, monkeypatch):
    definitions_path = tmp_path / "surowce.json"
    original = '[{"kod": "SUR-001"}]'
    definitions_path.write_text(original, encoding="utf-8")
    items = {
        "SUR-001": {
            "stan": 0,
            "rezerwacje": 0,
            "powiazanie_planista": True,
        }
    }
    data = {"items": items, "meta": {}}

    class FailingLM:
        calls = 0

        @classmethod
        def save_magazyn(cls, _data):
            cls.calls += 1
            if cls.calls == 1:
                raise OSError("brak zapisu")

    monkeypatch.setattr(PSR, "_raw_file", lambda: definitions_path)
    monkeypatch.setattr(PSR, "_physical_items", lambda: (FailingLM, data, items))

    def delete_definition():
        definitions_path.write_text("[]", encoding="utf-8")

    try:
        PSR._delete_linked_raw_card("SUR-001", delete_definition)
    except OSError:
        pass
    else:
        raise AssertionError("Błąd zapisu Magazynu powinien zostać przekazany")

    assert definitions_path.read_text(encoding="utf-8") == original
    assert FailingLM.calls == 2
