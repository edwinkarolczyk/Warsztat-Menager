# version: 1.0
import gui_maszyny
import widok_hali.machine_rooms_patch as rooms_patch
import widok_hali.machine_rooms_ui_patch as ui_patch
from widok_hali.rooms import Room, point_in_polygon


def _rooms():
    return [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        ),
        Room(
            id="POM_0002",
            name="Spawalnia",
            hala="1",
            polygon=[(120, 0), (260, 0), (260, 140), (120, 140)],
        ),
    ]


def test_room_ui_extension_is_installed():
    assert gui_maszyny._WM_ROOM_UI_INSTALLED is True
    assert hasattr(gui_maszyny.MachineHallRenderer, "_wm_refresh_visibility")


def test_change_room_relocates_machine_inside_new_room(monkeypatch):
    rooms = _rooms()
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: rooms)
    monkeypatch.setattr(rooms_patch, "load_rooms", lambda: rooms)

    rows = [
        {
            "id": "M-1",
            "nazwa": "Tokarka",
            "status": "ok",
            "nr_hali": "1",
            "lokalizacja": "Tokarnia",
            "lokalizacja_id": "POM_0001",
            "placement_status": "placed",
            "x": 50,
            "y": 50,
        },
        {
            "id": "M-2",
            "nazwa": "Spawarka",
            "status": "ok",
            "nr_hali": "1",
            "lokalizacja": "Spawalnia",
            "lokalizacja_id": "POM_0002",
            "placement_status": "placed",
            "x": 190,
            "y": 70,
        },
    ]

    update = dict(rows[0])
    update["lokalizacja"] = "Spawalnia"
    # Formularz zachowuje stare x/y; wrapper ma rozpoznać zmianę pomieszczenia.
    result = gui_maszyny.upsert_machine(rows, update)
    changed = next(row for row in result if row["id"] == "M-1")

    assert changed["lokalizacja"] == "Spawalnia"
    assert changed["lokalizacja_id"] == "POM_0002"
    assert changed["placement_status"] == "placed"
    assert point_in_polygon(changed["x"], changed["y"], rooms[1].polygon)
    assert (changed["x"], changed["y"]) != (50, 50)
    assert (changed["x"], changed["y"]) != (190, 70)


def test_same_room_keeps_exact_machine_coordinates(monkeypatch):
    rooms = _rooms()
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: rooms)
    monkeypatch.setattr(rooms_patch, "load_rooms", lambda: rooms)
    rows = [
        {
            "id": "M-1",
            "status": "ok",
            "nr_hali": "1",
            "lokalizacja": "Tokarnia",
            "lokalizacja_id": "POM_0001",
            "placement_status": "placed",
            "x": 33,
            "y": 44,
        }
    ]

    result = gui_maszyny.upsert_machine(rows, dict(rows[0]))
    changed = result[0]

    assert (changed["x"], changed["y"]) == (33, 44)
    assert changed["lokalizacja_id"] == "POM_0001"
