# version: 1.2
"""Headless Tk smoke: renderer Maszyn + pomieszczenia + kontrolki widoku/edycji."""

from types import SimpleNamespace

import pytest

import gui_maszyny
import widok_hali.machine_rooms_ui_patch as ui_patch
from widok_hali.rooms import Room


@pytest.mark.skipif(gui_maszyny.Image is None, reason="Pillow wymagany do smoke tła")
def test_room_layer_keeps_machine_drag_and_updates_location(tmp_path):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk

    background = tmp_path / "hala.png"
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

        # Tło JPG i siatka są niezależnymi warstwami, które można wyłączyć.
        assert renderer.canvas.find_withtag("hall-background")
        assert renderer.canvas.find_withtag("hall-grid")
        renderer._show_background_var.set(False)
        renderer._wm_refresh_visibility()
        root.update_idletasks()
        assert all(
            renderer.canvas.itemcget(item, "state") == "hidden"
            for item in renderer.canvas.find_withtag("hall-background")
        )
        renderer._show_grid_var.set(False)
        renderer._wm_refresh_visibility()
        root.update_idletasks()
        assert all(
            renderer.canvas.itemcget(item, "state") == "hidden"
            for item in renderer.canvas.find_withtag("hall-grid")
        )
        # Przywracamy warstwy przed testem drag&drop.
        renderer._show_background_var.set(True)
        renderer._show_grid_var.set(True)
        renderer._wm_refresh_visibility()

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


def test_machine_edit_location_is_readonly_dynamic_room_combobox(monkeypatch):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk
    rooms = [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        )
    ]
    monkeypatch.setattr(ui_patch, "load_rooms", lambda: list(rooms))

    root = tk.Tk()
    try:
        dialog = tk.Toplevel(root)
        dialog.title("Edycja maszyny")
        frm = ttk.Frame(dialog)
        frm.pack()

        fields = [ttk.Entry(frm, width=20) for _ in range(4)]
        location = fields[3]
        assert location.winfo_class() == "TCombobox"
        assert str(location.cget("state")) == "readonly"
        assert "Tokarnia" in tuple(location.cget("values"))

        rooms.append(
            Room(
                id="POM_0002",
                name="Spawalnia",
                hala="1",
                polygon=[(120, 0), (220, 0), (220, 100), (120, 100)],
            )
        )
        location._refresh_values()
        assert "Spawalnia" in tuple(location.cget("values"))
    finally:
        root.destroy()


@pytest.mark.skipif(gui_maszyny.Image is None, reason="Pillow wymagany do smoke tła")
def test_room_editor_is_brygadzista_only_and_rectangle_can_be_edited(tmp_path, monkeypatch):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk
    background = tmp_path / "hala_editor.png"
    gui_maszyny.Image.new("RGB", (600, 400), "white").save(background)

    # Pracownik widzi plan, ale nie dostaje paska modyfikującego pomieszczenia.
    worker_root = tk.Tk()
    try:
        worker_root._wm_role = "pracownik"
        worker_frame = ttk.Frame(worker_root)
        worker_frame.pack(fill="both", expand=True)
        worker_renderer = gui_maszyny.MachineHallRenderer(
            worker_frame,
            [],
            cfg={},
            bg_path=str(background),
            on_drag_commit=None,
        )
        worker_renderer.render()
        worker_root.update()
        assert worker_renderer._wm_edit_toolbar.winfo_manager() == ""
        worker_renderer._edit_var.set(True)
        worker_renderer._toggle_layout_edit()
        assert worker_renderer._layout_edit is False
        assert worker_renderer._edit_var.get() is False
    finally:
        worker_root.destroy()

    # Brygadzista dostaje pełny pasek i może zrobić prostokąt dwoma kliknięciami.
    root = tk.Tk()
    try:
        root._wm_role = "brygadzista"
        root.geometry("900x650")
        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)
        renderer = gui_maszyny.MachineHallRenderer(
            frame,
            [],
            cfg={},
            bg_path=str(background),
            on_drag_commit=None,
        )
        renderer._rooms = []
        renderer.render()
        root.update()

        assert renderer._wm_edit_toolbar.winfo_manager() == "pack"
        assert str(renderer._wm_btn_rectangle.cget("text")) == "Prostokąt"
        assert str(renderer._wm_btn_edit_room.cget("text")) == "Edytuj pomieszczenie"

        monkeypatch.setattr(
            gui_maszyny.simpledialog,
            "askstring",
            lambda *args, **kwargs: "Magazyn testowy",
        )
        renderer._edit_var.set(True)
        renderer._toggle_layout_edit()
        renderer._wm_start_rectangle()

        x1, y1 = renderer._map_bg_to_canvas(50, 50)
        x2, y2 = renderer._map_bg_to_canvas(250, 180)
        renderer._on_press(SimpleNamespace(x=x1, y=y1, state=0))
        assert renderer._wm_rectangle_start == (50, 50)
        renderer._on_canvas_motion(SimpleNamespace(x=x2, y=y2))
        assert renderer.canvas.find_withtag("hall-room-rect-preview")
        renderer._on_press(SimpleNamespace(x=x2, y=y2, state=0))

        assert len(renderer._rooms) == 1
        room = renderer._rooms[0]
        assert room.name == "Magazyn testowy"
        assert room.polygon == [(50, 50), (250, 50), (250, 180), (50, 180)]
        assert renderer._wm_room_tool == "edit"

        # Jawny tryb edycji: przeciągnięcie narożnika zmienia geometrię.
        renderer._wm_start_existing_room_edit()
        vx, vy = renderer._map_bg_to_canvas(50, 50)
        nx, ny = renderer._map_bg_to_canvas(70, 70)
        renderer._on_press(SimpleNamespace(x=vx, y=vy, state=0))
        assert renderer._vertex_drag == (room.id, 0)
        renderer._on_motion(SimpleNamespace(x=nx, y=ny, state=0))
        renderer._on_release(SimpleNamespace(x=nx, y=ny, state=0))
        assert room.polygon[0] == (70, 70)
        assert renderer._layout_dirty is True
    finally:
        root.destroy()
