import importlib
from datetime import date, time, timedelta

import grafiki.shifts_schedule as shifts_schedule


# Helper to avoid reading actual files

def _patch_loads(monkeypatch, modes=None, users=None):
    if modes is None:
        modes = {"anchor_monday": "2025-01-06", "patterns": {}, "modes": {}}
    if users is None:
        users = []
    monkeypatch.setattr(shifts_schedule, "_load_modes", lambda: modes)
    monkeypatch.setattr(shifts_schedule, "_load_users", lambda: users)
    return modes


def test_slot_for_mode_patterns(monkeypatch):
    _patch_loads(monkeypatch)
    cases = [
        ("211", 0, "POPO"),
        ("211", 1, "RANO"),
        ("211", 2, "RANO"),
        ("211", 3, "POPO"),
        ("1212", 0, "RANO"),
        ("1212", 1, "POPO"),
        ("1212", 2, "RANO"),
        ("1212", 3, "POPO"),
    ]
    for pattern, week_idx, expected in cases:
        assert shifts_schedule._slot_for_mode(pattern, week_idx) == expected


def test_week_matrix_with_saturday(monkeypatch):
    modes = {"anchor_monday": "2025-01-06", "patterns": {}, "modes": {"1": "1212"}}
    users = [{"id": "1", "name": "Ala", "active": True}]
    _patch_loads(monkeypatch, modes=modes, users=users)
    monkeypatch.setattr(
        shifts_schedule,
        "_shift_times",
        lambda: {
            "R_START": time(6, 0),
            "R_END": time(14, 0),
            "P_START": time(14, 0),
            "P_END": time(22, 0),
        },
    )
    result = shifts_schedule.week_matrix(date(2025, 1, 11))
    assert result["week_start"] == "2025-01-06"
    assert len(result["rows"]) == 1
    saturday = result["rows"][0]["days"][5]
    assert saturday["date"] == "2025-01-11"
    assert saturday["dow"] == "Sat"


def test_set_anchor_monday(monkeypatch):
    modes = {"anchor_monday": "2025-01-06", "patterns": {}, "modes": {}}
    saved = {}

    def fake_save(path, data):
        saved.update(data)

    monkeypatch.setattr(shifts_schedule, "_load_modes", lambda: modes)
    monkeypatch.setattr(shifts_schedule, "_save_json", fake_save)

    assert shifts_schedule._anchor_monday() == date(2025, 1, 6)
    future = date.today() + timedelta(days=14)
    shifts_schedule.set_anchor_monday(future.isoformat())
    expected = future - timedelta(days=future.weekday())
    assert saved["anchor_monday"] == expected.isoformat()
    assert shifts_schedule._anchor_monday() == expected


def test_patterns_subset_defaults(monkeypatch):
    patterns = {
        "111": "111",
        "112": "112",
        "12": "12",
        "121": "121",
        "211": "211",
        "1212": "1212",
    }
    modes = {"anchor_monday": "2025-01-06", "patterns": patterns, "modes": {}}
    _patch_loads(monkeypatch, modes=modes)
    available = shifts_schedule._available_patterns()
    for pattern in available.values():
        assert pattern in shifts_schedule._DEFAULT_PATTERNS


def test_slot_for_mode_121(monkeypatch):
    _patch_loads(monkeypatch)
    assert shifts_schedule._slot_for_mode("121", 0) == "RANO"
    assert shifts_schedule._slot_for_mode("121", 1) == "POPO"
    assert shifts_schedule._slot_for_mode("121", 2) == "RANO"

