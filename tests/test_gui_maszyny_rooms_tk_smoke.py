# version: 1.0
"""Headless Tk smoke: działający renderer Maszyn + warstwa pomieszczeń."""

from types import SimpleNamespace

import pytest

import gui_maszyny
from widok_hali.rooms import Room


@pytest.mark.skipif(gui_maszyny.Image is None, reason="Pillow wymagany do smoke tła")
def test_room_layer_keeps_machine_drag_and_updates_location(tmp_path):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk

    background = tmp_path / "hala.png"
    gui_maszyny.Image.new("RGB", (1000, 500), "white").save(background)

    root = tk.Tk()
    try:
        root.geometry("1200x800")
        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)
        root.update_idletasks()

        row = {
            "id": "M-TEST",
            "nazwa": "Maszyna testowa",
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

        assert "M-TEST" in renderer.nodes_by_id
        assert renderer._scale_x == pytest.approx(renderer._scale_y)
        assert renderer._scale_x > 0

        start_x, start_y = renderer._map_bg_to_canvas(100, 100)
        target_x, target_y = renderer._map_bg_to_canvas(700, 100)
        renderer._on_press(SimpleNamespace(x=start_x, y=start_y))
        assert renderer._drag_active is True

        renderer._on_motion(SimpleNamespace(x=target_x, y=target_y))
        renderer._on_release(SimpleNamespace(x=target_x, y=target_y))
        root.update_idletasks()

        assert commits and commits[-1][0] == "M-TEST"
        assert row["lokalizacja_id"] == "POM_0002"
        assert row["lokalizacja"] == "Spawalnia"
        assert row["placement_status"] == "placed"

        renderer._edit_var.set(True)
        renderer._toggle_layout_edit()
        renderer._on_press(SimpleNamespace(x=target_x, y=target_y, state=0))
        assert renderer._drag_active is False
    finally:
        root.destroy()
