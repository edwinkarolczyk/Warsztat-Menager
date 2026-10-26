"""Regression tests for automatic Planista -> execution-disposition status sync."""
import zlecenia_logika as ZL


def test_completed_full_order_targets_closed_disposition():
    assert ZL._execution_dispatch_target_status({
        "status": "zakończone", "ilosc": 10, "wykonano": 10,
    }) == "zamknieta"


def test_completed_order_with_short_quantity_does_not_close_disposition():
    assert ZL._execution_dispatch_target_status({
        "status": "zakończone", "ilosc": 10, "wykonano": 8,
    }) == "w_toku"


def test_in_progress_full_quantity_does_not_close_without_completed_status():
    assert ZL._execution_dispatch_target_status({
        "status": "w trakcie", "ilosc": 10, "wykonano": 10,
    }) == "w_toku"


def test_auto_close_uses_store_transitions_and_records_reason():
    class FakeStore:
        calls = []

        @classmethod
        def set_dyspozycja_status(cls, disp_id, status, **kwargs):
            cls.calls.append((disp_id, status, kwargs))
            return {"id": disp_id, "status": status}

    result = ZL._apply_execution_dispatch_status(
        FakeStore,
        {"id": "D-1", "status": "nowa"},
        "zamknieta",
        actor="operator",
    )

    assert result["status"] == "zamknieta"
    assert [call[1] for call in FakeStore.calls] == ["w_toku", "zamknieta"]
    assert FakeStore.calls[-1][2]["uwagi"] == "Zamknięto automatycznie ze źródła: Planista."
