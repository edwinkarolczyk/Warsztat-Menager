"""WM 1.0: last-operation output and safe consent-based dispatch closure."""
from copy import deepcopy
from pathlib import Path

import pytest

import planista_semi_progress_runtime as PS
import planista_dispatch_runtime as PD
import planista_audit_runtime as PAR
import zlecenia_logika as ZL
import zlecenia_progress as ZP
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


def test_order_sync_preserves_dispatch_status_history(monkeypatch):
    previous = {
        "id": "D1", "status": "zamknieta", "typ_dyspozycji": "zlecenie_wykonania",
        "obiekt_id": "zlecenie:000125",
        "meta": {"historia_statusow": [{"z": "w_toku", "na": "zamknieta"}],
                 "zamkniecie_potwierdzone": True},
    }
    recorded = {}
    monkeypatch.setattr(DS, "load_dyspozycje", lambda: [previous])
    monkeypatch.setattr(
        DS, "update_dyspozycja",
        lambda _id, data: recorded.update(data) or {**previous, **data},
    )
    ZL._sync_execution_disposition({
        "id": "000125", "produkt": "P", "ilosc": 6,
        "wykonano": 6, "plan_polprodukty": {},
    })
    assert recorded["meta"]["historia_statusow"] == [
        {"z": "w_toku", "na": "zamknieta"}
    ]
    assert recorded["meta"]["zamkniecie_potwierdzone"] is True
    assert "status" not in recorded


