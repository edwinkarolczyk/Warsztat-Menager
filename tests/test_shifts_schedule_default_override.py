from grafiki import shifts_schedule
from test_config_manager import make_manager


def test_set_user_mode_overrides_default(make_manager, monkeypatch):
    schema = {
        "config_version": 1,
        "options": [
            {"key": "shifts.modes", "type": "dict", "value_type": "string"},
            {"key": "shifts.patterns", "type": "dict", "value_type": "string"},
            {"key": "shifts.anchor_monday", "type": "string"},
        ],
    }
    defaults = {
        "shifts": {
            "anchor_monday": "2025-09-01",
            "patterns": {"111": "111", "112": "112", "121": "121"},
            "modes": {},
        }
    }
    mgr, _ = make_manager(defaults=defaults, schema=schema)
    monkeypatch.setattr(shifts_schedule, "ConfigManager", lambda: mgr)

    shifts_schedule._USER_DEFAULTS.clear()
    shifts_schedule._load_users()
    assert shifts_schedule._user_mode("dawid") == "111"

    shifts_schedule.set_user_mode("dawid", "112")
    assert shifts_schedule._user_mode("dawid") == "112"
    assert mgr.get("shifts.modes")["dawid"] == "112"

