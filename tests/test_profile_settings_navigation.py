# version: 1.0
from types import SimpleNamespace

import gui_profile
import settings_users_runtime as settings_runtime


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


def test_foreman_edit_profile_redirects_to_profile_settings(monkeypatch):
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

    gui_profile.ProfileView._open_edit_profile(FakeProfile())

    assert calls["root"] is root
    assert calls["frame"] is container
    assert calls["login"] == "edwin"
    assert calls["rola"] == "brygadzista"
    assert calls["target"] == "Profile"