def test_legacy_material_posting_cannot_be_consumed_twice(monkeypatch):
    order = {"id": "000020", "ilosc": 10, "wykonano": 10,
             "historia": [{"co": "wykonano -> 10"}]}
    monkeypatch.setattr(ZL, "_order_path", lambda _id: Path("000020.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: dict(order))
    with pytest.raises(ValueError, match="starsze zlecenie"):
        ZP.rozlicz_material("000020", kto="Edwin")


def test_concurrent_semi_progress_keeps_highest_cumulative_quantity(monkeypatch, tmp_path):
    """Two WM/WMM requests for one order cannot overwrite newer progress."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    order_path = tmp_path / "000125.json"
    order_path.write_text(json.dumps({
        "id": "000125", "produkt": "P", "ilosc": 10, "wykonano": 0,
        "status": "nowe", "historia": [],
        "plan_polprodukty": {"A": {"potrzeba": 10, "z_magazynu": 0}},
    }), encoding="utf-8")
    monkeypatch.setattr(PS, "_full_semi_targets", lambda _order: {
        "A": {"potrzeba": 10, "czynnosci": []}
    })
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: order_path)
    monkeypatch.setattr(
        ZL, "_read_json",
        lambda path: json.loads(Path(path).read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        ZL, "_write_json",
        lambda path, value: Path(path).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        ),
    )

    gate = Barrier(2)
    def report(value):
        gate.wait()
        try:
            PS.report_polprodukt_wykonano("000125", "A", value)
        except ValueError as exc:
            assert "zmniejszyć" in str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(report, (1, 2)))
    saved = json.loads(order_path.read_text(encoding="utf-8"))
    assert saved["wykonano_polprodukty"]["A"] == 2
    assert saved["wykonano"] == 0


def test_two_surplus_transfers_post_stock_once(monkeypatch, tmp_path):
    """A duplicate mobile/Desktop confirmation cannot add stock twice."""
    import json
    import logika_magazyn as LM
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    order_path = tmp_path / "000125.json"
    order_path.write_text(json.dumps({
        "id": "000125", "produkt": "P", "ilosc": 10,
        "zezwol_nadprodukcja": True, "rzaz_mm": 0, "historia": [],
        "polprodukty_z_magazynu_baza": {"A": 0},
        "wykonano_polprodukty": {"A": 12},
    }), encoding="utf-8")
    warehouse = {
        "RAW": {"stan": 100.0, "rezerwacje": 0.0},
        "A": {"stan": 0.0, "rezerwacje": 0.0},
    }
    transfers = []
    monkeypatch.setattr(PS, "_full_semi_targets", lambda _o: {
        "A": {"potrzeba": 10}
    })
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: order_path)
    monkeypatch.setattr(
        ZL, "_read_json", lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    )
    monkeypatch.setattr(
        ZL, "_write_json", lambda p, v: Path(p).write_text(
            json.dumps(v, ensure_ascii=False), encoding="utf-8"
        )
    )
    monkeypatch.setattr(ZL, "_raw_need_for_pp", lambda _code, qty, _cut: {
        "RAW": {"ilosc": float(qty) * 3}
    })
    monkeypatch.setattr(LM, "_warehouse_path", lambda: tmp_path / "magazyn.json")
    monkeypatch.setattr(LM, "get_item", lambda code: warehouse.get(code))
    monkeypatch.setattr(
        LM, "zuzyj", lambda code, qty, *_a, **_k:
        warehouse[code].__setitem__("stan", warehouse[code]["stan"] - qty)
    )
    def credit(code, qty, *_a, **_k):
        transfers.append((code, qty))
        warehouse[code]["stan"] += qty
    monkeypatch.setattr(LM, "zwrot", credit)
    monkeypatch.setattr(ZP, "_ensure_semi_item", lambda _code: warehouse["A"])
    monkeypatch.setattr(PAR, "_canonical_warehouse_snapshot", lambda: deepcopy(warehouse))
    monkeypatch.setattr(PAR, "_restore_canonical_warehouse", lambda saved: warehouse.update(saved))

    gate = Barrier(2)
    def transfer(_):
        gate.wait()
        PS.transfer_polprodukt_surplus("000125", "A", kto="Edwin")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(transfer, (1, 2)))
    saved = json.loads(order_path.read_text(encoding="utf-8"))
    assert saved["nadprodukcja_polproduktow_zaksiegowana"]["A"] == 2
    assert warehouse["RAW"]["stan"] == 94
    assert warehouse["A"]["stan"] == 2
    assert transfers == [("A", 2)]



def test_wmm_checkbox_completes_operations_in_order_and_is_idempotent(monkeypatch):
    state = {
        "id": "000125",
        "produkt": "P",
        "ilosc": 6,
        "wykonano": 0,
        "status": "nowe",
        "historia": [],
        "plan_polprodukty": {
            "A": {
                "nazwa": "Rama",
                "potrzeba": 6,
                "z_magazynu": 0,
                "czynnosci": ["Cięcie", "Spawanie"],
            }
        },
    }
    monkeypatch.setattr(
        PS,
        "_full_semi_targets",
        lambda _order: {
            "A": {
                "nazwa": "Rama",
                "potrzeba": 6,
                "czynnosci": ["Cięcie", "Spawanie"],
            }
        },
    )
    monkeypatch.setattr(ZL, "_order_path", lambda _oid: Path("000125.json"))
    monkeypatch.setattr(ZL, "_read_json", lambda _path: deepcopy(state))

    def write(_path, data):
        state.clear()
        state.update(deepcopy(data))

    monkeypatch.setattr(ZL, "_write_json", write)
    monkeypatch.setattr(PAR, "_file_snapshot", lambda _path: (True, b"before"))
    monkeypatch.setattr(PAR, "_restore_file", lambda *_args: None)

    with pytest.raises(ValueError, match="Najpierw zakończ poprzednią operację"):
        PS._complete_polprodukt_operation_unlocked(
            "000125", "A", "Spawanie", kto="Edwin"
        )

    marker = "/api/v1/planista/orders/000125/semiproducts/A/operations/Cięcie|wmm-test-1234"
    PS._complete_polprodukt_operation_unlocked(
        "000125", "A", "Cięcie", kto="Edwin", request_marker=marker
    )
    assert state["postep_operacji_polproduktow"]["A"]["Cięcie"] == 6
    assert state.get("wykonano_polprodukty", {}).get("A", 0) == 0
    first_history_size = len(state["historia"])

    PS._complete_polprodukt_operation_unlocked(
        "000125", "A", "Cięcie", kto="Edwin", request_marker=marker
    )
    assert len(state["historia"]) == first_history_size
    assert state["wmm_applied_requests"].count(marker) == 1

    PS._complete_polprodukt_operation_unlocked(
        "000125", "A", "Spawanie", kto="Edwin"
    )
    assert state["postep_operacji_polproduktow"]["A"]["Spawanie"] == 6
    assert state["wykonano_polprodukty"]["A"] == 6
    assert state["status"] == "w przygotowaniu"
