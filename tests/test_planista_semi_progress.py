# WM-VERSION: 0.1
# Plik: tests/test_planista_semi_progress.py
# version: 1.3
from pathlib import Path

import pytest

import bom
import logika_magazyn as LM
import planista_audit_runtime as PAR
import zlecenia_progress as ZP
import zlecenia_logika as ZL
from planista_semi_progress_runtime import (
    _guard_quantity_change,
    _semi_product_links,
    report_polprodukt_wykonano,
    semi_progress_rows,
    semi_shortages_for_completion,
)


def _fake_bom(_product, qty, version=None):
    return {
        "POL-001": {
            "nazwa": "Zbijak 90 mm",
            "ilosc": float(qty),
        }
    }


def test_progress_separates_stock_from_amount_to_make(monkeypatch):
    monkeypatch.setattr(bom, "compute_bom_for_prd", _fake_bom)
    order = {
        "produkt": "PRD-1",
        "ilosc": 10,
        "plan_polprodukty": {
            "POL-001": {"nazwa": "Zbijak 90 mm", "potrzeba": 10, "z_magazynu": 2}
        },
    }

    row = semi_progress_rows(order)[0]
    assert row["potrzeba"] == 10
    assert row["z_magazynu"] == 2
    assert row["do_wykonania"] == 8
    assert row["wykonano"] == 0
    assert row["pozostalo"] == 8


def test_product_completion_checks_reported_semis_after_stock(monkeypatch):
    monkeypatch.setattr(bom, "compute_bom_for_prd", _fake_bom)
    order = {
        "produkt": "PRD-1",
        "ilosc": 10,
        "sledzenie_polproduktow": True,
        "polprodukty_z_magazynu_baza": {"POL-001": 2},
        "wykonano_polprodukty": {"POL-001": 3},
    }

    assert semi_shortages_for_completion(order, 5) == []
    shortages = semi_shortages_for_completion(order, 6)
    assert len(shortages) == 1
    assert shortages[0]["kod"] == "POL-001"
    assert shortages[0]["brakuje"] == pytest.approx(1.0)


def test_reporting_semi_progress_is_cumulative_and_saved(monkeypatch):
    monkeypatch.setattr(bom, "compute_bom_for_prd", _fake_bom)
    order = {
        "id": "000001",
        "produkt": "PRD-1",
        "ilosc": 10,
        "wykonano": 0,
        "status": "nowe",
        "plan_polprodukty": {
            "POL-001": {"nazwa": "Zbijak 90 mm", "potrzeba": 10, "z_magazynu": 2}
        },
        "historia": [],
    }
    written = {}
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000001.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: dict(order))
    monkeypatch.setattr(ZL, "_write_json", lambda _path, data: written.update(data))

    result = report_polprodukt_wykonano("000001", "POL-001", 3, kto="Edwin")
    assert result["wykonano_polprodukty"]["POL-001"] == 3
    assert result["polprodukty_z_magazynu_baza"]["POL-001"] == 2
    assert result["sledzenie_polproduktow"] is True
    assert result["status"] == "w przygotowaniu"
    assert written["wykonano_polprodukty"]["POL-001"] == 3


