# version: 1.0
import gui_maszyny
from widok_hali.machine_rooms_editor_patch import (
    _is_brygadzista,
    _project_point_to_segment,
    _rectangle_polygon,
)


def test_room_editor_extension_is_installed():
    assert gui_maszyny._WM_ROOM_EDITOR_INSTALLED is True
    assert hasattr(gui_maszyny.MachineHallRenderer, "_wm_start_rectangle")
    assert hasattr(gui_maszyny.MachineHallRenderer, "_wm_start_existing_room_edit")
    assert hasattr(gui_maszyny.MachineHallRenderer, "_wm_start_add_point")
    assert hasattr(gui_maszyny.MachineHallRenderer, "_wm_insert_vertex_from_click")


def test_rectangle_from_two_opposite_corners():
    assert _rectangle_polygon((20, 30), (120, 90)) == [
        (20, 30),
        (120, 30),
        (120, 90),
        (20, 90),
    ]


def test_rectangle_accepts_reverse_corner_order():
    assert _rectangle_polygon((120, 90), (20, 30)) == [
        (20, 30),
        (120, 30),
        (120, 90),
        (20, 90),
    ]


def test_rectangle_rejects_accidental_tiny_shape():
    assert _rectangle_polygon((20, 30), (25, 35), minimum_size=10) is None


def test_only_brygadzista_gets_room_edit_permission():
    assert _is_brygadzista("brygadzista") is True
    assert _is_brygadzista(" Brygadzista ") is True
    assert _is_brygadzista("pracownik") is False
    assert _is_brygadzista("administrator") is False
    assert _is_brygadzista("lider") is False


def test_project_point_to_room_edge_returns_nearest_point():
    qx, qy, distance = _project_point_to_segment(
        50, 20,
        0, 0,
        100, 0,
    )
    assert qx == 50
    assert qy == 0
    assert distance == 20


def test_project_point_to_room_edge_clamps_to_segment_ends():
    qx, qy, distance = _project_point_to_segment(
        140, 0,
        0, 0,
        100, 0,
    )
    assert qx == 100
    assert qy == 0
    assert distance == 40
