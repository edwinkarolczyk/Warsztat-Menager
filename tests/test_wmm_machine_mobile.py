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

    @staticmethod
    def _append_history(row, action, author, note=""):
        row.setdefault("historia", []).append(
            {"kiedy": "2026-09-15T07:00:00", "kto": author, "co": action, "uwaga": note}
        )


def test_quick_repair_uses_existing_machine_status_history(monkeypatch):
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
        }
    )

    started = mobile.start_quick_repair(impl, "42", "edwin", "Nie działa czujnik")
    assert started["status"] == "warn"
    assert started["status_current"]["label"] == "Awaria"
    assert started["status_current"]["started_at"] == "2026-09-15T07:00:00"
    assert started["status_current"]["changed_by"] == "edwin"
    assert started["status_current"]["note"].startswith("[WMM]")

    finished, duration = mobile.finish_quick_repair(impl, "42", "edwin", "Czujnik wymieniony")
    assert finished["status"] == "ok"
    assert finished["status_current"]["label"] == "Sprawna"
    assert duration == 35

    repair = finished["status_history"][-1]
    assert repair["status"] == "warn"
    assert repair["started_at"] == "2026-09-15T07:00:00"
    assert repair["ended_at"] == "2026-09-15T07:35:00"
    assert repair["duration_minutes"] == 35
    assert repair["closed_by"] == "edwin"
    assert repair["close_note"].startswith("[WMM]")


def test_quick_repair_does_not_duplicate_existing_failure(monkeypatch):
    monkeypatch.setattr(mobile, "_now_iso", lambda: "2026-09-15T07:00:00")
    impl = FakeImpl({"id": "42", "status": "warn"})

    with pytest.raises(RuntimeError, match="już status Awaria"):
        mobile.start_quick_repair(impl, "42", "edwin")


def test_planned_review_uses_only_existing_wm_schema():
    impl = FakeImpl({"id": "42", "status": "ok", "reviews": []})

    updated, review = mobile.add_planned_review(
        impl,
        "42",
        "edwin",
        review_type="Konserwacja",
        planned_date="2026-10-20",
        description="Smarowanie prowadnic",
    )

    assert review["id"].startswith("rev_")
    assert review["type"] == "Konserwacja"
    assert review["planned_date"] == "2026-10-20"
    assert review["status"] == "planned"
    assert review["source"] == "manual"
    assert review["description"].startswith("[WMM]")
    assert review["completed_at"] == ""
    assert review["completed_by"] == []
    assert review["result_note"] == ""
    assert review["photos"] == []
    assert updated["reviews"][-1] == review


def test_planned_review_rejects_new_types():
    impl = FakeImpl({"id": "42", "status": "ok", "reviews": []})

    with pytest.raises(RuntimeError, match="typ przeglądu"):
        mobile.add_planned_review(
            impl,
            "42",
            "edwin",
            review_type="Szybki serwis WMM",
            planned_date="2026-10-20",
        )


def test_review_types_are_exactly_the_existing_wm_list():
    assert mobile.REVIEW_TYPES == (
        "Przegląd okresowy",
        "Serwis planowany",
        "Konserwacja",
        "Kalibracja",
        "Czyszczenie",
        "Inne",
    )
