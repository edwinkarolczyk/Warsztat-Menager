import importlib


def test_foreman_role_case_insensitive():
    mod = importlib.import_module('gui_profile')
    order = {'nr': 1}
    tool = {'id': 'NARZ-1-1'}
    roles = ['brygadzista', 'BRYGADZISTA', 'Brygadzista', 'BrYgAdZiStA']
    for r in roles:
        assert mod._order_visible_for(order, 'user', r)
        assert mod._tool_visible_for(tool, 'user', r)
