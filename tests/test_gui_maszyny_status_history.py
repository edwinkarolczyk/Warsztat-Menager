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
    monkeypatch.setattr(
        gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T12:00:00"
    )
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


def test_apply_machine_status_change_stores_photos_for_new_period(monkeypatch):
    monkeypatch.setattr(
        gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T13:00:00"
    )
    machine = {"status": "ok"}
    photos = ["data/maszyny/attachments/M-1/status_01.jpg"]

    changed = gui_maszyny._apply_machine_status_change(
        machine, "alert", actor="anna", note="Przegląd", photos=photos
    )

    assert changed is True
    assert machine["status_current"]["photos"] == photos


def test_machine_status_history_rows_show_photo_count(monkeypatch):
    monkeypatch.setattr(
        gui_maszyny, "_machine_now_iso", lambda: "2026-05-30T12:00:00"
    )
    machine = {
        "status_history": [
            {
                "status": "alert",
                "started_at": "2026-05-30T08:00:00",
                "ended_at": "2026-05-30T09:00:00",
                "duration_minutes": 60,
                "closed_by": "anna",
                "close_note": "Przegląd wykonany",
                "photos": ["one.jpg", "two.jpg"],
            }
        ],
        "status_current": {
            "status": "ok",
            "started_at": "2026-05-30T09:00:00",
            "changed_by": "anna",
            "note": "Gotowa",
            "photos": ["three.jpg"],
        },
    }

    rows = gui_maszyny._machine_status_history_rows(machine)

    assert rows[0][-1] == "Przegląd wykonany | zdjęcia: 2"
    assert rows[1][-1] == "Gotowa | zdjęcia: 1"


def test_copy_machine_status_photos_uses_attachment_directory(monkeypatch, tmp_path):
    attachment_root = tmp_path / "attachments"
    source = tmp_path / "Zdjęcie.JPG"
    source.write_bytes(b"photo")
    monkeypatch.setattr(
        gui_maszyny, "_machine_attachment_root", lambda: str(attachment_root)
    )

    copied = gui_maszyny._copy_machine_status_photos("M 1/2", [str(source)])

    assert len(copied) == 1
    target = attachment_root / "M_1_2"
    copied_path = gui_maszyny.os.path.relpath(copied[0], target)
    assert gui_maszyny.os.path.basename(copied_path) == "status_01.jpg"
    assert gui_maszyny.os.path.isfile(copied[0])
    assert gui_maszyny.os.path.splitext(copied[0])[1] == ".jpg"
