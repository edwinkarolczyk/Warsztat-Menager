from __future__ import annotations

import json

import presence
import wm_operational_followup_runtime as followup
from services import feedback_service, workforce_profile_service


def test_pending_leave_message_contains_count_employee_and_target(monkeypatch):
    monkeypatch.setattr(
        workforce_profile_service,
        "get_user",
        lambda login: {"login": login, "imie": "Marek", "nazwisko": "Kowalski"},
    )
    monkeypatch.setattr(
        workforce_profile_service,
        "display_name",
        lambda user: f"{user.get('imie')} {user.get('nazwisko')}",
    )

    text = followup._format_pending_leave_message([
        {
            "login": "marek",
            "date_start": "2026-09-10",
            "date_end": "2026-09-12",
        }
    ])

    assert "WNIOSKI URLOPOWE DO AKCEPTACJI: 1" in text
    assert "Marek Kowalski" in text
    assert "2026-09-10–2026-09-12" in text
    assert "Profil → Brygadzista → Urlopy" in text


def test_feedback_canonicalization_persists_id_and_user_id(tmp_path, monkeypatch):
    path = tmp_path / "opinie.json"
    path.write_text(
        json.dumps([
            {
                "login": "Edwin",
                "rola": "brygadzista",
                "ts": "2026-09-07T12:00:00",
                "message": "Test opinii",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(feedback_service, "feedback_path", lambda: path)
    monkeypatch.setattr(
        feedback_service,
        "get_user",
        lambda _login: {"user_id": "USR-0001", "rola": "brygadzista"},
    )

    assert followup._canonicalize_feedback_storage() is True

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored[0]["id"].startswith("OPN-")
    assert stored[0]["user_id"] == "USR-0001"
    assert stored[0]["login_snapshot"] == "Edwin"
    assert stored[0]["status"] == "nowa"
    assert stored[0]["created_at"] == "2026-09-07T12:00:00"
    assert stored[0]["message"] == "Test opinii"

    assert followup._canonicalize_feedback_storage() is False


def test_background_presence_session_stops_on_logout(monkeypatch):
    writes = []
    presence._stop_background_session(mark_logout=False)
    monkeypatch.setattr(
        presence,
        "_heartbeat_write",
        lambda login, role=None, machine=None, logout=False: writes.append(
            (login, role, bool(logout))
        ) or True,
    )

    presence.start_session("jan", "operator", interval_sec=999)
    stop_event = presence._session_stop

    assert stop_event is not None
    assert writes[0] == ("jan", "operator", False)
    assert stop_event.is_set() is False

    presence.heartbeat("jan", "operator", logout=True)

    assert stop_event.is_set() is True
    assert writes[-1] == ("jan", "operator", True)
    presence._stop_background_session(mark_logout=False)


def test_lazy_foreman_helper_renders_only_selected_tab():
    class Notebook:
        def select(self):
            return "tab-id"

        def tab(self, _tab_id, option):
            assert option == "text"
            return "Opinie"

    class Panel:
        notebook = Notebook()

        def __init__(self):
            self.calls = []

        def _render_dashboard(self):
            self.calls.append("Pulpit")

        def _render_feedback(self):
            self.calls.append("Opinie")

    panel = Panel()
    followup._render_selected_foreman_tab(panel)

    assert panel.calls == ["Opinie"]
