from __future__ import annotations

import copy

import pytest

from services import wmm_machine_mobile as mobile


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


def test_quick_repair_creates_one_failure_period(monkeypatch):
    times = iter(("2026-09-15T07:00:00", "2026-09-15T07:35:00"))
    monkeypatch.setattr(mobile, "_now_iso", lambda: next(times))
    impl = FakeImpl(
        {
            "id": "42",
            "status": "ok",
            "status_current": {
                "status": "ok",
                "label": "Sprawna",
                "started_at": "2026-09-15T06:00:00",
                "changed_by": "marek",
                "note": "",
                "photos": [],
            },
            "status_history": [],
        }
    )

    started = mobile.start_quick_repair(impl, "42", "edwin", "Nie działa czujnik")
    assert started["status"] == "warn"
    assert started["status_current"]["label"] == "Awaria"
    assert started["status_current"]["started_at"] == "2026-09-15T07:00:00"
    assert started["status_current"]["changed_by"] == "edwin"
    assert started["status_current"]["note"].startswith("[WMM]")
    assert started["status_history"] == []

    finished, duration = mobile.finish_quick_repair(impl, "42", "edwin", "Czujnik wymieniony")
    assert finished["status"] == "ok"
    assert finished["status_current"]["label"] == "Sprawna"
    assert duration == 35
    assert len(finished["status_history"]) == 1

    repair = finished["status_history"][0]
    assert repair["status"] == "warn"
    assert repair["started_at"] == "2026-09-15T07:00:00"
    assert repair["ended_at"] == "2026-09-15T07:35:00"
    assert repair["duration_minutes"] == 35
    assert repair["closed_by"] == "edwin"
    assert repair["close_note"].startswith("[WMM]")


def test_quick_repair_overwrites_stale_status_current(monkeypatch):
    monkeypatch.setattr(mobile, "_now_iso", lambda: "2026-09-15T07:00:00")
    impl = FakeImpl(
        {
            "id": "42",
            "status": "ok",
            "status_current": {
                "status": "warn",
                "label": "Awaria",
                "started_at": "2026-09-15T06:00:00",
                "changed_by": "stary-wpis",
                "note": "stary",
            },
            "status_history": [],
        }
    )

    started = mobile.start_quick_repair(impl, "42", "edwin", "Nowa naprawa")
    assert started["status"] == "warn"
    assert started["status_current"]["status"] == "warn"
    assert started["status_current"]["started_at"] == "2026-09-15T07:00:00"
    assert started["status_current"]["changed_by"] == "edwin"
    assert started["status_history"] == []


def test_quick_repair_does_not_duplicate_existing_failure(monkeypatch):
    monkeypatch.setattr(mobile, "_now_iso", lambda: "2026-09-15T07:00:00")
    impl = FakeImpl({"id": "42", "status": "warn"})

    with pytest.raises(RuntimeError, match="już status Awaria"):
        mobile.start_quick_repair(impl, "42", "edwin")


def _fake_cycle_entries(machine):
    persisted = [
        dict(item)
        for item in machine.get("reviews", [])
        if isinstance(item, dict) and item.get("source") == "cycle" and item.get("status") != "done"
    ]
    if persisted:
        return persisted
    return [
        {
            "id": "cycle_2026_09",
            "date": "2026-09-20",
            "type": "Przegląd okresowy",
            "status": "planned",
            "source": "cycle",
            "suggested_people": ["edwin"],
            "display_type": "Przegląd cykliczny",
        }
    ]


def _fake_apply_status(machine, new_status, *, actor, note):
    machine["status"] = new_status
    machine["status_current"] = {
        "status": new_status,
        "started_at": "2026-09-15T08:00:00",
        "changed_by": actor,
        "note": note,
    }


def test_cycle_review_uses_existing_wm_schedule_and_materializes_on_action(monkeypatch):
    times = iter(("2026-09-15T08:00:00", "2026-09-15T08:25:00"))
    monkeypatch.setattr(mobile, "_now_iso", lambda: next(times))
    monkeypatch.setattr(mobile, "_wm_combined_cycle_entries", _fake_cycle_entries)
    monkeypatch.setattr(mobile, "_apply_wm_machine_status", _fake_apply_status)
    monkeypatch.setattr(mobile, "_sync_review_to_disposition", lambda *args, **kwargs: None)

    impl = FakeImpl({"id": "42", "status": "ok", "reviews": []})

    planned = mobile.cycle_reviews(impl, "42")
    assert [item["id"] for item in planned] == ["cycle_2026_09"]
    assert impl.machine["reviews"] == []

    started, review = mobile.start_cycle_review(
        impl,
        "42",
        "cycle_2026_09",
        "edwin",
    )
    assert len(started["reviews"]) == 1
    assert review["id"].startswith("rev_")
    assert review["source"] == "cycle"
    assert review["cycle_year"] == 2026
    assert review["cycle_month"] == 9
    assert review["planned_date"] == "2026-09-20"
    assert review["status"] == "in_progress"
    assert review["started_by"] == "edwin"
    assert started["status"] == "alert"

    current_id = review["id"]
    completed, done = mobile.complete_cycle_review(
        impl,
        "42",
        current_id,
        "edwin",
        "Smarowanie i kontrola osłon",
    )
    assert len(completed["reviews"]) == 1
    assert done["id"] == current_id
    assert done["status"] == "done"
    assert done["completed_by"] == ["edwin"]
    assert done["completed_at"] == "2026-09-15T08:25:00"
    assert done["result_note"].startswith("[WMM]")
    assert completed["status"] == "ok"


def test_cycle_review_rejects_id_not_present_in_wm_schedule(monkeypatch):
    monkeypatch.setattr(mobile, "_wm_combined_cycle_entries", _fake_cycle_entries)
    impl = FakeImpl({"id": "42", "status": "ok", "reviews": []})

    with pytest.raises(RuntimeError, match="nie jest już aktywny"):
        mobile.start_cycle_review(impl, "42", "cycle_2099_12", "edwin")
    assert impl.machine["reviews"] == []


def test_mobile_module_does_not_create_planned_reviews():
    assert not hasattr(mobile, "add_planned_review")
    assert not hasattr(mobile, "REVIEW_TYPES")