def test_allowed_semi_overproduction_consumes_raw_and_credits_surplus_once(monkeypatch):
    monkeypatch.setattr(bom, "compute_bom_for_prd", _fake_bom)
    order = {
        "id": "000001",
        "produkt": "PRD-1",
        "ilosc": 10,
        "wykonano": 0,
        "status": "nowe",
        "rzaz_mm": 0,
        "zezwol_nadprodukcja": True,
        "plan_polprodukty": {
            "POL-001": {"nazwa": "Zbijak 90 mm", "potrzeba": 10, "z_magazynu": 2}
        },
        "historia": [],
    }
    state = {
        "SUR-1": {"stan": 10.0, "rezerwacje": 0.0},
        "POL-001": {"stan": 0.0, "rezerwacje": 0.0, "typ": "półprodukt"},
    }
    written = {}
    returns = []
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000001.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: order)
    monkeypatch.setattr(ZL, "_write_json", lambda _path, data: written.update(data))
    monkeypatch.setattr(
        ZL,
        "_raw_need_for_pp",
        lambda _code, qty, _cut: {"SUR-1": {"ilosc": float(qty) * 5.0}},
    )
    monkeypatch.setattr(LM, "get_item", lambda code: state.get(code))
    monkeypatch.setattr(
        LM,
        "zuzyj",
        lambda code, amount, *_a, **_k: state[code].__setitem__(
            "stan", state[code]["stan"] - amount
        ),
    )

    def give_back(code, amount, *_a, **_k):
        returns.append((code, amount))
        state[code]["stan"] += amount

    monkeypatch.setattr(LM, "zwrot", give_back)
    monkeypatch.setattr(ZP, "_ensure_semi_item", lambda _code: state["POL-001"])
    monkeypatch.setattr(PAR, "_canonical_warehouse_snapshot", lambda: {})
    monkeypatch.setattr(PAR, "_file_snapshot", lambda _path: (False, b""))
    monkeypatch.setattr(PAR, "_restore_canonical_warehouse", lambda _data: None)
    monkeypatch.setattr(PAR, "_restore_file", lambda *_a: None)

    from planista_semi_progress_runtime import (
        pending_semi_surplus, transfer_polprodukt_surplus,
    )

    result = report_polprodukt_wykonano("000001", "POL-001", 10, kto="Edwin")

    # 8 szt. planu + 2 szt. nadwyżki: samo zgłoszenie nie zmienia Magazynu.
    assert pending_semi_surplus(result, "POL-001") == pytest.approx(2.0)
    assert state["SUR-1"]["stan"] == pytest.approx(10.0)
    assert state["POL-001"]["stan"] == pytest.approx(0.0)
    assert returns == []

    result = transfer_polprodukt_surplus("000001", "POL-001", kto="Edwin")
    assert state["SUR-1"]["stan"] == pytest.approx(0.0)
    assert state["POL-001"]["stan"] == pytest.approx(2.0)
    assert result["nadprodukcja_polproduktow_zaksiegowana"]["POL-001"] == pytest.approx(2.0)
    assert pending_semi_surplus(result, "POL-001") == pytest.approx(0.0)
    assert returns == [("POL-001", pytest.approx(2.0))]

    transfer_polprodukt_surplus("000001", "POL-001", kto="Edwin")
    assert returns == [("POL-001", pytest.approx(2.0))]


def test_quantity_cannot_drop_below_reported_semi_progress(monkeypatch):
    monkeypatch.setattr(bom, "compute_bom_for_prd", _fake_bom)
    order = {
        "produkt": "PRD-1",
        "ilosc": 10,
        "sledzenie_polproduktow": True,
        "polprodukty_z_magazynu_baza": {"POL-001": 0},
        "wykonano_polprodukty": {"POL-001": 4},
    }
    with pytest.raises(ValueError, match="zgłoszonego postępu"):
        _guard_quantity_change(order, 3)


def test_semiproduct_lists_all_linked_products():
    class Model:
        produkty = {
            "P-1": {
                "nazwa": "Produkt A",
                "BOM": [{"kod": "POL-001", "ilosc_na_sztuke": 1}],
            },
            "P-2": {
                "nazwa": "Produkt B",
                "BOM": [{"kod": "POL-001", "ilosc_na_sztuke": 2}],
            },
        }

    links = _semi_product_links(Model())
    assert links["POL-001"] == ["Produkt A [P-1]", "Produkt B [P-2]"]


def test_gui_planowanie_installs_semi_progress_runtime():
    source = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "install_planista_semi_progress_runtime" in source
    assert "install_planista_semi_progress_runtime()" in source
