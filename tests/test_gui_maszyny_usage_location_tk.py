# version: 1.0
"""Headless Tk smoke dla lokalizacji w nagłówku Użytkowania maszyny."""

import tkinter.font as tkfont

import gui_maszyny
import widok_hali.machine_usage_location_patch as usage_patch
from widok_hali.rooms import Room


def test_usage_status_frame_shows_location_on_right_and_missing_is_clickable(monkeypatch):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk
    rows = [
        {
            "id": "27",
            "nazwa": "Tokarka",
            "status": "ok",
            "nr_hali": "1",
            "x": 900,
            "y": 900,
            "lokalizacja": "",
            "lokalizacja_id": "",
            "placement_status": "unplaced",
        }
    ]
    rooms = [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (300, 0), (300, 300), (0, 300)],
        )
    ]

    monkeypatch.setattr(usage_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(gui_maszyny, "get_config", lambda: {})
    monkeypatch.setattr(
        gui_maszyny,
        "load_machines_rows_with_fallback",
        lambda cfg, resolve_rel: (list(rows), "/tmp/maszyny.json"),
    )
    monkeypatch.setattr(gui_maszyny, "load_machines_rows", lambda: list(rows))

    root = tk.Tk()
    try:
        win = tk.Toplevel(root)
        win.title("Użytkowanie maszyny — 27")
        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True)
        status_box = ttk.LabelFrame(outer, text="Aktualny status")
        status_box.pack(fill="x")
        status = ttk.Label(
            status_box,
            text="Sprawna",
            foreground="#16a34a",
            font=("TkDefaultFont", 24, "bold"),
        )
        status.pack(anchor="w", padx=10, pady=8)
        root.update()

        location = status._wm_location_label
        assert location is not None
        assert str(location.cget("text")) == "Brak lokalizacji"
        assert status.pack_info()["side"] == "left"
        assert location.pack_info()["side"] == "right"
        assert tkfont.Font(font=location.cget("font")).cget("size") == 22
        assert str(location.cget("cursor")) == "hand2"
        assert location.bind("<Button-1>")
    finally:
        root.destroy()


def test_usage_status_frame_shows_existing_room_without_click_binding(monkeypatch):
    tk = gui_maszyny.tk
    ttk = gui_maszyny.ttk
    rows = [
        {
            "id": "27",
            "status": "ok",
            "nr_hali": "1",
            "x": 100,
            "y": 100,
            "lokalizacja": "Tokarnia",
            "lokalizacja_id": "POM_0001",
            "placement_status": "placed",
        }
    ]
    rooms = [
        Room(
            id="POM_0001",
            name="Tokarnia",
            hala="1",
            polygon=[(0, 0), (300, 0), (300, 300), (0, 300)],
        )
    ]

    monkeypatch.setattr(usage_patch, "load_rooms", lambda: list(rooms))
    monkeypatch.setattr(gui_maszyny, "get_config", lambda: {})
    monkeypatch.setattr(
        gui_maszyny,
        "load_machines_rows_with_fallback",
        lambda cfg, resolve_rel: (list(rows), "/tmp/maszyny.json"),
    )
    monkeypatch.setattr(gui_maszyny, "load_machines_rows", lambda: list(rows))

    root = tk.Tk()
    try:
        win = tk.Toplevel(root)
        win.title("Użytkowanie maszyny — 27")
        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True)
        status_box = ttk.LabelFrame(outer, text="Aktualny status")
        status_box.pack(fill="x")
        status = ttk.Label(
            status_box,
            text="Sprawna",
            foreground="#16a34a",
            font=("TkDefaultFont", 24, "bold"),
        )
        status.pack(anchor="w", padx=10, pady=8)
        root.update()

        location = status._wm_location_label
        assert location is not None
        assert str(location.cget("text")) == "Tokarnia"
        assert str(location.cget("cursor")) in ("", "arrow")
        assert not location.bind("<Button-1>")
    finally:
        root.destroy()
