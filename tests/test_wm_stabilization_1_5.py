"""Targeted WM/WMM stabilization: compatibility, retries and paid leave races."""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_wmm_0532_is_advertised_consistently():
    from services import wmm_api as api

    assert api.WMM_COMPAT_VERSION == "0.5.32"
    assert api.mobile_status()["wmm_version"] == api.WMM_COMPAT_VERSION


def test_two_concurrent_paid_leave_requests_cannot_spend_one_day_twice(
    tmp_path, monkeypatch,
):
    from services import leave_workflow_service as leave
    from services import leave_balance_service as balance

    leaves = tmp_path / "leaves.json"
    requests = tmp_path / "leave_requests.json"
    monkeypatch.setattr(leave, "leaves_path", lambda: leaves)
    monkeypatch.setattr(leave, "requests_path", lambda: requests)
    monkeypatch.setattr(leave, "_identity", lambda login: ("USR-1", str(login)))
    monkeypatch.setattr(leave, "_vacation_workdays", lambda login, days: list(days))
    monkeypatch.setattr(leave, "read_leaves", lambda **kw: [])

    def live_balance(login, year):
        pending = leave.read_requests(login=login, status="pending")
        return {"remaining": 1, "pending": float(sum(
            len(row.get("dates") or []) for row in pending
        ))}

    monkeypatch.setattr(balance, "get_balance", live_balance)
    started = threading.Barrier(2)

    def submit(day):
        started.wait(timeout=4)
        try:
            return ("ok", leave.request_vacation("Marek", [day]))
        except ValueError as exc:
            return ("blocked", str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ("2026-09-25", "2026-09-26")))

    assert sorted(result[0] for result in results) == ["blocked", "ok"]
    assert any("przekracza dostępny urlop" in result[1] for result in results
               if result[0] == "blocked")
    saved = json.loads(requests.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert len(saved[0]["dates"]) == 1


def test_wmm_pending_order_retry_after_restart_does_not_duplicate_mutation(
    tmp_path, monkeypatch,
):
    from services import wmm_api as api

    monkeypatch.setattr(api, "_idempotency_path", lambda: tmp_path / "ledger.json")
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    api._IDEMPOTENCY_CACHE.clear()
    performed = []

    def interrupted_after_write():
        performed.append("create")
        raise OSError("Odpowiedź HTTP utracona po zapisie")

    with pytest.raises(OSError, match="utracona"):
        api._run_idempotent(
            "wmm-order-unique-001", "/api/v1/planista/orders",
            interrupted_after_write, "product=P1,quantity=1",
        )
    assert performed == ["create"]
    api._IDEMPOTENCY_CACHE.clear()
    monkeypatch.setattr(api, "_IDEMPOTENCY_LOADED_PATH", None)
    with pytest.raises(api.WmmIdempotencyPending, match="Niepewny"):
        api._run_idempotent(
            "wmm-order-unique-001", "/api/v1/planista/orders",
            interrupted_after_write, "product=P1,quantity=1",
        )
    assert performed == ["create"]
