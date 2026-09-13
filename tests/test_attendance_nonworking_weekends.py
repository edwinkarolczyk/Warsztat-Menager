from datetime import datetime
from unittest.mock import Mock

import pytest

from services import attendance_service as attendance


@pytest.mark.parametrize('workdays, expected', [
    ({0, 1, 2, 3, 4}, []),
    ({0, 1, 2, 3, 4, 5}, ['2026-09-05']),
    ({0, 1, 2, 3, 4, 6}, ['2026-09-06']),
])
def test_stored_empty_weekend_plans_follow_employee_schedule(
    monkeypatch, workdays, expected,
):
    rows = [{'date': day, 'slot': 'RANO', 'planned': True,
             'logged_ts': '', 'confirmed': False}
            for day in ['2026-09-05', '2026-09-06']]
    monkeypatch.setattr(attendance, '_actual_month_records', lambda *a: rows)
    monkeypatch.setattr(attendance, 'user_id_for', lambda login: 'USR-1')
    monkeypatch.setattr(attendance, '_planned_slot_for_day',
                        lambda login, day: 'RANO' if day.weekday() in workdays else None)
    writer = Mock()
    monkeypatch.setattr(attendance, '_write', writer)
    now = datetime(2026, 9, 7)
    result = attendance.month_records('marek', 2026, 9, now=now)
    weekends = [r['date'] for r in result if r['date'] in {'2026-09-05', '2026-09-06'}]
    assert weekends == expected
    summary = attendance.summary_for_month('marek', 2026, 9, now=now)
    assert summary['missing'] == 4 + len(expected)
    writer.assert_not_called()
    assert all('status' not in row for row in rows)


@pytest.mark.parametrize('evidence', [
    {'logged_ts': '2026-09-05T06:00:00'},
    {'first_login_ts': '2026-09-05T06:00:00'},
    {'source': 'foreman', 'day_value': 0},
    {'status': attendance.STATUS_PRESENT, 'day_value': 1},
    {'reason': 'L4'},
    {'overtime': {'hours': 2, 'status': 'confirmed'}},
    {'confirmed': True},
    {'note': 'Uzgodniona korekta'},
])
def test_real_weekend_record_remains_visible(monkeypatch, evidence):
    row = {'date': '2026-09-05', 'slot': 'RANO', 'planned': True,
           'status': attendance.STATUS_MISSING, **evidence}
    monkeypatch.setattr(attendance, '_actual_month_records', lambda *a: [row])
    monkeypatch.setattr(attendance, '_planned_slot_for_day', lambda *a: None)
    result = attendance.month_records('marek', 2026, 9, now=datetime(2026, 9, 7))
    assert len(result) == 1
    assert result[0]['date'] == '2026-09-05'
