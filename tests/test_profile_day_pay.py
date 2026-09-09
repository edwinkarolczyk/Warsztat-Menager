from services import day_pay_service
from profile_calendar_team_runtime import _leave_code, _slot_text


def _no_overrides(monkeypatch):
    monkeypatch.setattr(day_pay_service, "_config_overrides", lambda: {})


def test_force_majeure_defaults_to_50_percent(monkeypatch):
    _no_overrides(monkeypatch)
    row = day_pay_service.compensation("ŚW", pay_day_value=1.0)
    assert row["pay_code"] == "ŚW"
    assert row["pay_percent"] == 50.0
    assert row["pay_equivalent_days"] == 0.5


def test_force_majeure_alias_is_normalized(monkeypatch):
    _no_overrides(monkeypatch)
    row = day_pay_service.compensation("sila_wyzsza")
    assert row["pay_code"] == "ŚW"
    assert row["pay_percent"] == 50.0


def test_paid_day_defaults_cover_future_payroll_seed(monkeypatch):
    _no_overrides(monkeypatch)
    expected = {
        "PRACA": 100.0,
        "UR": 100.0,
        "UŻ": 100.0,
        "L4": 80.0,
        "ŚW": 50.0,
        "NN": 0.0,
        "UB": 0.0,
        "BRAK": 0.0,
    }
    for code, percent in expected.items():
        assert day_pay_service.compensation(code)["pay_percent"] == percent


def test_half_workday_is_half_paid_equivalent(monkeypatch):
    _no_overrides(monkeypatch)
    row = day_pay_service.compensation("PRACA", pay_day_value=0.5)
    assert row["pay_equivalent_days"] == 0.5


def test_pending_day_has_no_pay_percent():
    row = day_pay_service.mark_pending({})
    assert row["payroll_pending"] is True
    assert row["pay_percent"] is None
    assert row["pay_equivalent_days"] is None


def test_team_calendar_labels_force_majeure_and_shifts():
    assert _leave_code("sila_wyzsza") == "ŚW"
    assert _leave_code("urlop_bezplatny") == "UB"
    assert _slot_text("RANO") == "06–14"
    assert _slot_text("POPO") == "14–22"
