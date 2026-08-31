# version: 1.0
from copy import deepcopy

import gui_maszyny
import widok_hali.machine_rooms_ui_patch as ui_patch
import widok_hali.machine_usage_location_patch as usage_patch
from widok_hali.rooms import Room, point_in_polygon


def _rooms():
    return [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (200, 0), (200, 200), (0, 200)],
        ),
        Room(
            id="POM_0002",
            name="Spawalnia",
            hala="1",
            polygon=[(300, 0), (500, 0), (500, 200), (300, 200)],
        ),
    ]


def test_usage_location_extension_is_installed():
    assert gui_maszyny._WM_USAGE_LOCATION_INSTALLED is True
    assert callable(gui_maszyny._wm_assign_machine_to_room)


def test_click_assignment_persists_room_and_relocates_machine(monkeypatch):
    rooms = _rooms()
    rows = [
        {
            "id": "M-27",
            "nazwa": "Tokarka",
            "status": "ok",
            "nr_hali": "1",
            "x": 700,
            "y": 700,
            "lokalizacja": "",
            "lokalizacja_id": "",
            "placement_status": "unplaced",
        }
    ]
    saved = {}

    monkeypatch.setattr(usage_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(gui_maszyny, "get_config", lambda: {})
    monkeypatch.setattr(
        gui_maszyny,
        "load_machines_rows_with_fallback",
        lambda cfg, resolve_rel: (deepcopy(rows), "/tmp/maszyny.json"),
    )
    monkeypatch.setattr(gui_maszyny, "load_machines_rows", lambda: deepcopy(rows))

    def fake_save(path, new_rows):
        saved["path"] = path
        saved["rows"] = deepcopy(new_rows)
        return True

    monkeypatch.setattr(gui_maszyny, "_save_machines", fake_save)

    changed = gui_maszyny._wm_assign_machine_to_room("M-27", "Tokarnia")

    assert changed["lokalizacja"] == "Tokarnia"
    assert changed["lokalizacja_id"] == "POM_0001"
    assert changed["placement_status"] == "placed"
    assert point_in_polygon(changed["x"], changed["y"], rooms[0].polygon)
    assert saved["path"] == "/tmp/maszyny.json"
    assert saved["rows"][0]["lokalizacja"] == "Tokarnia"


def test_fresh_location_survives_later_stale_status_save(monkeypatch):
    rooms = _rooms()
    original = {
        "id": "M-27",
        "nazwa": "Tokarka",
        "status": "ok",
        "nr_hali": "1",
        "x": 700,
        "y": 700,
        "lokalizacja": "",
        "lokalizacja_id": "",
        "placement_status": "unplaced",
    }
    rows = [deepcopy(original)]

    monkeypatch.setattr(usage_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(gui_maszyny, "get_config", lambda: {})
    monkeypatch.setattr(
        gui_maszyny,
        "load_machines_rows_with_fallback",
        lambda cfg, resolve_rel: (deepcopy(rows), "/tmp/maszyny.json"),
    )
    monkeypatch.setattr(gui_maszyny, "load_machines_rows", lambda: deepcopy(rows))
    monkeypatch.setattr(gui_maszyny, "_save_machines", lambda path, new_rows: True)

    changed = gui_maszyny._wm_assign_machine_to_room("M-27", "Tokarnia")
    assert changed["lokalizacja"] == "Tokarnia"

    stale_status_update = deepcopy(original)
    stale_status_update["status"] = "warn"
    merged = gui_maszyny.upsert_machine(rows, stale_status_update)
    merged_row = merged[0]

    assert merged_row["status"] == "warn"
    assert merged_row["lokalizacja"] == "Tokarnia"
    assert merged_row["lokalizacja_id"] == "POM_0001"
    assert merged_row["placement_status"] == "placed"


def test_explicit_later_room_change_is_not_blocked(monkeypatch):
    rooms = _rooms()
    original = {
        "id": "M-27",
        "status": "ok",
        "nr_hali": "1",
        "x": 700,
        "y": 700,
        "lokalizacja": "",
        "lokalizacja_id": "",
        "placement_status": "unplaced",
    }
    rows = [deepcopy(original)]

    monkeypatch.setattr(usage_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(gui_maszyny, "get_config", lambda: {})
    monkeypatch.setattr(
        gui_maszyny,
        "load_machines_rows_with_fallback",
        lambda cfg, resolve_rel: (deepcopy(rows), "/tmp/maszyny.json"),
    )
    monkeypatch.setattr(gui_maszyny, "load_machines_rows", lambda: deepcopy(rows))
    monkeypatch.setattr(gui_maszyny, "_save_machines", lambda path, new_rows: True)

    gui_maszyny._wm_assign_machine_to_room("M-27", "Tokarnia")

    explicit = deepcopy(original)
    explicit["lokalizacja"] = "Spawalnia"
    explicit["lokalizacja_id"] = "POM_0002"
    explicit["placement_status"] = "outside_room"
    changed_rows = gui_maszyny.upsert_machine(rows, explicit)
    changed = changed_rows[0]

    assert changed["lokalizacja"] == "Spawalnia"
    assert changed["lokalizacja_id"] == "POM_0002"
    assert changed["placement_status"] == "placed"
    assert point_in_polygon(changed["x"], changed["y"], rooms[1].polygon)
