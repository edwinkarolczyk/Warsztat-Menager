# version: 1.2
from datetime import date, time, timedelta

import grafiki.shifts_schedule as shifts_schedule
from test_config_manager import make_manager


def _patch_loads(monkeypatch, modes=None, users=None):
    if modes is None:
        modes = {
            "anchor_monday": "2025-01-06",
            "patterns": {},
            "modes": {},
            "user_anchor": {},
        }
    if users is None:
        users = []
    monkeypatch.setattr(shifts_schedule, "_load_modes", lambda: modes)
    monkeypatch.setattr(shifts_schedule, "_load_users", lambda: users)
    return modes


def test_exactly_four_canonical_patterns(monkeypatch):
    stale = {
        "anchor_monday": "2025-01-06",
        "patterns": {
            "111": "111",
            "222": "222",
            "121": "121",
            "212": "212",
            "112": "112",
            "12": "12",
            "21": "21",
        },
        "modes": {},
        "user_anchor": {},
    }
    _patch_loads(monkeypatch, modes=stale)
    assert shifts_schedule._available_patterns() == {
        "11": "11",
        "22": "22",
        "12": "12",
        "21": "21",
    }


def test_two_week_cycle_and_wrap(monkeypatch):
    _patch_loads(monkeypatch)
    expected = {
        "11": ["RANO", "RANO", "RANO", "RANO", "RANO", "RANO"],
        "22": ["POPO", "POPO", "POPO", "POPO", "POPO", "POPO"],
        "12": ["RANO", "POPO", "RANO", "POPO", "RANO", "POPO"],
        "21": ["POPO", "RANO", "POPO", "RANO", "POPO", "RANO"],
    }
    for mode, slots in expected.items():
        assert [shifts_schedule._slot_for_mode(mode, idx) for idx in range(6)] == slots


def test_alternating_modes_are_complementary(monkeypatch):
    _patch_loads(monkeypatch)
    for week_idx in range(-4, 8):
        assert shifts_schedule._slot_for_mode("12", week_idx) != shifts_schedule._slot_for_mode(
            "21", week_idx
        )


def test_legacy_aliases_are_canonicalized(monkeypatch):
    _patch_loads(monkeypatch)
    assert shifts_schedule._normalize_mode("111") == "11"
    assert shifts_schedule._normalize_mode("1111") == "11"
    assert shifts_schedule._normalize_mode("222") == "22"
    assert shifts_schedule._normalize_mode("2222") == "22"
    assert shifts_schedule._normalize_mode("112") == "12"
    assert shifts_schedule._normalize_mode("121") == "12"
    assert shifts_schedule._normalize_mode("1212") == "12"
    assert shifts_schedule._normalize_mode("212") == "21"
    assert shifts_schedule._normalize_mode("2121") == "21"
    assert shifts_schedule._normalize_mode("I") == "11"
    assert shifts_schedule._normalize_mode("II") == "22"


def test_each_employee_has_independent_anchor(monkeypatch):
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "121", "rotacja_start": ""},
        {"id": "USR-0002", "login": "ola", "name": "Ola", "active": True, "tryb_zmian": "121", "rotacja_start": ""},
    ]
    modes = {
        "anchor_monday": "2025-01-06",
        "patterns": {},
        "modes": {"USR-0001": "121", "USR-0002": "121"},
        "user_anchor": {"USR-0001": "2026-08-31", "USR-0002": "2026-09-07"},
    }
    _patch_loads(monkeypatch, modes=modes, users=users)

    same_day = date(2026, 9, 14)
    assert shifts_schedule._week_idx_for_user("USR-0001", same_day) == 2
    assert shifts_schedule._week_idx_for_user("USR-0002", same_day) == 1
    assert shifts_schedule._slot_for_mode(
        shifts_schedule._user_mode("USR-0001"),
        shifts_schedule._week_idx_for_user("USR-0001", same_day),
    ) == "RANO"
    assert shifts_schedule._slot_for_mode(
        shifts_schedule._user_mode("USR-0002"),
        shifts_schedule._week_idx_for_user("USR-0002", same_day),
    ) == "POPO"


