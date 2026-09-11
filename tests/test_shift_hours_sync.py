# version: 1.1
from datetime import datetime, time

from gui import widgets_user_footer as user_footer
from services import attendance_service


CUSTOM_SHIFT_TIMES = {
    "R_START": time(5, 30),
    "R_END": time(13, 30),
    "P_START": time(13, 30),
    "P_END": time(21, 30),
}


def _custom_shift_times():
    return dict(CUSTOM_SHIFT_TIMES)


def test_attendance_reads_canonical_shift_time_mapping(monkeypatch):
    monkeypatch.setattr(
        attendance_service,
        "_grafik_shift_times",
        _custom_shift_times,
    )

    rules = attendance_service._shift_rules()

    assert rules["RANO"]["shift_start"] == time(5, 30)
    assert rules["RANO"]["shift_end"] == time(13, 30)
    assert rules["RANO"]["early_from"] == time(4, 30)
    assert rules["RANO"]["auto_until"] == time(11, 30)
    assert rules["POPO"]["shift_start"] == time(13, 30)
    assert rules["POPO"]["shift_end"] == time(21, 30)
    assert rules["POPO"]["early_from"] == time(12, 30)
    assert rules["POPO"]["auto_until"] == time(19, 30)


def test_login_uses_canonical_shift_hours(monkeypatch):
    import gui_logowanie

    monkeypatch.setattr(
        gui_logowanie.shifts_schedule,
        "_shift_times",
        _custom_shift_times,
    )

    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 5, 29)) is None
    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 5, 30)) == "RANO"
    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 13, 29)) == "RANO"
    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 13, 30)) == "POPO"
    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 21, 29)) == "POPO"
    assert gui_logowanie._slot_now(datetime(2026, 9, 11, 21, 30)) is None

    start, end = gui_logowanie._shift_bounds_for_slot(
        datetime(2026, 9, 11, 8, 0),
        "RANO",
    )
    assert start == datetime(2026, 9, 11, 5, 30)
    assert end == datetime(2026, 9, 11, 13, 30)

    start, end = gui_logowanie._shift_bounds_for_slot(
        datetime(2026, 9, 11, 18, 0),
        "POPO",
    )
    assert start == datetime(2026, 9, 11, 13, 30)
    assert end == datetime(2026, 9, 11, 21, 30)


def test_footer_progress_uses_canonical_shift_hours(monkeypatch):
    monkeypatch.setattr(
        user_footer.shifts_schedule,
        "_shift_times",
        _custom_shift_times,
    )

    start, end, label = user_footer._shift_bounds(datetime(2026, 9, 11, 9, 30))
    assert (start, end, label) == (
        datetime(2026, 9, 11, 5, 30),
        datetime(2026, 9, 11, 13, 30),
        "RANO",
    )
    assert user_footer._shift_progress(datetime(2026, 9, 11, 9, 30)) == (50, True)

    start, end, label = user_footer._shift_bounds(datetime(2026, 9, 11, 17, 30))
    assert (start, end, label) == (
        datetime(2026, 9, 11, 13, 30),
        datetime(2026, 9, 11, 21, 30),
        "POŁUDNIE",
    )

    start, end, label = user_footer._shift_bounds(datetime(2026, 9, 11, 22, 30))
    assert (start, end, label) == (
        datetime(2026, 9, 11, 21, 30),
        datetime(2026, 9, 12, 5, 30),
        "NOC",
    )
