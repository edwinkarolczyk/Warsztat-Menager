# version: 1.1
from types import SimpleNamespace

import gui_profile
import settings_users_runtime as settings_runtime
from profile_settings_fields import normalize_editable_fields


def test_requested_profile_settings_tab_is_opened_and_consumed():
    root = SimpleNamespace(_wm_settings_target_tab="Profile")
    opened = []

    class Panel:
        def winfo_toplevel(self):
            return root

        def open_tab(self, title):
            opened.append(title)
            return True

    panel = Panel()
    settings_runtime._open_requested_profile_tab(panel)

    assert opened == ["Profile"]
    assert not hasattr(root, "_wm_settings_target_tab")


def test_foreman_has_separate_profile_settings_shortcut(monkeypatch):
    root = SimpleNamespace()
    container = object()
    calls = {}

    class FakeProfile:
        login = "edwin"
        master = container

        def _logged_user_is_brygadzista(self):
            return True

        def winfo_toplevel(self):
            return root

    monkeypatch.setattr(
        gui_profile.ProfileService,
        "ensure_active_user_or_none",
        lambda: "edwin",
    )
    monkeypatch.setattr(
        gui_profile,
        "get_user",
        lambda login: {"login": login, "rola": "brygadzista"},
    )

    import ustawienia_systemu

    def fake_panel_ustawien(root_arg, frame_arg, login=None, rola=None, **_kwargs):
        calls["root"] = root_arg
        calls["frame"] = frame_arg
        calls["login"] = login
        calls["rola"] = rola
        calls["target"] = getattr(root_arg, "_wm_settings_target_tab", "")
        return frame_arg

    monkeypatch.setattr(ustawienia_systemu, "panel_ustawien", fake_panel_ustawien)

    gui_profile.ProfileView._open_profile_settings(FakeProfile())

    assert calls["root"] is root
    assert calls["frame"] is container
    assert calls["login"] == "edwin"
    assert calls["rola"] == "brygadzista"
    assert calls["target"] == "Profile"


def test_editable_fields_normalize_legacy_and_garbage():
    assert normalize_editable_fields(
        ["imie", "staz", "telefon", "im", "EMAIL", "telefon"]
    ) == ["imie", "zatrudniony_od", "telefon", "email"]
    assert normalize_editable_fields("imie, nazwisko; staz\nim") == [
        "imie",
        "nazwisko",
        "zatrudniony_od",
    ]


def test_profile_respects_explicit_empty_editable_fields(monkeypatch):
    class FakeConfig:
        def get(self, key, default=None):
            values = {
                "profiles.editable_fields": [],
                "profiles.pin.change_allowed": False,
                "profiles.pin": {"min_length": 4},
            }
            return values.get(key, default)

    monkeypatch.setattr(gui_profile, "ConfigManager", lambda: FakeConfig())
    fields, allow_pin, pin_min = gui_profile.ProfileView._user_editable_fields(object())

    assert fields == []
    assert allow_pin is False
    assert pin_min == 4


def test_profile_maps_staz_to_real_employment_date_field(monkeypatch):
    class FakeConfig:
        def get(self, key, default=None):
            values = {
                "profiles.editable_fields": ["imie", "staz", "telefon", "im"],
                "profiles.pin.change_allowed": True,
                "profiles.pin": {"min_length": 5},
            }
            return values.get(key, default)

    monkeypatch.setattr(gui_profile, "ConfigManager", lambda: FakeConfig())
    fields, allow_pin, pin_min = gui_profile.ProfileView._user_editable_fields(object())

    assert fields == ["imie", "zatrudniony_od", "telefon"]
    assert allow_pin is True
    assert pin_min == 5
