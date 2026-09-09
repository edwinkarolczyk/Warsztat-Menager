# version: 1.0
"""Regresje końcowego workspace Brygadzisty."""

import pytest

import profile_foreman_workspace_runtime as workspace


def test_full_attendance_edit_accepts_work_with_force_majeure():
    payload = workspace._validate_attendance_edit(
        "2026-09-07",
        "RANO",
        "1",
        "ŚW",
        "2.5",
        "05:57",
    )

    assert payload["date"] == "2026-09-07"
    assert payload["slot"] == "RANO"
    assert payload["day_value"] == 1.0
    assert payload["absence"] == "ŚW"
    assert payload["overtime_hours"] == 2.5
    assert payload["first_login"] == "05:57"


def test_full_attendance_edit_blocks_day_value_for_l4():
    with pytest.raises(ValueError, match="dniówka musi wynosić 0"):
        workspace._validate_attendance_edit(
            "2026-09-07",
            "RANO",
            "1",
            "L4",
            "0",
            "",
        )


def test_full_attendance_edit_blocks_overtime_for_unpaid_leave():
    with pytest.raises(ValueError, match="nie zapisuj nadgodzin"):
        workspace._validate_attendance_edit(
            "2026-09-07",
            "POPO",
            "0",
            "UB",
            "1",
            "14:02",
        )


def test_full_attendance_edit_accepts_unpaid_leave_and_empty_login_time():
    payload = workspace._validate_attendance_edit(
        "2026-09-07",
        "POPO",
        "0",
        "urlop bezpłatny",
        "0",
        "",
    )

    assert payload["absence"] == "UB"
    assert payload["first_login"] == ""


def test_full_attendance_edit_rejects_invalid_login_time():
    with pytest.raises(ValueError, match="GG:MM"):
        workspace._validate_attendance_edit(
            "2026-09-07",
            "RANO",
            "1",
            "Brak",
            "0",
            "5 rano",
        )


def test_workspace_contains_all_supported_absence_choices():
    assert workspace._ABSENCE_CHOICES == ("Brak", "ŚW", "L4", "NN", "UR", "UŻ", "UB")