def test_anchor_is_normalized_to_monday_and_legacy_login_is_fallback(monkeypatch):
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "111", "rotacja_start": ""}
    ]
    modes = {
        "anchor_monday": "2025-01-06",
        "patterns": {},
        "modes": {"ala": "2121"},
        "user_anchor": {"ala": "2026-09-03"},
    }
    _patch_loads(monkeypatch, modes=modes, users=users)

    mode, anchor = shifts_schedule.get_user_schedule("USR-0001")
    assert mode == "21"
    assert anchor == "2026-08-31"


def test_stable_user_id_wins_over_legacy_login(monkeypatch):
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "111", "rotacja_start": ""}
    ]
    modes = {
        "anchor_monday": "2025-01-06",
        "patterns": {},
        "modes": {"USR-0001": "121", "ala": "222"},
        "user_anchor": {"USR-0001": "2026-08-31", "ala": "2026-09-07"},
    }
    _patch_loads(monkeypatch, modes=modes, users=users)

    assert shifts_schedule.get_user_schedule("USR-0001") == ("12", "2026-08-31")


def test_cycle_handles_year_boundary_and_dates_before_anchor(monkeypatch):
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "121", "rotacja_start": ""}
    ]
    modes = {
        "anchor_monday": "2025-01-06",
        "patterns": {},
        "modes": {"USR-0001": "121"},
        "user_anchor": {"USR-0001": "2025-12-29"},
    }
    _patch_loads(monkeypatch, modes=modes, users=users)

    assert shifts_schedule._week_idx_for_user("USR-0001", date(2026, 1, 19)) == 3
    assert shifts_schedule._slot_for_mode("121", 3) == "POPO"
    assert shifts_schedule._week_idx_for_user("USR-0001", date(2025, 12, 22)) == -1
    assert shifts_schedule._slot_for_mode("121", -1) == "POPO"


def test_week_matrix_with_saturday(monkeypatch):
    modes = {
        "anchor_monday": "2025-01-06",
        "patterns": {},
        "modes": {"USR-0001": "121"},
        "user_anchor": {"USR-0001": "2025-01-06"},
    }
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "121", "rotacja_start": ""}
    ]
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
    assert result["rows"][0]["mode"] == "12"
    saturday = result["rows"][0]["days"][5]
    assert saturday["date"] == "2025-01-11"
    assert saturday["dow"] == "Sat"
    assert saturday["shift"] == "R"


def test_global_anchor_does_not_drive_employee_schedule(monkeypatch):
    users = [
        {"id": "USR-0001", "login": "ala", "name": "Ala", "active": True, "tryb_zmian": "112", "rotacja_start": ""}
    ]
    modes = {
        "anchor_monday": "2035-12-31",
        "patterns": {},
        "modes": {"USR-0001": "112"},
        "user_anchor": {},
    }
    _patch_loads(monkeypatch, modes=modes, users=users)

    mode, anchor = shifts_schedule.get_user_schedule("USR-0001")
    assert mode == "12"
    assert anchor == "2025-01-06"


def test_set_anchor_monday(monkeypatch, make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "shifts.anchor_monday", "type": "string"}],
    }
    defaults = {"shifts": {"anchor_monday": "2025-01-06"}}
    mgr, _ = make_manager(defaults=defaults, schema=schema)
    monkeypatch.setattr(shifts_schedule, "ConfigManager", lambda: mgr)

    assert shifts_schedule._anchor_monday() == date(2025, 1, 6)
    future = date.today() + timedelta(days=14)
    shifts_schedule.set_anchor_monday(future.isoformat())
    expected = future - timedelta(days=future.weekday())
    assert mgr.get("shifts.anchor_monday") == expected.isoformat()
    assert shifts_schedule._anchor_monday() == expected