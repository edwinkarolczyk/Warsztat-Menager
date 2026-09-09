# Plik: tests/test_production_bom_reservation.py
# Wersja: 1.0

import json

import bom
import zlecenia_logika as zl


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_banaszak_product_expands_through_semi_finished_to_raw_material(tmp_path, monkeypatch):
    monkeypatch.setattr(bom, "DATA_DIR", tmp_path)

    _write(
        tmp_path / "produkty" / "1.775.250.json",
        {
            "kod": "1.775.250",
            "nazwa": "Banaszak",
            "polprodukty": [
                {"kod": "POL-OSKA", "ilosc_na_szt": 2},
                {"kod": "POL-ZAW", "ilosc_na_szt": 1},
            ],
        },
    )
    _write(
        tmp_path / "polprodukty" / "POL-OSKA.json",
        {
            "kod": "POL-OSKA",
            "nazwa": "Ośka banaszak",
            "surowiec": {"kod": "SUR-FI8", "ilosc_na_szt": 369, "jednostka": "mm"},
            "czynnosci": ["toczenie", "gwintowanie M8"],
            "norma_strat_procent": 0,
        },
    )
    _write(
        tmp_path / "polprodukty" / "POL-ZAW.json",
        {
            "kod": "POL-ZAW",
            "nazwa": "Zawleczka banaszak",
            "surowiec": {"kod": "SUR-FI2", "ilosc_na_szt": 50, "jednostka": "mm"},
            "czynnosci": ["gięcie"],
        },
    )
    _write(
        tmp_path / "magazyn" / "surowce.json",
        [
            {"id": "SUR-FI8", "kod": "SUR-FI8", "nazwa": "Drut fi8", "jednostka": "mm"},
            {"id": "SUR-FI2", "kod": "SUR-FI2", "nazwa": "Drut fi2", "jednostka": "mm"},
        ],
    )

    pp = bom.compute_bom_for_prd("1.775.250", 100)
    assert pp["POL-OSKA"]["ilosc"] == 200
    assert pp["POL-OSKA"]["czynnosci"] == ["toczenie", "gwintowanie M8"]
    assert pp["POL-OSKA"]["surowiec"]["kod"] == "SUR-FI8"

    raw = bom.compute_sr_for_prd("1.775.250", 100)
    assert raw["SUR-FI8"] == {"ilosc": 73800.0, "jednostka": "mm"}
    assert raw["SUR-FI2"] == {"ilosc": 5000.0, "jednostka": "mm"}


def test_reservation_changes_reserved_quantity_not_physical_stock(monkeypatch):
    state = {
        "SUR-FI8": {"id": "SUR-FI8", "stan": 100000.0, "rezerwacje": 0.0, "jednostka": "mm"}
    }

    def fake_rezerwuj(item_id, qty, user, kontekst=None):
        rec = state[item_id]
        free = rec["stan"] - rec["rezerwacje"]
        actual = min(float(qty), free)
        rec["rezerwacje"] += actual
        return actual

    monkeypatch.setattr(zl.LM, "rezerwuj", fake_rezerwuj)
    monkeypatch.setattr(zl.LM, "get_item", lambda item_id: state[item_id])

    result = zl.reserve_materials(
        {"SUR-FI8": {"ilosc": 73800.0, "jednostka": "mm"}},
        user="Edwin",
        context="zlecenie:test",
    )

    assert state["SUR-FI8"]["stan"] == 100000.0
    assert state["SUR-FI8"]["rezerwacje"] == 73800.0
    assert result["SUR-FI8"] == 26200.0


def test_check_materials_uses_free_stock_after_existing_reservations(monkeypatch):
    monkeypatch.setattr(
        zl,
        "read_magazyn",
        lambda: {
            "SUR-FI8": {
                "nazwa": "Drut fi8",
                "stan": 100000.0,
                "rezerwacje": 40000.0,
                "dostepne": 60000.0,
            }
        },
    )

    shortages = zl.check_materials(
        {"SUR-FI8": {"ilosc": 73800.0, "jednostka": "mm"}},
        1,
    )

    assert len(shortages) == 1
    assert shortages[0]["stan"] == 100000.0
    assert shortages[0]["zarezerwowane"] == 40000.0
    assert shortages[0]["dostepne"] == 60000.0
    assert shortages[0]["brakuje"] == 13800.0
