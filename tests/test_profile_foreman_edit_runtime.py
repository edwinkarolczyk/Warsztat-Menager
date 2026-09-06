from __version__ import __version__
import profile_employee_editor_finish_runtime as finish_runtime
from profile_employee_editor_finish_runtime import (
    _attendance_export_rows,
    _employee_inconsistencies,
    _employee_key,
    _human_action,
    _refresh_open_profile_views,
)
from profile_foreman_edit_runtime import _parse_carryover


def test_profile_release_is_current():
    assert __version__ == "0.11.0"


def test_carryover_keeps_source_years():
    assert _parse_carryover("2024=2; 2025=4", 2026) == {2024: 2.0, 2025: 4.0}


def test_carryover_rejects_current_year():
    try:
        _parse_carryover("2026=1", 2026)
    except ValueError:
        return
    raise AssertionError("Bieżący rok nie może być zapisany jako urlop zaległy")


def test_employee_window_key_uses_stable_user_id(monkeypatch):
    class Owner:
        def winfo_toplevel(self):
            return self

    owner = Owner()
    monkeypatch.setattr(
        "profile_employee_editor_finish_runtime.workforce_profile_service.get_user",
        lambda _login: {"user_id": "USR-0042"},
    )

    assert _employee_key(owner, "jan") == _employee_key(owner, "jan.po.zmianie")


def test_history_humanizes_shift_move():
    title, detail = _human_action(
        {
            "action": "manual_day_move",
            "before": {"slot": "RANO", "day_value": 1.0},
            "after": {"slot": "POPO", "day_value": 1.0},
            "note": "Zmiana RANO → POPO.",
        }
    )

    assert title == "Zmiana zmiany"
    assert "zmiana: RANO → POPO" in detail


def test_refresh_notifies_profile_and_foreman_panel():
    calls = []

    ForemanProfilePanel = type("ForemanProfilePanel", (), {})
    panel = ForemanProfilePanel()
    panel.winfo_children = lambda: []
    panel.refresh_data = lambda: calls.append("foreman")
    panel.after_idle = lambda callback: callback()

    ProfileView = type("ProfileView", (), {})
    profile = ProfileView()
    profile.winfo_children = lambda: []
    profile._refresh_view = lambda: calls.append("profile")
    profile.after_idle = lambda callback: callback()

    class Owner:
        def __init__(self):
            self.events = []

        def winfo_toplevel(self):
            return self

        def winfo_children(self):
            return [panel, profile]

        def event_generate(self, name, when=None):
            self.events.append((name, when))

    owner = Owner()
    _refresh_open_profile_views(owner)

    assert ("<<ProfileDataUpdated>>", "tail") in owner.events
    assert calls == ["foreman", "profile"]


def test_monthly_export_rows_include_shift_absence_and_overtime(monkeypatch):
    monkeypatch.setattr(
        finish_runtime.attendance_service,
        "month_records",
        lambda _login, _year, _month: [
            {
                "date": "2026-09-07",
                "slot": "POPO",
                "status": finish_runtime.attendance_service.STATUS_PRESENT,
                "day_value": 1.0,
                "first_login_ts": "2026-09-07T13:55:00",
                "source": "auto_login",
                "overtime": {"hours": 2.0, "type": "zwykle", "note": "pilne"},
            }
        ],
    )
    monkeypatch.setattr(
        finish_runtime,
        "_absence_codes",
        lambda _login, day, _row=None: ["ŚW"] if day == "2026-09-07" else [],
    )

    rows = _attendance_export_rows("jan", 2026, 9)

    assert rows == [
        {
            "date": "2026-09-07",
            "slot": "POPO",
            "first_login": "13:55:00",
            "status": "Obecny",
            "day_value": 1.0,
            "absence": "ŚW",
            "overtime_hours": 2.0,
            "overtime_type": "zwykle",
            "source": "auto_login",
            "note": "pilne",
        }
    ]


def test_employee_inconsistencies_include_conflict_and_double_shift():
    issues = _employee_inconsistencies(
        "jan",
        2026,
        9,
        decisions=[
            {
                "login": "jan",
                "date": "2026-09-08",
                "slot": "RANO",
                "is_conflict": True,
                "decision_label": "L4 + Obecny",
            }
        ],
        records=[
            {"date": "2026-09-09", "slot": "RANO", "synthetic": False},
            {"date": "2026-09-09", "slot": "POPO", "synthetic": False},
        ],
    )

    assert {issue["kind"] for issue in issues} == {"Konflikt", "Duplikat zmiany"}
    assert any(issue["text"] == "L4 + Obecny" for issue in issues)


def test_employee_inconsistencies_are_empty_when_data_is_clean():
    assert _employee_inconsistencies("jan", 2026, 9, decisions=[], records=[]) == []
