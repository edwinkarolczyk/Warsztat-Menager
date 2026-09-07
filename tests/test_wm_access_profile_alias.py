import copy

import wm_access


class _FakeConfig:
    def __init__(self, role_modules):
        self.role_modules = role_modules
        self.set_calls = 0
        self.save_all_calls = 0

    def get(self, key, default=None):
        if key == "access.role_modules":
            return self.role_modules
        return default

    def set(self, key, value, who="system"):
        assert key == "access.role_modules"
        self.role_modules = value
        self.set_calls += 1

    def save_all(self):
        self.save_all_calls += 1


def _normalized_defaults():
    return {
        role: wm_access._normalize_modules_map(modules)
        for role, modules in wm_access._all_default_role_modules().items()
    }


def test_profile_aliases_normalize_to_canonical_profile():
    assert wm_access.normalize_module_name("profil") == "profile"
    assert wm_access.normalize_module_name("profile") == "profile"


def test_repeated_profile_access_does_not_rewrite_complete_role_config(monkeypatch):
    expected = _normalized_defaults()
    cfg = _FakeConfig(copy.deepcopy(expected))

    monkeypatch.setattr(wm_access, "ConfigManager", lambda: cfg)
    monkeypatch.setattr(wm_access, "get_disabled_modules_for", lambda _login: [])

    for _ in range(100):
        assert wm_access.is_module_allowed_for_user(
            "Edwin", "brygadzista", "profil"
        )
        assert wm_access.is_module_allowed_for_user(
            "Edwin", "brygadzista", "profile"
        )

    assert cfg.role_modules == expected
    assert cfg.set_calls == 0
    assert cfg.save_all_calls == 0


def test_legacy_profil_keys_are_migrated_only_once(monkeypatch):
    cfg = _FakeConfig(copy.deepcopy(wm_access._all_default_role_modules()))
    monkeypatch.setattr(wm_access, "ConfigManager", lambda: cfg)

    wm_access.ensure_default_role_modules_config()
    assert cfg.role_modules == _normalized_defaults()
    assert cfg.set_calls == 1
    assert cfg.save_all_calls == 1

    wm_access.ensure_default_role_modules_config()
    assert cfg.set_calls == 1
    assert cfg.save_all_calls == 1
