from __version__ import __version__
from profile_employee_editor_finish_runtime import (
    _employee_key,
    _human_action,
    _refresh_open_profile_views,
)
from profile_foreman_edit_runtime import _parse_carryover


def test_profile_release_is_current():
    assert __version__ == "0.10.0"


def test_carryover_keeps_source_years():
    assert _parse_carryover("2024=2; 2025=4", 2026) == {2024: 2.0, 2025: 4.0}


def test_carryover_rejects_current_year():
    try:
        _parse_carryover("2026=1", 2026)
    except ValueError:
        return
    raise AssertionError("Bieżący rok nie może być zapisany jako urlop zaległy")


def test_employee_window_key_uses_stable_user_id(monkeypatch):
    class Owner:
        def winfo_toplevel(self):
            return self

    owner = Owner()
    monkeypatch.setattr(
        "profile_employee_editor_finish_runtime.workforce_profile_service.get_user",
        lambda _login: {"user_id": "USR-0042"},
    )

    assert _employee_key(owner, "jan") == _employee_key(owner, "jan.po.zmianie")


def test_history_humanizes_shift_move():
    title, detail = _human_action(
        {
            "action": "manual_day_move",
            "before": {"slot": "RANO", "day_value": 1.0},
            "after": {"slot": "POPO", "day_value": 1.0},
            "note": "Zmiana RANO → POPO.",
        }
    )

    assert title == "Zmiana zmiany"
    assert "zmiana: RANO → POPO" in detail


def test_refresh_notifies_profile_and_foreman_panel():
    calls = []

    ForemanProfilePanel = type("ForemanProfilePanel", (), {})
    panel = ForemanProfilePanel()
    panel.winfo_children = lambda: []
    panel.refresh_data = lambda: calls.append("foreman")
    panel.after_idle = lambda callback: callback()

    ProfileView = type("ProfileView", (), {})
    profile = ProfileView()
    profile.winfo_children = lambda: []
    profile._refresh_view = lambda: calls.append("profile")
    profile.after_idle = lambda callback: callback()

    class Owner:
        def __init__(self):
            self.events = []

        def winfo_toplevel(self):
            return self

        def winfo_children(self):
            return [panel, profile]

        def event_generate(self, name, when=None):
            self.events.append((name, when))

    owner = Owner()
    _refresh_open_profile_views(owner)

    assert ("<<ProfileDataUpdated>>", "tail") in owner.events
    assert calls == ["foreman", "profile"]
