from __future__ import annotations

import pytest

import profile_foreman_edit_runtime as foreman_runtime
from services import attendance_service as attendance


@pytest.mark.parametrize(
    "raw",
    [-1, "-0,5", "abc", float("nan"), float("inf"), float("-inf")],
)
def test_overtime_rejects_invalid_value_before_record_access(monkeypatch, raw):
    def fail_record(*_args, **_kwargs):
        raise AssertionError("_record nie może zostać wywołany dla błędnych nadgodzin")

    monkeypatch.setattr(attendance, "_record", fail_record)

    with pytest.raises(ValueError):
        attendance.set_overtime(
            "2026-09-18", "RANO", "jan", raw, "brygadzista"
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0.0), (1.5, 1.5), ("1,5", 1.5)],
)
def test_overtime_validator_accepts_valid_values(raw, expected):
    assert attendance.validate_overtime_hours(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0.0), ("0,5", 0.5), (1, 1.0)],
)
def test_manual_day_validator_accepts_supported_values(raw, expected):
    assert attendance.validate_manual_day_value(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["abc", float("nan"), float("inf"), float("-inf"), -0.5, 0.25, 1.5],
)
def test_manual_day_validator_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        attendance.validate_manual_day_value(raw)


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
