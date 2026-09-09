# WM-VERSION: 0.2
# Plik: tests/test_planista_excel_orders.py
# version: 1.1

from __future__ import annotations

import pytest

import planista_excel_orders as sync
from planista_excel_match import STATUS_AMBIGUOUS, STATUS_FOUND, STATUS_MISSING


def _row(
    order="659",
    code="1.327.50",
    qty=640,
    *,
    date="2026-09-14",
    process="zgrzane",
    status=STATUS_FOUND,
    source_row=4,
):
    return {
        "source_row": source_row,
        "nr_zlec": str(order),
        "excel_oznaczenie": code,
        "produkt": f"{code} Produkt testowy",
        "ilosc": float(qty),
        "data_wysylki": date,
        "proces": process,
        "match_status": status,
        "wm_symbol": code if status == STATUS_FOUND else "",
        "wm_nazwa": "Produkt testowy" if status == STATUS_FOUND else "",
        "excel_change_fields": [],
    }


def _payload(rows, removed=None):
    return {
        "source_path": "C:/plan/Plan Produkcji 2026.xlsx",
        "source_name": "Plan Produkcji 2026.xlsx",
        "sheet": "PLAN 2026",
        "source_sha256": "abc123",
        "rows": [dict(row) for row in rows],
        "removed_rows": [dict(row) for row in (removed or [])],
    }


def _imported_order(
    order_id="000101",
    external="659",
    code="1.327.50",
    qty=640,
    *,
    date="2026-09-14",
    process="zgrzane",
    status="nowe",
):
    return {
        "id": order_id,
        "produkt": code,
        "ilosc": float(qty),
        "wykonano": 0.0,
        "status": status,
        "termin": date,
        "zlec_wew": str(external),
        "planista_excel": {
            "schema": 1,
            "typ": "plan_excel",
            "nr_zlec": str(external),
            "wm_symbol": code,
            "proces": process,
            "identity": f"{str(external).casefold()}|{code.casefold()}",
        },
    }


def test_two_different_products_under_same_external_order_are_two_creates():
    rows = [
        _row(code="1.327.50", qty=640),
        _row(code="1.620.165", qty=84, source_row=5),
    ]

    plan = sync.build_order_sync_plan(_payload(rows), orders=[])

    assert [item["action"] for item in plan["items"]] == [
        sync.ACTION_CREATE,
        sync.ACTION_CREATE,
    ]
    assert plan["items"][0]["identity"] != plan["items"][1]["identity"]


def test_duplicate_same_product_under_same_external_order_requires_decision():
    rows = [
        _row(qty=100, source_row=4),
        _row(qty=200, source_row=5),
    ]

    plan = sync.build_order_sync_plan(_payload(rows), orders=[])

    assert len(plan["items"]) == 2
    assert all(item["action"] == sync.ACTION_CONFLICT for item in plan["items"])
    assert plan["can_write"] is False


def test_same_imported_line_is_idempotent_and_source_row_is_not_identity():
    existing = _imported_order()
    row = _row(source_row=999)

    plan = sync.build_order_sync_plan(_payload([row]), orders=[existing])

    item = plan["items"][0]
    assert item["action"] == sync.ACTION_NONE
    assert item["order_id"] == "000101"
    assert item["identity"] == "659|1.327.50"
    assert plan["can_write"] is False


def test_quantity_date_and_process_change_update_same_imported_order():
    existing = _imported_order()
    row = _row(qty=700, date="2026-09-18", process="malowane")

    plan = sync.build_order_sync_plan(_payload([row]), orders=[existing])

    item = plan["items"][0]
    assert item["action"] == sync.ACTION_UPDATE
    assert item["order_id"] == "000101"
    assert item["changes"] == ["Ilość", "Data wysyłki", "Proces"]


def test_missing_and_ambiguous_products_never_auto_create():
    rows = [
        _row(status=STATUS_MISSING),
        _row(code="5.300.600", status=STATUS_AMBIGUOUS, source_row=5),
    ]

    plan = sync.build_order_sync_plan(_payload(rows), orders=[])

    assert all(item["action"] == sync.ACTION_SKIP for item in plan["items"])
    assert plan["can_write"] is False


