import gui_maszyny


def test_apply_machine_status_change_closes_current_period(monkeypatch):
    monkeypatch.setattr(gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T10:30:00")
    machine = {
        "status": "ok",
        "status_current": {
            "status": "ok",
            "label": "Sprawna",
            "started_at": "2026-05-30T09:00:00",
            "changed_by": "anna",
            "note": "",
            "photos": [],
        },
    }

    changed = gui_maszyny._apply_machine_status_change(
        machine, "warn", actor="jan", note="Pęknięty pasek"
    )

    assert changed is True
    assert machine["status"] == "warn"
    assert machine["status_current"] == {
        "status": "warn",
        "label": "Awaria",
        "started_at": "2026-05-30T10:30:00",
        "changed_by": "jan",
        "note": "Pęknięty pasek",
        "photos": [],
    }
    assert machine["status_history"] == [
        {
            "status": "ok",
            "label": "Sprawna",
            "started_at": "2026-05-30T09:00:00",
            "changed_by": "anna",
            "note": "",
            "photos": [],
            "ended_at": "2026-05-30T10:30:00",
            "duration_minutes": 90,
            "closed_by": "jan",
            "close_note": "Pęknięty pasek",
        }
    ]


def test_apply_machine_status_change_initializes_current_when_unchanged(monkeypatch):
    monkeypatch.setattr(gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T11:00:00")
    machine = {"status": "sprawna"}

    changed = gui_maszyny._apply_machine_status_change(
        machine, "ok", actor="anna", note=""
    )

    assert changed is False
    assert machine["status"] == "ok"
    assert machine["status_current"]["started_at"] == "2026-05-30T11:00:00"
    assert machine["status_current"]["changed_by"] == "anna"


def test_machine_status_history_rows_include_closed_and_current(monkeypatch):
    monkeypatch.setattr(gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T12:00:00")
    machine = {
        "status_history": [
            {
                "status": "alert",
                "started_at": "2026-05-28T08:00:00",
                "ended_at": "2026-05-30T08:00:00",
                "duration_minutes": 2880,
                "closed_by": "anna",
                "close_note": "Przegląd wykonany",
            }
        ],
        "status_current": {
            "status": "ok",
            "started_at": "2026-05-30T08:00:00",
            "changed_by": "anna",
            "note": "Gotowa do pracy",
        },
    }

    rows = gui_maszyny._machine_status_history_rows(machine)

    assert rows == [
        (
            "Serwis / przegląd",
            "2026-05-28 08:00",
            "2026-05-30 08:00",
            "2d 0h",
            "anna",
            "Przegląd wykonany",
        ),
        (
            "Sprawna",
            "2026-05-30 08:00",
            "w toku",
            "4h 0m",
            "anna",
            "Gotowa do pracy",
        ),
    ]
