from types import SimpleNamespace
from unittest.mock import Mock

from services import attendance_service as attendance
import wm_operational_followup_runtime as followup


def test_decisions_reuse_month_without_changing_results(monkeypatch):
    rows = [
        {'status': attendance.STATUS_MISSING},
        {'status': attendance.STATUS_PENDING_LATE},
        {'status': attendance.STATUS_SATURDAY},
        {'status': attendance.STATUS_PRESENT},
        {'status': attendance.STATUS_MISSING, 'approval_required': False},
        {'status': attendance.STATUS_EXCUSED, 'reason': 'L4'},
    ]
    source = Mock(return_value=rows)
    monkeypatch.setattr(attendance, 'month_records', source)
    expected = attendance.decision_records('marek', 2026, 9)
    source.reset_mock()
    assert attendance.decision_records_from_rows(rows) == expected
    source.assert_not_called()
    assert len(expected) == 3
    assert all('decision_label' not in row for row in rows)


def test_online_column_preserves_headings_and_widths(monkeypatch):
    class Tree:
        def __init__(self):
            self.columns = ['name', 'today', 'days']
            self.headings = {c: {'text': c.upper(), 'anchor': 'w', 'state': ''}
                             for c in self.columns}
            self.settings = {c: {'id': c, 'width': 123, 'anchor': 'center',
                                 'minwidth': 40, 'stretch': False}
                             for c in self.columns}
            self.values = ['Marek', 'Obecny', '5']

        def cget(self, key):
            return self.columns

        def configure(self, **kwargs):
            self.columns = kwargs['columns']
            self.headings = {c: {} for c in self.columns}
            self.settings = {c: {} for c in self.columns}

        def heading(self, key, **kwargs):
            if kwargs:
                self.headings[key].update(kwargs)
            return self.headings[key]

        def column(self, key, **kwargs):
            if kwargs:
                self.settings[key].update(kwargs)
            return self.settings[key]

        def get_children(self, parent):
            return ['row']

        def item(self, iid, option=None, **kwargs):
            if kwargs:
                self.values = kwargs['values']
            return self.values

    tree = Tree()
    monkeypatch.setattr(followup, '_online_logins', lambda: {'marek'})
    panel = SimpleNamespace(_wm_attendance_tree=tree,
                            _wm_attendance_user_by_iid={'row': 'Marek'})
    followup._decorate_online_column(panel)
    assert tree.values == ['Marek', 'Obecny', '● online', '5']
    for key in ['name', 'today', 'days']:
        assert tree.headings[key]['text'] == key.upper()
        assert tree.settings[key]['width'] == 123
    followup._decorate_online_column(panel)
    assert tree.columns.count('wm_online') == 1


def test_decision_queue_calculates_month_once(monkeypatch):
    import profile_attendance_finalize_runtime as overview

    records = Mock(return_value=[{
        'date': '2026-09-10', 'slot': attendance.RANO,
        'status': attendance.STATUS_MISSING,
    }])
    monkeypatch.setattr(attendance, 'month_records', records)
    monkeypatch.setattr(overview.workforce_profile_service, 'list_users',
                        lambda **kw: [{'login': 'marek'}])
    monkeypatch.setattr(overview.workforce_profile_service, 'display_name',
                        lambda user: 'Marek')
    monkeypatch.setattr(overview, '_absence_labels', lambda *args: [])
    result = overview._all_decisions(2026, 9)
    records.assert_called_once_with('marek', 2026, 9)
    assert len(result) == 1
    assert result[0]['decision_label'] == 'Brak logowania'
