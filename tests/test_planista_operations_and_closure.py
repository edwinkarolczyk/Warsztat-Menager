"""WM 1.0: last-operation output and safe consent-based dispatch closure."""
from copy import deepcopy
from pathlib import Path

import pytest

import planista_semi_progress_runtime as PS
import planista_dispatch_runtime as PD
import planista_audit_runtime as PAR
import zlecenia_logika as ZL
import dyspozycje_store as DS
import dyspozycje_access as DA
import planowanie_magazyn as PM


def test_only_last_operation_makes_semi(monkeypatch):
    state = {
        "id": "000125", "produkt": "P", "ilosc": 6, "wykonano": 0,
        "status": "nowe", "historia": [],
        "plan_polprodukty": {"A": {"potrzeba": 18, "z_magazynu": 0}},
    }
    monkeypatch.setattr(PS, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": 18, "czynnosci": ["Cięcie", "Spawanie"]}
    })
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000125.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: deepcopy(state))

    def write(_path, data):
        state.clear()
        state.update(deepcopy(data))

    monkeypatch.setattr(ZL, "_write_json", write)
    monkeypatch.setattr(PAR, "_file_snapshot", lambda _path: (False, b""))
    monkeypatch.setattr(PAR, "_restore_file", lambda *_args: None)

    PS.report_polprodukt_operation("000125", "A", "Cięcie", 6)
    assert state.get("wykonano_polprodukty", {}).get("A", 0) == 0
    with pytest.raises(ValueError, match="poprzedniej"):
        PS.report_polprodukt_operation("000125", "A", "Spawanie", 7)
    PS.report_polprodukt_operation("000125", "A", "Spawanie", 6)
    assert state["wykonano_polprodukty"]["A"] == 6
    assert state["wykonano"] == 0
    assert PS.proposed_product_completion(state)["complete_sets"] == 2
    with pytest.raises(ValueError, match="ostatniej"):
        PS.report_polprodukt_wykonano("000125", "A", 7)
    PS.report_polprodukt_operation("000125", "A", "Spawanie", 6)
    assert state["wykonano_polprodukty"]["A"] == 6


def test_closure_requires_completed_and_settled():
    active = {"id": "D1", "status": "w_toku"}
    original = PD.find_active_planista_dispatch
    try:
        PD.find_active_planista_dispatch = lambda _oid: active
        order = {"id": "000125", "ilosc": 6, "wykonano": 6,
                 "materialy_rozliczono_do": 0}
        assert not PD.closure_readiness(order)["ready"]
        order["materialy_rozliczono_do"] = 6
        assert PD.closure_readiness(order)["ready"]
        order["wykonano"] = 5
        assert not PD.closure_readiness(order)["ready"]
    finally:
        PD.find_active_planista_dispatch = original


def test_dispatch_close_never_reconsumes_material(monkeypatch):
    order = {"id": "000125", "ilosc": 6, "wykonano": 6,
             "materialy_rozliczono_do": 6}
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000125.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: dict(order))
    monkeypatch.setattr(PD, "find_active_planista_dispatch", lambda _id: {
        "id": "D1", "status": "w_toku",
    })
    monkeypatch.setattr(PD, "find_closed_planista_dispatch", lambda _id: None)
    monkeypatch.setattr(DA, "is_role_action_allowed", lambda *_args: True)
    calls = []
    monkeypatch.setattr(PM, "release_execution_reservations", lambda *args, **kwargs: calls.append(("release", args[0])))

    def set_status(dysp_id, target, **kwargs):
        calls.append((dysp_id, target))
        return {"id": dysp_id, "status": target}

    monkeypatch.setattr(DS, "set_dyspozycja_status", set_status)
    result = PD.close_completed_planista_dispatch(
        "000125", who="Edwin", role="brygadzista",
    )
    assert result["status"] == "zamknieta"
    assert calls == [("release", "D1"), ("D1", "zamknieta")]


def test_repeat_close_returns_existing_without_releasing_again(monkeypatch):
    order = {"id": "000125", "ilosc": 6, "wykonano": 6,
             "materialy_rozliczono_do": 6}
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000125.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: dict(order))
    monkeypatch.setattr(DA, "is_role_action_allowed", lambda *_args: True)
    monkeypatch.setattr(PD, "find_closed_planista_dispatch", lambda _oid: {
        "id": "D1", "status": "zamknieta",
    })
    monkeypatch.setattr(PD, "find_active_planista_dispatch", lambda _oid: None)

    def should_not_release(*_args, **_kwargs):
        raise AssertionError("Rezerwacja nie może być zwolniona ponownie")

    monkeypatch.setattr(PM, "release_execution_reservations", should_not_release)
    assert PD.close_completed_planista_dispatch(
        "000125", who="Edwin", role="brygadzista",
    )["status"] == "zamknieta"


def test_ensure_dispatch_does_not_duplicate_closed_one(monkeypatch):
    monkeypatch.setattr(PD, "find_active_planista_dispatch", lambda _oid: None)
    monkeypatch.setattr(PD, "find_closed_planista_dispatch", lambda _oid: {
        "id": "D1", "status": "zamknieta",
    })
    record, created = PD.ensure_planista_dispatch({"id": "000125"})
    assert record["id"] == "D1"
    assert created is False


def test_reduce_order_rejects_in_progress_operations(monkeypatch):
    monkeypatch.setattr(PS, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": float(order["ilosc"]) * 3, "czynnosci": ["Cięcie", "Spawanie"]}
    })
    order = {
        "ilosc": 6, "produkt": "P",
        "sledzenie_operacji_polproduktow": True,
        "postep_operacji_polproduktow": {"A": {"Cięcie": 12}},
    }
    with pytest.raises(ValueError, match="operacje zgłoszono"):
        PS._guard_quantity_change(order, 3)


def test_nonfinite_operation_progress_is_rejected(monkeypatch):
    monkeypatch.setattr(PS, "_full_semi_targets", lambda order: {
        "A": {"potrzeba": 18, "czynnosci": ["Cięcie"]}
    })
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000125.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: {
        "id": "000125", "ilosc": 6, "historia": [],
    })
    with pytest.raises(ValueError, match="skończoną"):
        PS.report_polprodukt_operation("000125", "A", "Cięcie", float("nan"))
