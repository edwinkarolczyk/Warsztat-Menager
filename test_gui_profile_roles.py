import importlib
import json


def test_foreman_role_case_insensitive():
    mod = importlib.import_module('gui_profile')
    order = {'nr': 1}
    tool = {'id': 'NARZ-1-1'}
    roles = ['brygadzista', 'BRYGADZISTA', 'Brygadzista', 'BrYgAdZiStA']
    for r in roles:
        assert mod._order_visible_for(order, 'user', r)
        assert mod._tool_visible_for(tool, 'user', r)


def test_read_tasks_foreman_role_case_insensitive(monkeypatch):
    mod = importlib.import_module('gui_profile')

    sample_order = {'nr': 1, 'login': 'other', 'status': 'Nowe'}

    def fake_load_json(path, default):
        if str(path).endswith('zlecenia.json'):
            return [sample_order]
        return []

    monkeypatch.setattr(mod, '_load_json', fake_load_json)
    monkeypatch.setattr(mod, '_load_status_overrides', lambda login: {})
    monkeypatch.setattr(mod, '_load_assign_orders', lambda: {})
    monkeypatch.setattr(mod, '_load_assign_tools', lambda: {})
    monkeypatch.setattr(mod.glob, 'glob', lambda pattern: [])

    roles = ['brygadzista', 'BRYGADZISTA', 'Brygadzista', 'BrYgAdZiStA']
    for r in roles:
        tasks = mod._read_tasks('user', r)
        assert any(t.get('id') == 'ZLEC-1' for t in tasks)
