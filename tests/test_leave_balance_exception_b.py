"""B: balance is checked in write services and overrides are explicitly auditable."""
from copy import deepcopy

import pytest

from services import leave_workflow_service as LW
from services import leave_balance_service as LB
import profile_attendance_edit_runtime as EDIT


@pytest.fixture()
def setup_leave(monkeypatch, tmp_path):
    monkeypatch.setattr(LW, "_identity", lambda who: ("USR-1", str(who)))
    monkeypatch.setattr(LW, "_require_foreman", lambda actor: str(actor) if actor == "Edwin" else (_ for _ in ()).throw(PermissionError("brygadzista")))
    monkeypatch.setattr(LW, "_vacation_workdays", lambda _login, dates: list(dates))
    monkeypatch.setattr(LW, "read_leaves", lambda **kw: [])
    monkeypatch.setattr(LW, "read_requests", lambda **kw: [])
    monkeypatch.setattr(LW, "get_user", lambda _login: {"login": "Marek", "user_id": "USR-1"})
    monkeypatch.setattr(LB, "get_balance", lambda *_a, **_k: {"remaining": 0, "pending": 0})
    monkeypatch.setattr(LW, "requests_path", lambda: tmp_path / "requests.json")
    monkeypatch.setattr(LW, "leaves_path", lambda: tmp_path / "leaves.json")
    return tmp_path


def test_no_balance_blocks_normal_request_without_file_write(setup_leave):
    with pytest.raises(ValueError, match="przekracza dostępny urlop"):
        LW.request_vacation("Marek", ["2026-09-25"])
    assert not (setup_leave / "requests.json").exists()


def test_exception_requires_foreman_and_reason(setup_leave):
    with pytest.raises(ValueError, match="przekracza dostępny"):
        LW.require_paid_leave_balance("Marek", ["2026-09-25"])
    with pytest.raises(PermissionError):
        LW.require_paid_leave_balance("Marek", ["2026-09-25"],
                                       override_actor="Marek", override_reason="decyzja")
    with pytest.raises(ValueError, match="przyczyny"):
        LW.require_paid_leave_balance("Marek", ["2026-09-25"],
                                       override_actor="Edwin")
    accepted = LW.require_paid_leave_balance(
        "Marek", ["2026-09-25"], override_actor="Edwin",
        override_reason="Wyjątkowa sytuacja",
    )
    assert accepted["shortage"] == 1


def test_no_balance_is_not_bypassed_by_same_day_replacement_of_other_absence(setup_leave):
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(LW, "read_leaves", lambda **kw: [
            {"type": "l4", "date": "2026-09-25", "user_id": "USR-1"},
        ])
        with pytest.raises(ValueError, match="przekracza dostępny urlop"):
            LW.require_paid_leave_balance(
                "Marek", ["2026-09-25"], replacing_dates=["2026-09-25"],
            )
    finally:
        monkeypatch.undo()


def test_existing_paid_leave_is_not_charged_twice(setup_leave, monkeypatch):
    monkeypatch.setattr(LW, "read_leaves", lambda **kw: [
        {"type": "urlop", "date": "2026-09-25", "user_id": "USR-1"},
    ])
    bal = LW.require_paid_leave_balance(
        "Marek", ["2026-09-25"], replacing_dates=["2026-09-25"],
    )
    assert bal["shortage"] == 0


def test_approval_rechecks_actual_balance_and_records_exception(setup_leave, monkeypatch):
    request = {
        "id": "REQ1", "status": "pending", "login": "Marek",
        "user_id": "USR-1", "dates": ["2026-09-25"],
        "note": "test",
    }
    monkeypatch.setattr(LW, "read_requests", lambda **kw: [dict(request)])
    (setup_leave / "requests.json").write_text(__import__("json").dumps([request]), encoding="utf-8")
    monkeypatch.setattr(LW, "_read_all_leaves", lambda: [])
    monkeypatch.setattr(LW, "_source_years_for_dates", lambda *_: {"2026-09-25": 2026})
    monkeypatch.setattr(LW, "_sync_attendance_reason", lambda *_: None)
    with pytest.raises(ValueError, match="przekracza dostępny urlop"):
        LW.approve_request("REQ1", "Edwin")
    with pytest.raises(ValueError, match="przyczyny"):
        LW.approve_request("REQ1", "Edwin", allow_over_balance=True)
    row = LW.approve_request(
        "REQ1", "Edwin", allow_over_balance=True,
        override_reason="Pilna sytuacja rodzinna",
    )
    assert row["status"] == "approved"
    assert row["over_balance_override"] is True
    assert row["override_actor"] == "Edwin"
    assert row["override_reason"] == "Pilna sytuacja rodzinna"
    assert __import__("json").loads((setup_leave / "leaves.json").read_text())[0]["date"] == "2026-09-25"
