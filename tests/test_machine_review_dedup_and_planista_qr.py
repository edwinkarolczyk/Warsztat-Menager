from __future__ import annotations

import re

import gui_maszyny_legacy as GM
import gui_planista as GP


def test_machine_review_duplicates_merge_done_over_planned_and_preserve_people():
    machine = {
        "id": "19",
        "reviews": [
            {
                "id": "rev_20260831_071938",
                "type": "Konserwacja",
                "planned_date": "2026-08-31",
                "status": "done",
                "suggested_workers": ["dawid", "edwin"],
                "completed_at": "2026-09-28T13:12:32",
                "completed_by": ["Edwin"],
                "description": "Zlokalizować wyciek i go usunąć",
            },
            {
                "id": "rev_20260831_071938",
                "type": "Konserwacja",
                "planned_date": "2026-08-31",
                "status": "planned",
                "suggested_workers": ["dawid", "edwin"],
                "completed_at": "",
                "completed_by": [],
                "description": "Zlokalizować wyciek i go usunąć",
            },
        ],
    }

    rows = GM._machine_reviews(machine)

    assert len(rows) == 1
    assert len(machine["reviews"]) == 1
    assert rows[0]["status"] == "done"
    assert rows[0]["completed_at"] == "2026-09-28T13:12:32"
    assert rows[0]["completed_by"] == ["Edwin"]


def test_machine_review_duplicate_when_done_is_second_promotes_progress():
    machine = {
        "id": "19",
        "reviews": [
            {
                "id": "rev_same",
                "type": "Konserwacja",
                "planned_date": "2026-08-31",
                "status": "planned",
                "description": "Wyciek",
                "completed_by": [],
            },
            {
                "id": "rev_same",
                "type": "Konserwacja",
                "planned_date": "2026-08-31",
                "status": "done",
                "description": "Wyciek",
                "completed_at": "2026-09-28T11:01:47",
                "completed_by": ["Edwin"],
            },
        ],
    }

    rows = GM._machine_reviews(machine)

    assert len(rows) == 1
    assert rows[0]["status"] == "done"
    assert rows[0]["completed_at"] == "2026-09-28T11:01:47"
    assert rows[0]["completed_by"] == ["Edwin"]


def test_row_repair_counts_removed_duplicate_copies():
    rows = [
        {
            "id": "19",
            "reviews": [
                {"id": "dup", "planned_date": "2026-08-31", "status": "done"},
                {"id": "dup", "planned_date": "2026-08-31", "status": "planned"},
                {"id": "dup", "planned_date": "2026-08-31", "status": "planned"},
            ],
        }
    ]

    removed = GM._repair_duplicate_reviews_in_rows(rows)

    assert removed == 2
    assert len(rows[0]["reviews"]) == 1
    assert rows[0]["reviews"][0]["status"] == "done"


def test_new_machine_review_ids_do_not_collide_in_fast_sequence():
    first = GM._new_review_id()
    second = GM._new_review_id()
    assert first != second
    assert re.fullmatch(r"rev_\d{8}_\d{6}_\d{6}", first)


def test_planista_work_order_contains_wmm_qr_payload_and_embedded_image():
    order = {
        "id": "000012",
        "zlec_wew": "742",
        "produkt": "1.300.300",
        "ilosc": 80,
        "wykonano": 0,
        "termin": "2026-09-22",
        "plan_polprodukty": {},
    }

    assert GP._work_order_qr_payload(order) == "WM:PLANISTA:ORDER:000012"
    html = GP._work_order_html(order)
    assert "WM:PLANISTA:ORDER:000012" in html
    assert "data:image/png;base64," in html
    assert "Skanuj QR w WMM" in html
