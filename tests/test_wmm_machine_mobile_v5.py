from __future__ import annotations

import copy

from services import wmm_machine_mobile_v5 as mobile


def test_manual_review_is_visible_even_when_gui_combiner_omits_it(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    machine = {
        "id": "42",
        "reviews": [
            {
                "id": "rev_manual_1",
                "planned_date": "2026-09-18",
                "type": "Serwis planowany",
                "status": "planned",
                "source": "manual",
            }
        ],
    }
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: [
            {
                "id": "cycle_2026_10",
                "date": "2026-10-01",
                "type": "Przegląd okresowy",
                "status": "planned",
                "source": "cycle",
            }
        ],
    )

    rows = mobile.combined_actionable_reviews(copy.deepcopy(machine))

    assert [row["id"] for row in rows] == ["rev_manual_1", "cycle_2026_10"]
    assert rows[0]["date"] == "2026-09-18"
    assert rows[0]["source_label"] == "Ręczny / zaplanowany w WM"
    assert rows[1]["source_label"] == "Cykliczny"


def test_duplicate_review_from_gui_is_not_returned_twice(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    manual = {
        "id": "rev_manual_1",
        "planned_date": "2026-09-18",
        "type": "Serwis planowany",
        "status": "planned",
        "source": "manual",
    }
    machine = {"id": "42", "reviews": [copy.deepcopy(manual)]}
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: [copy.deepcopy(manual)],
    )

    rows = mobile.combined_actionable_reviews(machine)

    assert [row["id"] for row in rows] == ["rev_manual_1"]


def test_done_and_cancelled_reviews_stay_hidden(monkeypatch):
    import gui_maszyny_legacy as machines_gui

    machine = {
        "id": "42",
        "reviews": [
            {"id": "done", "planned_date": "2026-09-01", "status": "done"},
            {"id": "cancelled", "planned_date": "2026-09-02", "status": "cancelled"},
            {"id": "planned", "planned_date": "2026-09-03", "status": "planned"},
        ],
    }
    monkeypatch.setattr(
        machines_gui,
        "_combined_machine_review_entries",
        lambda machine, today, years_ahead: [],
    )

    rows = mobile.combined_actionable_reviews(machine)

    assert [row["id"] for row in rows] == ["planned"]
