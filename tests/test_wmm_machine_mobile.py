from __future__ import annotations

import copy

import pytest

from services import wmm_machine_mobile as mobile


class FakeImpl:
    def __init__(self, machine):
        self.machine = copy.deepcopy(machine)

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


def test_mobile_module_does_not_create_planned_reviews():
    assert not hasattr(mobile, "add_planned_review")
    assert not hasattr(mobile, "REVIEW_TYPES")
