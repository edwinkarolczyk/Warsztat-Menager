from datetime import date, timedelta

import pytest

from grafiki import shifts_schedule as ss
from test_config_manager import make_manager


@pytest.fixture(autouse=True)
def cfg_env(monkeypatch, make_manager):
    schema = {
        "config_version": 1,
        "options": [{"key": "shifts.anchor_monday", "type": "string"}],
    }
    defaults = {"shifts": {"anchor_monday": "2025-01-06"}}
    mgr, _ = make_manager(defaults=defaults, schema=schema)
    monkeypatch.setattr(ss, "ConfigManager", lambda: mgr)
    yield


def test_set_anchor_monday_invalid_format():
    with pytest.raises(ValueError, match="invalid date format"):
        ss.set_anchor_monday("2024/01/01")


def test_set_anchor_monday_past_date():
    past = (date.today() - timedelta(days=7)).isoformat()
    with pytest.raises(ValueError, match="in the past"):
        ss.set_anchor_monday(past)


def test_set_anchor_monday_far_future():
    far_future = (date.today() + timedelta(days=400)).isoformat()
    with pytest.raises(ValueError, match="too far in the future"):
        ss.set_anchor_monday(far_future)
