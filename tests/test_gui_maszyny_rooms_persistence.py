# version: 1.0
"""Regresja zapisu lokalizacji przy przeładowywaniu rows_cache."""
from __future__ import annotations

import gui_maszyny
from widok_hali import machine_rooms_patch
from widok_hali.rooms import Room


def _machine(mid: str, *, x: int, y: int, room_id: str, room_name: str) -> dict:
    return {
        "id": mid,
        "nazwa": f"Maszyna {mid}",
        "status": "ok",
        "nr_hali": "1",
        "x": x,
        "y": y,
        "lokalizacja": room_name,
        "lokalizacja_id": room_id,
        "placement_status": "placed",
    }


def test_batch_location_snapshot_survives_reload_after_each_commit(monkeypatch):
    room = Room(
        id="POM_0001",
        name="Tokarnia CNC",
        hala="1",
        polygon=[(0, 0), (400, 0), (400, 400), (0, 400)],
    )
    monkeypatch.setattr(machine_rooms_patch, "load_rooms", lambda: [room])

    persisted = [
        _machine("M-1", x=100, y=100, room_id="POM_0001", room_name="Tokarnia"),
        _machine("M-2", x=200, y=100, room_id="POM_0001", room_name="Tokarnia"),
    ]

    renderer = gui_maszyny.MachineHallRenderer.__new__(gui_maszyny.MachineHallRenderer)
    renderer.rows = [dict(row) for row in persisted]
    renderer._rooms = [room]

    def stale_legacy_commit(mid: str, x: int, y: int) -> None:
        nonlocal persisted
        update = dict(next(row for row in persisted if row["id"] == mid))
        update["x"], update["y"] = x, y
        persisted = gui_maszyny.upsert_machine(persisted, update)
        # Tak zachowuje się panel po zapisie: rows_cache jest zastępowane
        # świeżo wczytaną listą. Drugi rekord nie może stracić swojej migawki.
        renderer.rows = [dict(row) for row in persisted]

    renderer._wm_original_drag_commit = stale_legacy_commit
    renderer._sync_and_persist_machine_locations()

    assert [row["lokalizacja"] for row in persisted] == ["Tokarnia CNC", "Tokarnia CNC"]
    assert [row["lokalizacja_id"] for row in persisted] == ["POM_0001", "POM_0001"]
    assert [row["placement_status"] for row in persisted] == ["placed", "placed"]


def test_single_drag_persists_new_room_even_with_stale_backing_row(monkeypatch):
    rooms = [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (400, 0), (400, 400), (0, 400)],
        ),
        Room(
            id="POM_0002",
            name="Spawalnia",
            hala="1",
            polygon=[(500, 0), (900, 0), (900, 400), (500, 400)],
        ),
    ]
    monkeypatch.setattr(machine_rooms_patch, "load_rooms", lambda: rooms)

    persisted = [
        _machine("M-1", x=100, y=100, room_id="POM_0001", room_name="Tokarnia")
    ]
    current = _machine(
        "M-1", x=700, y=100, room_id="POM_0002", room_name="Spawalnia"
    )

    renderer = gui_maszyny.MachineHallRenderer.__new__(gui_maszyny.MachineHallRenderer)
    renderer.rows = [current]

    def stale_legacy_commit(mid: str, x: int, y: int) -> None:
        nonlocal persisted
        update = dict(next(row for row in persisted if row["id"] == mid))
        update["x"], update["y"] = x, y
        persisted = gui_maszyny.upsert_machine(persisted, update)

    renderer._wm_original_drag_commit = stale_legacy_commit
    renderer._wm_commit_with_current_location("M-1", 700, 100)

    assert persisted[0]["lokalizacja"] == "Spawalnia"
    assert persisted[0]["lokalizacja_id"] == "POM_0002"
    assert persisted[0]["placement_status"] == "placed"
