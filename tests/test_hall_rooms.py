# version: 1.0
from pathlib import Path

from widok_hali.rooms import (
    Room,
    load_rooms,
    location_values,
    next_room_id,
    point_in_polygon,
    room_at_point,
    save_rooms,
    sync_location_fields,
    sync_record_from_point,
)


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
            polygon=[(100, 0), (200, 0), (200, 100), (100, 100)],
        ),
    ]


def test_point_in_polygon_includes_edges():
    polygon = [(0, 0), (100, 0), (100, 100), (0, 100)]

    assert point_in_polygon(50, 50, polygon)
    assert point_in_polygon(0, 50, polygon)
    assert not point_in_polygon(120, 50, polygon)


def test_room_at_point_respects_hall():
    rooms = _rooms()
    rooms.append(
        Room(
            id="POM_0003",
            name="Hala 2",
            hala="2",
            polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )
    )

    assert room_at_point(rooms, 50, 50, hala="1").id == "POM_0001"
    assert room_at_point(rooms, 50, 50, hala="2").id == "POM_0003"


def test_legacy_location_is_mapped_to_stable_room_id():
    row = {
        "id": "42",
        "lokalizacja": "  tokarnia ",
        "nr_hali": "1",
        "x": 50,
        "y": 50,
    }

    sync_location_fields(row, _rooms())

    assert row["lokalizacja_id"] == "POM_0001"
    assert row["lokalizacja"] == "Tokarnia"
    assert row["placement_status"] == "placed"


def test_room_location_with_coordinates_outside_is_flagged_not_moved():
    row = {
        "id": "42",
        "lokalizacja": "Tokarnia",
        "nr_hali": "1",
        "x": 150,
        "y": 50,
    }

    sync_location_fields(row, _rooms())

    assert row["lokalizacja_id"] == "POM_0001"
    assert row["placement_status"] == "outside_room"
    assert (row["x"], row["y"]) == (150, 50)


def test_drag_between_rooms_updates_location_and_keeps_exact_xy():
    row = {
        "id": "42",
        "lokalizacja": "Tokarnia",
        "lokalizacja_id": "POM_0001",
        "nr_hali": "1",
        "x": 50,
        "y": 50,
    }

    sync_record_from_point(row, 150, 60, _rooms())

    assert row["lokalizacja_id"] == "POM_0002"
    assert row["lokalizacja"] == "Spawalnia"
    assert row["placement_status"] == "placed"
    assert (row["x"], row["y"]) == (150, 60)


def test_drag_outside_rooms_does_not_destroy_assignment():
    row = {
        "id": "42",
        "lokalizacja": "Tokarnia",
        "lokalizacja_id": "POM_0001",
        "nr_hali": "1",
        "x": 50,
        "y": 50,
    }

    sync_record_from_point(row, 250, 150, _rooms())

    assert row["lokalizacja_id"] == "POM_0001"
    assert row["lokalizacja"] == "Tokarnia"
    assert row["placement_status"] == "outside_room"
    assert (row["x"], row["y"]) == (250, 150)


def test_external_location_clears_room_id_without_touching_text():
    row = {
        "id": "42",
        "lokalizacja": "Serwis zewnętrzny",
        "lokalizacja_id": "POM_0001",
        "nr_hali": "1",
        "x": 50,
        "y": 50,
    }

    sync_location_fields(row, _rooms())

    assert row["lokalizacja_id"] == ""
    assert row["lokalizacja"] == "Serwis zewnętrzny"
    assert row["placement_status"] == "external"


def test_room_names_feed_location_values_and_keep_special_locations():
    values = location_values(_rooms())

    assert values[:2] == ("Tokarnia", "Spawalnia")
    assert "Serwis zewnętrzny" in values
    assert "Brak lokalizacji" in values


def test_next_room_id_is_stable_and_monotonic():
    rooms = _rooms()
    assert next_room_id(rooms) == "POM_0003"


def test_room_roundtrip_uses_versioned_atomic_document(tmp_path: Path):
    target = tmp_path / "pomieszczenia_hali.json"

    save_rooms(_rooms(), str(target))
    loaded = load_rooms(str(target))

    assert [room.id for room in loaded] == ["POM_0001", "POM_0002"]
    assert loaded[0].polygon == [(0, 0), (100, 0), (100, 100), (0, 100)]

    changed = _rooms()
    changed[0].name = "Tokarnia CNC"
    save_rooms(changed, str(target))

    assert (tmp_path / "pomieszczenia_hali.json.bak").exists()
    assert load_rooms(str(target))[0].name == "Tokarnia CNC"
