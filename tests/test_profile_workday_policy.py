# version: 1.1
from datetime import date, datetime

import pytest

import profile_calendar_team_runtime as calendar_runtime
import profile_workday_policy_runtime as policy
from services import attendance_service, workforce_profile_service


def _payload(day_text: str, *, absence: str = "BRAK", day_value: float = 1.0) -> dict:
    return {
        "date": day_text,
        "slot": "RANO",
        "day_value": day_value,
        "absence": absence,
        "overtime_hours": 0.0,
        "first_login": "",
    }


def test_weekday_labels_match_polish_calendar():
    assert policy._weekday_label("2026-09-07") == "Pon"
    assert policy._weekday_label("2026-09-08") == "Wt"
    assert policy._weekday_label("2026-09-09") == "Śr"
    assert policy._weekday_label("2026-09-10") == "Czw"
    assert policy._weekday_label("2026-09-11") == "Pt"
    assert policy._weekday_label("2026-09-12") == "Sob"
    assert policy._weekday_label("2026-09-13") == "Nie"


def test_empty_workdays_really_means_no_workdays():
    user = {"login": "marek", "workdays": []}
    assert workforce_profile_service.workdays_for(user) == set()
    assert workforce_profile_service.is_workday(user, date(2026, 9, 7)) is False


def test_normal_attendance_is_blocked_on_disabled_saturday(monkeypatch):
    user = {"login": "marek", "workdays": [0, 1, 2, 3, 4]}
    monkeypatch.setattr(workforce_profile_service, "get_user", lambda _login: user)

    with pytest.raises(ValueError, match="Praca w dniu wolnym"):
        policy._ensure_allowed("marek", _payload("2026-09-05"), allow_offday=False)


def test_explicit_offday_work_is_allowed(monkeypatch):
    user = {"login": "marek", "workdays": [0, 1, 2, 3, 4]}
    monkeypatch.setattr(workforce_profile_service, "get_user", lambda _login: user)

    assert policy._ensure_allowed("marek", _payload("2026-09-05"), allow_offday=True) is True


def test_l4_can_cover_disabled_saturday_without_work_override(monkeypatch):
    user = {"login": "dawid", "workdays": [0, 1, 2, 3, 4]}
    monkeypatch.setattr(workforce_profile_service, "get_user", lambda _login: user)
    payload = _payload("2026-09-05", absence="L4", day_value=0.0)

    assert policy._ensure_allowed("dawid", payload, allow_offday=False) is False


def _calendar_rows(*, offday_work: bool = False, leave_l4: bool = False):
    policy._install_calendar_policy()
    user = {
        "login": "marek",
        "user_id": "USR-0002",
        "imie": "Marek",
        "rola": "operator",
        "workdays": [0, 1, 2, 3, 4],
    }
    record = {
        "user_id": "USR-0002",
        "login_snapshot": "marek",
        "status": attendance_service.STATUS_MISSING,
        "day_value": 0.0,
        "source": "manual",
    }
    if offday_work:
        record.update(
            {
                "offday_work": True,
                "status": attendance_service.STATUS_PRESENT,
                "day_value": 1.0,
            }
        )
    attendance_doc = {
        "2026-09-05": {
            attendance_service.RANO: {"USR-0002": record},
            attendance_service.POPO: {},
        }
    }
    leaves = []
    if leave_l4:
        leaves.append({"login": "marek", "date": "2026-09-05", "type": "l4"})

    return calendar_runtime._team_day_rows_from_snapshots(
        date(2026, 9, 5),
        [user],
        {},
        attendance_doc,
        leaves,
        [],
        now=datetime(2026, 9, 7, 8, 0),
    )


def test_stale_saturday_attendance_does_not_create_br():
    rows = _calendar_rows()
    assert rows[0]["status_code"] == "WOLNE"
    assert rows[0]["status"] == "Wolne"


def test_explicit_saturday_work_remains_visible():
    rows = _calendar_rows(offday_work=True)
    assert rows[0]["status_code"] == "PRACA"
    assert rows[0]["offday_work"] is True
    assert "Praca w dniu wolnym" in rows[0]["status"]


def test_l4_remains_visible_on_disabled_saturday():
    rows = _calendar_rows(leave_l4=True)
    assert rows[0]["status_code"] == "L4"