def test_started_or_completed_order_is_protected_from_excel_overwrite():
    for status in ("w trakcie", "wstrzymane", "zakończone"):
        existing = _imported_order(status=status)
        plan = sync.build_order_sync_plan(_payload([_row(qty=700)]), orders=[existing])
        assert plan["items"][0]["action"] == sync.ACTION_PROTECTED


def test_product_replacement_is_conflict_not_silent_create():
    existing = _imported_order(code="1.327.50")
    row = _row(code="1.620.165")
    row["excel_change_fields"] = ["Produkt"]

    plan = sync.build_order_sync_plan(_payload([row]), orders=[existing])

    item = plan["items"][0]
    assert item["action"] == sync.ACTION_CONFLICT
    assert item["changes"] == ["Produkt"]


def test_manual_order_with_same_business_key_blocks_duplicate_creation():
    manual = {
        "id": "000050",
        "produkt": "1.327.50",
        "ilosc": 640.0,
        "status": "nowe",
        "termin": "2026-09-14",
        "zlec_wew": "659",
    }

    plan = sync.build_order_sync_plan(_payload([_row()]), orders=[manual])

    assert plan["items"][0]["action"] == sync.ACTION_CONFLICT
    assert plan["items"][0]["order_id"] == "000050"


def test_removed_excel_row_never_deletes_order_automatically():
    existing = _imported_order()
    removed = _row()
    removed["excel_change_status"] = "Usunięta pozycja"

    plan = sync.build_order_sync_plan(_payload([], removed=[removed]), orders=[existing])

    item = plan["items"][0]
    assert item["action"] == sync.ACTION_REMOVED
    assert item["order_id"] == "000101"
    assert plan["can_write"] is False


def test_apply_requires_explicit_approval_and_writes_provenance(monkeypatch):
    payload = _payload([_row()])
    plan = sync.build_order_sync_plan(payload, orders=[])

    with pytest.raises(sync.ExcelOrderSyncError):
        sync.apply_order_sync(payload, plan, approved_identities=set())

    created = []
    provenance = []

    def fake_create(product, qty, **kwargs):
        created.append((product, qty, kwargs))
        return {"id": "000777", "produkt": product}, []

    monkeypatch.setattr(sync.ZL, "list_zlecenia", lambda: [])
    monkeypatch.setattr(sync.ZL, "create_zlecenie", fake_create)
    monkeypatch.setattr(
        sync,
        "_write_order_provenance",
        lambda order_id, meta, *, autor: provenance.append((order_id, meta, autor)) or {},
    )

    result = sync.apply_order_sync(
        payload,
        plan,
        approved_identities={plan["items"][0]["identity"]},
        autor="test",
    )

    assert result["written"] == 1
    assert created[0][0] == "1.327.50"
    assert created[0][2]["zlec_wew"] == "659"
    assert created[0][2]["termin"] == "2026-09-14"
    assert provenance[0][0] == "000777"
    assert provenance[0][1]["nr_zlec"] == "659"
    assert provenance[0][1]["wm_symbol"] == "1.327.50"
    assert "source_row" not in provenance[0][1]


def test_apply_rechecks_duplicate_before_create(monkeypatch):
    payload = _payload([_row()])
    plan = sync.build_order_sync_plan(payload, orders=[])
    existing = _imported_order()

    monkeypatch.setattr(sync.ZL, "list_zlecenia", lambda: [existing])
    monkeypatch.setattr(
        sync.ZL,
        "create_zlecenie",
        lambda *args, **kwargs: pytest.fail("create must not run"),
    )

    with pytest.raises(sync.ExcelOrderSyncError):
        sync.apply_order_sync(
            payload,
            plan,
            approved_identities={plan["items"][0]["identity"]},
        )


def test_apply_rechecks_protected_status_before_update(monkeypatch):
    existing = _imported_order(status="nowe")
    payload = _payload([_row(qty=700)])
    plan = sync.build_order_sync_plan(payload, orders=[existing])
    protected_now = _imported_order(status="w trakcie")

    monkeypatch.setattr(sync.ZL, "list_zlecenia", lambda: [protected_now])
    monkeypatch.setattr(sync.ZL, "update_zlecenie", lambda *args, **kwargs: pytest.fail("update must not run"))

    with pytest.raises(sync.ExcelOrderSyncError):
        sync.apply_order_sync(
            payload,
            plan,
            approved_identities={plan["items"][0]["identity"]},
        )
