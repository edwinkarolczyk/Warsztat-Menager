# version: 1.0
from __future__ import annotations

import dyspozycje_access as access


class DummyConfig:
    data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save_all(self):
        return None


def test_default_actions_for_brygadzista(monkeypatch):
    DummyConfig.data = {}
    monkeypatch.setattr(access, "ConfigManager", DummyConfig)
    monkeypatch.setattr(access, "is_module_allowed_for_role", lambda role, module: True)

    assert access.is_role_action_allowed("brygadzista", access.ACTION_ADD) is True
    assert access.is_role_action_allowed("brygadzista", access.ACTION_EDIT) is True
    assert access.is_role_action_allowed("operator", access.ACTION_ADD) is False
    assert access.is_role_action_allowed("operator", access.ACTION_EDIT) is False


def test_saved_role_actions_override_defaults(monkeypatch):
    DummyConfig.data = {}
    monkeypatch.setattr(access, "ConfigManager", DummyConfig)
    monkeypatch.setattr(access, "is_module_allowed_for_role", lambda role, module: True)

    access.set_role_actions(
        "brygadzista",
        {access.ACTION_ADD: False, access.ACTION_EDIT: True},
    )

    assert access.get_role_actions("brygadzista") == {
        access.ACTION_ADD: False,
        access.ACTION_EDIT: True,
    }


def test_actions_require_dyspozycje_module_access(monkeypatch):
    DummyConfig.data = {}
    monkeypatch.setattr(access, "ConfigManager", DummyConfig)
    monkeypatch.setattr(access, "is_module_allowed_for_role", lambda role, module: False)

    assert access.is_role_action_allowed("brygadzista", access.ACTION_ADD) is False
    assert access.is_role_action_allowed("brygadzista", access.ACTION_EDIT) is False
