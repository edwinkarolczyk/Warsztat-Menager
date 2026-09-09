# version: 1.0
"""Tk smoke dla informacji o lokalizacji po drag&drop maszyny."""

from types import SimpleNamespace

import pytest

import gui_maszyny
from widok_hali.rooms import Room


@pytest.mark.skipif(gui_maszyny.Image is None, reason="Pillow wymagany do smoke tła")
def test_drag_shows_room_message_and_outside_sets_no_location(tmp_path):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk

    background = tmp_path / "hala_drag_feedback.png"
    gui_maszyny.Image.new("RGB", (1000, 500), "white").save(background)

    root = tk.Tk()
    try:
        root._wm_role = "brygadzista"
        root.geometry("1200x800")
        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)
        root.update_idletasks()

        row = {
            "id": "M-TEST",
            "nazwa": "Tokarka",
            "status": "ok",
            "nr_hali": "1",
            "x": 100,
            "y": 100,
            "lokalizacja": "Tokarnia",
            "lokalizacja_id": "POM_0001",
            "placement_status": "placed",
        }
        commits = []
        renderer = gui_maszyny.MachineHallRenderer(
            frame,
            [row],
            cfg={},
            bg_path=str(background),
            on_drag_commit=lambda mid, x, y: commits.append((mid, x, y)),
        )
        renderer._rooms = [
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
        renderer.render()
        root.update()

        start_x, start_y = renderer._map_bg_to_canvas(100, 100)
        room_x, room_y = renderer._map_bg_to_canvas(700, 100)
        renderer._on_press(SimpleNamespace(x=start_x, y=start_y))
        renderer._on_motion(SimpleNamespace(x=room_x, y=room_y))
        renderer._on_release(SimpleNamespace(x=room_x, y=room_y))
        root.update_idletasks()

        assert row["lokalizacja"] == "Spawalnia"
        assert row["lokalizacja_id"] == "POM_0002"
        assert row["placement_status"] == "placed"
        assert renderer._status_var.get() == "Maszyna M-TEST → Spawalnia"

        outside_x, outside_y = renderer._map_bg_to_canvas(950, 450)
        renderer._on_press(SimpleNamespace(x=room_x, y=room_y))
        renderer._on_motion(SimpleNamespace(x=outside_x, y=outside_y))
        renderer._on_release(SimpleNamespace(x=outside_x, y=outside_y))
        root.update_idletasks()

        assert len(commits) == 2
        assert row["lokalizacja"] == ""
        assert row["lokalizacja_id"] == ""
        assert row["placement_status"] == "unplaced"
        assert renderer._status_var.get() == "Maszyna M-TEST → Brak lokalizacji"
    finally:
        root.destroy()
