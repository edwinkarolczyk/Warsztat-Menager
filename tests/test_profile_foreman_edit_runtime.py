from __version__ import __version__

import pytest

import profile_attendance_export_runtime as export_runtime
import profile_employee_editor_finish_runtime as finish_runtime
import profile_foreman_edit_runtime as foreman_runtime
import profile_shift_mode_sync_runtime as shift_mode_runtime
from grafiki import shifts_schedule
from profile_employee_editor_finish_runtime import (
    _attendance_export_rows,
    _employee_inconsistencies,
    _employee_key,
    _human_action,
    _refresh_open_profile_views,
)
from profile_foreman_edit_runtime import _parse_carryover


def test_profile_release_is_current():
    assert __version__ == "0.13.3"


def test_profile_shift_modes_match_engine_and_add_dialog():
    expected_codes = tuple(code for code, _label in shift_mode_runtime.SHIFT_MODE_OPTIONS)
    assert expected_codes == tuple(shifts_schedule.TRYBY)
    assert expected_codes == ("111", "112", "222", "121", "212")

    import ustawienia_uzytkownicy as settings_profiles

    shift_mode_runtime._patch_add_profile_dialog()
    assert tuple(settings_profiles.ProfileEditDialog.SHIFT_MODES) == shift_mode_runtime.SHIFT_MODE_OPTIONS


def test_profile_shift_mode_options_are_built_from_engine(monkeypatch):
    monkeypatch.setattr(shifts_schedule, "TRYBY", ["111", "112", "212"])
    options = shift_mode_runtime._build_shift_mode_options()
    assert tuple(code for code, _label in options) == ("111", "112", "212")


def test_profile_shift_mode_sync_patches_legacy_users_panel():
    import gui_uzytkownicy as legacy_users

    shift_mode_runtime._patch_legacy_users_panel()
    assert tuple(legacy_users.SHIFT_MODE_CHOICES.values()) == tuple(shifts_schedule.TRYBY)


def test_profile_shift_mode_labels_save_as_codes():
    labels = dict(shift_mode_runtime.SHIFT_MODE_OPTIONS)
    assert shift_mode_runtime._mode_code(labels["111"]) == "111"
    assert shift_mode_runtime._mode_code(labels["112"]) == "112"
    assert shift_mode_runtime._mode_code(labels["222"]) == "222"
    assert shift_mode_runtime._mode_code(labels["121"]) == "121"
    assert shift_mode_runtime._mode_code(labels["212"]) == "212"
    assert shift_mode_runtime._mode_label("112") == labels["112"]


def test_carryover_keeps_source_years():
    assert _parse_carryover("2024=2; 2025=4", 2026) == {2024: 2.0, 2025: 4.0}


def test_carryover_rejects_current_year():
    try:
        _parse_carryover("2026=1", 2026)
    except ValueError:
        return
    raise AssertionError("Bieżący rok nie może być zapisany jako urlop zaległy")


@pytest.mark.parametrize(
    "raw_overtime",
    ["-1", "abc", "nan", "inf", "-inf"],
)
def test_invalid_overtime_blocks_day_write(monkeypatch, raw_overtime):
    calls = []
    monkeypatch.setattr(
        foreman_runtime.attendance_service,
        "set_manual_day",
        lambda *_args, **_kwargs: calls.append("day"),
    )
    monkeypatch.setattr(
        foreman_runtime.attendance_service,
        "set_overtime",
        lambda *_args, **_kwargs: calls.append("overtime"),
    )

    with pytest.raises(ValueError):
        foreman_runtime._save_attendance_correction(
            "2026-09-18",
            "RANO",
            "jan",
            "1",
            "brygadzista",
            "",
            overtime_enabled=True,
            overtime_hours=raw_overtime,
            overtime_type="zwykle",
        )

    assert calls == []


