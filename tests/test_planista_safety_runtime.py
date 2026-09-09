# WM-VERSION: 0.1
# Plik: tests/test_planista_safety_runtime.py
# version: 1.3

from pathlib import Path

import logika_magazyn as LM
import planista_audit_runtime as PAR
import planista_safety_runtime as PSR
import planista_transaction_runtime as PTR
import zlecenia_logika as ZL
from planista_versions_runtime import (
    _archive_name,
    _bom_signature,
    _orders_using_version,
    _suggest_next_version,
)


def test_reservation_state_distinguishes_full_partial_and_missing():
    base = {
        "zapotrzebowanie_surowce": {"SUR-1": {"ilosc": 6000}},
        "plan_polprodukty": {"POL-1": {"z_magazynu": 2}},
    }

    full = dict(base, rezerwacje_surowce={"SUR-1": 6000}, rezerwacje_polprodukty={"POL-1": 2})
    partial = dict(base, rezerwacje_surowce={"SUR-1": 3000}, rezerwacje_polprodukty={"POL-1": 2})
    missing = dict(base, rezerwacje_surowce={}, rezerwacje_polprodukty={})

    assert PSR._reservation_state(full) == (True, "pełne")
    assert PSR._reservation_state(partial) == (False, "częściowe")
    assert PSR._reservation_state(missing) == (False, "brak")


def test_reservation_state_no_need_is_not_a_shortage():
    assert PSR._reservation_state({}) == (True, "nie dotyczy")


def test_product_version_archive_name_and_suggestion_are_stable():
    assert _archive_name("1.775/250", "1.0") == "1.775_250__v1.0.json"
    assert _suggest_next_version("1.0") == "1.1"
    assert _suggest_next_version("2.7") == "2.8"


def test_bom_signature_ignores_row_order_but_detects_quantity_change():
    left = {
        "BOM": [
            {"kod": "POL-2", "ilosc_na_sztuke": 2},
            {"kod": "POL-1", "ilosc_na_sztuke": 1},
        ]
    }
    same = {
        "BOM": [
            {"kod": "POL-1", "ilosc_na_sztuke": 1},
            {"kod": "POL-2", "ilosc_na_sztuke": 2},
        ]
    }
    changed = {
        "BOM": [
            {"kod": "POL-1", "ilosc_na_sztuke": 1},
            {"kod": "POL-2", "ilosc_na_sztuke": 3},
        ]
    }
    assert _bom_signature(left) == _bom_signature(same)
    assert _bom_signature(left) != _bom_signature(changed)


def test_orders_using_version_includes_legacy_orders(monkeypatch):
    monkeypatch.setattr(
        ZL,
        "list_zlecenia",
        lambda: [
            {"id": "Z-1", "produkt": "PRD-1", "version": "1.0"},
            {"id": "Z-LEGACY", "produkt": "PRD-1"},
            {"id": "Z-2", "produkt": "PRD-1", "version": "2.0"},
            {"id": "Z-X", "produkt": "PRD-X", "version": "1.0"},
        ],
    )
    assert _orders_using_version("PRD-1", "1.0") == ["Z-1", "Z-LEGACY"]


def test_warehouse_restore_writes_snapshot(monkeypatch):
    calls = []
    monkeypatch.setattr(LM, "save_magazyn", lambda data: calls.append(("save", data)))
    monkeypatch.setattr(LM, "zapisz_stan_magazynu", lambda data: calls.append(("state", data)))

    snapshot = {"items": {"SUR-1": {"stan": 123, "rezerwacje": 10}}}
    PTR._restore_warehouse(snapshot)

    assert calls[0][0] == "save"
    assert calls[1][0] == "state"
    assert calls[0][1]["items"]["SUR-1"]["stan"] == 123


def test_audit_snapshot_never_merges_external_catalogs(monkeypatch):
    calls = []

    def fake_load(*, include_external=True):
        calls.append(include_external)
        return {"items": {}}

    monkeypatch.setattr(LM, "load_magazyn", fake_load)
    assert PAR._canonical_warehouse_snapshot() == {"items": {}}
    assert calls == [False]


def test_file_snapshot_restores_previous_bytes(tmp_path):
    path = tmp_path / "order.json"
    path.write_bytes(b"old")
    snapshot = PAR._file_snapshot(path)
    path.write_bytes(b"new")
    PAR._restore_file(path, snapshot)
    assert path.read_bytes() == b"old"


def test_gui_planowanie_installs_all_planista_runtime_layers():
    text = Path("gui_planowanie.py").read_text(encoding="utf-8")
    assert "install_planista_safety_runtime" in text
    assert "install_planista_transaction_runtime" in text
    assert "install_planista_versions_runtime" in text
    assert "install_planista_operations_runtime" in text
    assert "install_planista_audit_runtime" in text
    assert "install_planista_editor_runtime" in text
    assert "_runtime_ready" in text


def test_operations_dictionary_is_a_planista_catalog():
    text = Path("planista_operations_runtime.py").read_text(encoding="utf-8")
    assert '"Operacje technologiczne"' in text
    assert 'operacje_technologiczne.json' in text
    assert "_used_operations" in text
    assert "Nie można usunąć operacji używanej przez półprodukt" in text


def test_planista_editor_exposes_requested_actions():
    text = Path("planista_editor_runtime.py").read_text(encoding="utf-8")
    assert 'text="Dodaj zlecenie"' in text
    assert 'text="Edytuj zlecenie"' in text
    assert 'text="Zapisz zmianę"' in text
    assert "_edit_operation" in text
    assert "_edit_raw_kind" in text


def test_audit_runtime_skips_archived_products_and_uses_full_transaction():
    text = Path("planista_audit_runtime.py").read_text(encoding="utf-8")
    assert 'include_external=False' in text
    assert '"__v" in pth.stem' in text
    assert "_wm_full_transaction" in text
    assert "_refresh_model_from_disk" in text
