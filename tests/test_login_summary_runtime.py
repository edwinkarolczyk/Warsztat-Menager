# WM-VERSION: 0.1

from datetime import datetime, timezone

import login_summary_runtime as LSR


def _snapshot(**overrides):
    base = {
        "previous": datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc),
        "new_pm": [],
        "changed_dysp": [],
        "activity": [],
        "tool_tasks_changed": False,
    }
    base.update(overrides)
    return base


def test_first_login_summary_is_allowed():
    assert LSR._should_show_summary(_snapshot(previous=None)) is True


def test_unchanged_summary_is_not_shown_again():
    assert LSR._should_show_summary(_snapshot()) is False


def test_new_pm_or_dysp_or_activity_triggers_summary():
    assert LSR._should_show_summary(_snapshot(new_pm=[{"id": "m1"}])) is True
    assert LSR._should_show_summary(_snapshot(changed_dysp=[{"id": "d1"}])) is True
    assert LSR._should_show_summary(_snapshot(activity=[{"event": "x"}])) is True


def test_changed_tool_tasks_trigger_summary():
    assert LSR._should_show_summary(_snapshot(tool_tasks_changed=True)) is True


def test_tool_task_keys_are_stable_and_order_independent():
    rows = [
        {"tool": "002", "tool_name": "Wiertarka", "task": "Sprawdź uchwyt"},
        {"tool": "001", "tool_name": "Tokarka", "task": "Wymień osłonę"},
    ]
    reversed_rows = list(reversed(rows))

    assert LSR._tool_task_keys(rows) == LSR._tool_task_keys(reversed_rows)


def test_login_marker_persists_last_login_and_task_state(monkeypatch, tmp_path):
    state_path = tmp_path / "login_summary_state.json"
    monkeypatch.setattr(LSR, "_state_path", lambda: state_path)

    when = datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)
    tasks = [{"tool": "001", "tool_name": "Tokarka", "task": "Wymień osłonę"}]
    LSR._save_login_marker("Edwin", when, tool_tasks=tasks)

    state = LSR._read_state()
    assert "edwin" in state
    assert state["edwin"]["last_login"] == "2026-09-25T06:30:00Z"
    assert state["edwin"]["tool_tasks"] == [
        "001|Tokarka|Wymień osłonę"
    ]
