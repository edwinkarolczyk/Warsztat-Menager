from __future__ import annotations

import copy

import pytest

from services import wmm_machine_mobile_v4 as mobile


class FakeImpl:
    def __init__(self, machine):
        self.machine = copy.deepcopy(machine)

    def _find_machine(self, machine_id):
        assert machine_id == "42"
        return copy.deepcopy(self.machine)

    def _update_machine(self, machine_id, mutator):
        assert machine_id == "42"
        mutator(self.machine)
        return copy.deepcopy(self.machine)


class FakeHandler:
    def __init__(self, session_id="session-1"):
        self.headers = {"X-WMM-Session": session_id}


class FakeSessionImpl:
    def __init__(self, user):
        self.user = user

    def _touch_session(self, session_id):
        return copy.deepcopy(self.user) if session_id == "session-1" else None


def test_active_author_requires_real_wmm_session():
    assert mobile._active_author(
        FakeHandler(), FakeSessionImpl({"login": "edwin", "name": "Edwin"})
    ) == "edwin"

    with pytest.raises(PermissionError, match="Sesja użytkownika WMM wygasła"):
        mobile._active_author(FakeHandler("stara-sesja"), FakeSessionImpl({"login": "edwin"}))


def test_wmm_note_contains_source_and_login():
    note = mobile._wmm_note("edwin", "Szybka naprawa", "czujnik")
    assert note.startswith("[WMM] edwin — Szybka naprawa")
    assert "czujnik" in note


def test_planned_list_contains_manual_and_cycle(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    rows = [
        {
            "id": "rev_manual_1",
            "date": "2026-09-18",
            "planned_date": "2026-09-18",
            "type": "Serwis planowany",
            "status": "planned",
            "source": "manual",
        },
        {
            "id": "cycle_2026_10",
            "date": "2026-10-01",
            "type": "Przegląd okresowy",
            "status": "planned",
            "source": "cycle",
        },
        {
            "id": "rev_done",
            "date": "2026-08-01",
            "type": "Przegląd okresowy",
            "status": "done",
            "source": "manual",
        },
    ]
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: copy.deepcopy(rows),
    )

    listed = mobile._combined_actionable_reviews({"id": "42"})
    assert [item["id"] for item in listed] == ["rev_manual_1", "cycle_2026_10"]
    assert listed[0]["source_label"] == "Ręczny / zaplanowany w WM"
    assert listed[1]["source_label"] == "Cykliczny"


def test_manual_planned_review_is_used_without_creating_second_entry(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    manual = {
        "id": "rev_manual_1",
        "planned_date": "2026-09-18",
        "type": "Serwis planowany",
        "status": "planned",
        "source": "manual",
        "completed_by": [],
    }
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: [copy.deepcopy(manual)],
    )
    monkeypatch.setattr(mobile.legacy, "_sync_review_to_disposition", lambda *args, **kwargs: None)

    def fake_status(machine, new_status, *, actor, note):
        machine["status"] = new_status
        machine["status_current"] = {
            "status": new_status,
            "changed_by": actor,
            "note": note,
        }

    monkeypatch.setattr(mobile.legacy, "_apply_wm_machine_status", fake_status)
    monkeypatch.setattr(mobile, "_now_iso", lambda: "2026-09-15T10:00:00")

    impl = FakeImpl({"id": "42", "status": "ok", "reviews": [copy.deepcopy(manual)]})
    started, review = mobile._start_planned_review(
        impl, "42", "rev_manual_1", "edwin"
    )

    assert len(started["reviews"]) == 1
    assert review["id"] == "rev_manual_1"
    assert review["status"] == "in_progress"
    assert review["started_by"] == "edwin"
    assert started["status_current"]["changed_by"] == "edwin"
    assert "[WMM] edwin" in started["status_current"]["note"]


def test_manual_planned_review_can_be_completed_with_login(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    manual = {
        "id": "rev_manual_1",
        "planned_date": "2026-09-18",
        "type": "Serwis planowany",
        "status": "in_progress",
        "source": "manual",
        "started_at": "2026-09-15T09:30:00",
        "started_by": "edwin",
    }
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: [copy.deepcopy(manual)],
    )
    monkeypatch.setattr(mobile.legacy, "_sync_review_to_disposition", lambda *args, **kwargs: None)

    def fake_status(machine, new_status, *, actor, note):
        machine["status"] = new_status
        machine["status_current"] = {
            "status": new_status,
            "changed_by": actor,
            "note": note,
        }

    monkeypatch.setattr(mobile.legacy, "_apply_wm_machine_status", fake_status)
    monkeypatch.setattr(mobile, "_now_iso", lambda: "2026-09-15T10:10:00")

    impl = FakeImpl({"id": "42", "status": "alert", "reviews": [copy.deepcopy(manual)]})
    completed, review = mobile._complete_planned_review(
        impl,
        "42",
        "rev_manual_1",
        "edwin",
        "Smarowanie i kontrola",
    )

    assert len(completed["reviews"]) == 1
    assert review["status"] == "done"
    assert review["completed_by"] == ["edwin"]
    assert review["result_note"].startswith("[WMM] edwin")
    assert completed["status_current"]["changed_by"] == "edwin"


def test_completing_one_review_keeps_alert_for_another_active_review(monkeypatch):
    first = {
        "id": "rev_manual_1",
        "status": "in_progress",
        "source": "manual",
    }
    second = {
        "id": "rev_manual_2",
        "status": "in_progress",
        "source": "manual",
    }
    monkeypatch.setattr(
        mobile,
        "_find_display_entry",
        lambda machine, review_id: next(
            item for item in machine["reviews"] if item["id"] == review_id
        ),
    )
    monkeypatch.setattr(
        mobile.legacy,
        "_sync_review_to_disposition",
        lambda *args, **kwargs: None,
    )
    status_changes = []
    monkeypatch.setattr(
        mobile.legacy,
        "_apply_wm_machine_status",
        lambda machine, new_status, **kwargs: status_changes.append(new_status),
    )

    impl = FakeImpl(
        {
            "id": "42",
            "status": "alert",
            "reviews": [copy.deepcopy(first), copy.deepcopy(second)],
        }
    )
    completed, review = mobile._complete_planned_review(
        impl, "42", "rev_manual_1", "edwin"
    )

    assert review["status"] == "done"
    assert completed["reviews"][1]["status"] == "in_progress"
    assert completed["status"] == "alert"
    assert status_changes == []