def test_valid_attendance_correction_writes_day_then_overtime(monkeypatch):
    calls = []

    def save_day(date_ymd, slot, login, value, actor, note):
        calls.append(("day", date_ymd, slot, login, value, actor, note))

    def save_overtime(
        date_ymd, slot, login, hours, actor, *, overtime_type, note
    ):
        calls.append(
            (
                "overtime",
                date_ymd,
                slot,
                login,
                hours,
                actor,
                overtime_type,
                note,
            )
        )

    monkeypatch.setattr(
        foreman_runtime.attendance_service, "set_manual_day", save_day
    )
    monkeypatch.setattr(
        foreman_runtime.attendance_service, "set_overtime", save_overtime
    )

    foreman_runtime._save_attendance_correction(
        "2026-09-18",
        "RANO",
        "jan",
        "0,5",
        "brygadzista",
        "korekta",
        overtime_enabled=True,
        overtime_hours="1,5",
        overtime_type="zwykle",
    )

    assert [row[0] for row in calls] == ["day", "overtime"]
    assert calls[0][4] == 0.5
    assert calls[1][4] == 1.5


@pytest.mark.parametrize(
    "raw",
    [-1, "-0,5", "abc", float("nan"), float("inf"), float("-inf")],
)
def test_overtime_rejects_invalid_value_before_record_access(monkeypatch, raw):
    def fail_record(*_args, **_kwargs):
        raise AssertionError("_record nie może zostać wywołany dla błędnych nadgodzin")

    monkeypatch.setattr(foreman_runtime.attendance_service, "_record", fail_record)

    with pytest.raises(ValueError):
        foreman_runtime.attendance_service.set_overtime(
            "2026-09-18", "RANO", "jan", raw, "brygadzista"
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0.0), (1.5, 1.5), ("1,5", 1.5)],
)
def test_overtime_validator_accepts_valid_values(raw, expected):
    assert foreman_runtime.attendance_service.validate_overtime_hours(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0.0), ("0,5", 0.5), (1, 1.0)],
)
def test_manual_day_validator_accepts_supported_values(raw, expected):
    assert foreman_runtime.attendance_service.validate_manual_day_value(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["abc", float("nan"), float("inf"), float("-inf"), -0.5, 0.25, 1.5],
)
def test_manual_day_validator_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        foreman_runtime.attendance_service.validate_manual_day_value(raw)


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


def test_a3_month_export_reads_absences_once_and_keeps_identity(monkeypatch):
    calls = {"leaves": 0}

    monkeypatch.setattr(
        export_runtime.attendance_service,
        "month_records",
        lambda _login, _year, _month: [
            {
                "date": "2026-09-07",
                "slot": "RANO",
                "status": export_runtime.attendance_service.STATUS_PRESENT,
                "day_value": 1.0,
                "source": "auto_login",
            }
        ],
    )
    monkeypatch.setattr(
        export_runtime.workforce_profile_service,
        "get_user",
        lambda _login: {"user_id": "USR-0042", "login": "jan"},
    )

    def read_leaves():
        calls["leaves"] += 1
        return [
            {
                "user_id": "USR-0042",
                "login_snapshot": "jan.stary",
                "date": "2026-09-07",
                "type": "L4",
            },
            {
                "login": "jan",
                "date": "2026-09-08",
                "type": "urlop",
            },
            {
                "user_id": "USR-9999",
                "login": "inny",
                "date": "2026-09-09",
                "type": "NN",
            },
            {
                "user_id": "USR-0042",
                "date": "2026-10-01",
                "type": "NN",
            },
        ]

    monkeypatch.setattr(export_runtime.leave_workflow_service, "read_leaves", read_leaves)

    rows = export_runtime._attendance_export_rows("jan", 2026, 9)

    assert calls["leaves"] == 1
    by_day = {row["date"]: row for row in rows}
    assert by_day["2026-09-07"]["absence"] == "L4"
    assert by_day["2026-09-08"]["absence"] == "UR"
    assert by_day["2026-09-08"]["status"] == "Nieobecność"
    assert "2026-09-09" not in by_day
    assert "2026-10-01" not in by_day
