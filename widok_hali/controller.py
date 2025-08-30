"""Prosty kontroler widoku hali."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import Any, Dict, List, Optional

from config_manager import ConfigManager
from maszyny_logika import load_machines, _save_machines as save_machines

from .const import HALL_OUTLINE
from .models import Hala
from .renderer import HalaRenderer
from .storage import load_hale, save_hale
from .a_star import a_star
from .animator import Animator


class HalaController:
    """Zarządza kanwą, rysowaniem hal i maszyn."""

    def __init__(
        self, canvas: tk.Canvas, style: ttk.Style, edit_mode: bool = False
    ):
        self.canvas = canvas
        self.style = style
        self.edit_mode = edit_mode
        self.hale: List[Hala] = load_hale()
        self.machines: List[Dict[str, Any]] = load_machines()
        cfg = ConfigManager()
        self.drag_snap_px = cfg.get("hall.drag_snap_px", 20)
        self.triple_confirm_delete = cfg.get(
            "hall.triple_confirm_delete", False
        )
        self.renderer = HalaRenderer(canvas, style)
        self.animator = Animator(canvas)
        self.mode: str = "view"
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.dragged_machine: Optional[Dict[str, Any]] = None
        self.drag_last_x = 0
        self.drag_last_y = 0

        self.canvas.bind("<Configure>", lambda e: self.redraw())
        if self.edit_mode:
            self.canvas.bind("<Button-1>", self.on_click)
            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_drop)
        self.redraw()
        self.check_for_awaria()

    def set_mode(self, mode: str) -> None:
        """Ustaw tryb pracy kontrolera."""
        self.mode = mode
        self.start_x = None
        self.start_y = None
        self.dragged_machine = None

    def redraw(self) -> None:
        """Przerysuj halę i maszyny."""
        self.renderer.draw(self.hale)
        for m in self.machines:
            x, y = m.get("x", 0), m.get("y", 0)
            self.canvas.create_oval(
                x - 5, y - 5, x + 5, y + 5, fill="blue", tags="machine"
            )

    # --- event handlers ---
    def on_click(self, event: tk.Event) -> None:
        if self.mode == "add_hall":
            self.start_x, self.start_y = event.x, event.y
        elif self.mode == "drag_machine":
            self.dragged_machine = self._machine_at(event.x, event.y)
            self.drag_last_x, self.drag_last_y = event.x, event.y

    def on_drag(self, event: tk.Event) -> None:
        if self.mode == "add_hall":
            if self.start_x is None or self.start_y is None:
                return
            self.redraw()
            self.canvas.create_rectangle(
                self.start_x,
                self.start_y,
                event.x,
                event.y,
                outline=HALL_OUTLINE,
                dash=(4, 2),
            )
        elif self.mode == "drag_machine" and self.dragged_machine:
            dx = event.x - self.drag_last_x
            dy = event.y - self.drag_last_y
            self.dragged_machine["x"] += dx
            self.dragged_machine["y"] += dy
            self.drag_last_x, self.drag_last_y = event.x, event.y
            self.redraw()

    def on_drop(self, event: tk.Event) -> None:
        if self.mode == "add_hall":
            if self.start_x is None or self.start_y is None:
                return
            name = simpledialog.askstring("Nowa hala", "Podaj nazwę hali:")
            if name:
                hala = Hala(name, self.start_x, self.start_y, event.x, event.y)
                self.hale.append(hala)
                save_hale(self.hale)
            self.start_x = None
            self.start_y = None
            self.redraw()
        elif self.mode == "drag_machine" and self.dragged_machine:
            snap = self.drag_snap_px
            self.dragged_machine["x"] = (
                round(self.dragged_machine["x"] / snap) * snap
            )
            self.dragged_machine["y"] = (
                round(self.dragged_machine["y"] / snap) * snap
            )
            save_machines(self.machines)
            self.dragged_machine = None
            self.redraw()
            self.check_for_awaria()

    def delete_machine_with_triple_confirm(self, machine_id: str) -> bool:
        """Usuń maszynę po wielokrotnym potwierdzeniu."""
        confirms = 3 if self.triple_confirm_delete else 1
        for _ in range(confirms):
            ans = simpledialog.askstring(
                "Potwierdzenie", "Wpisz USUN aby potwierdzić:"
            )
            if ans != "USUN":
                return False
        before = len(self.machines)
        self.machines = [
            m for m in self.machines if m.get("nr_ewid") != machine_id
        ]
        if len(self.machines) == before:
            return False
        save_machines(self.machines)
        self.redraw()
        return True

    def _machine_at(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        for m in reversed(self.machines):
            mx, my = m.get("x", 0), m.get("y", 0)
            if abs(mx - x) <= 5 and abs(my - y) <= 5:
                return m
        return None

    def check_for_awaria(self) -> None:
        """Uruchom animację dla maszyn ze statusem AWARIA."""
        for m in self.machines:
            if m.get("status") == "AWARIA":
                self._route_and_animate(m)

    def _route_and_animate(self, machine: Dict[str, Any]) -> None:
        a_star(
            (machine.get("x", 0), machine.get("y", 0)),
            (0, 0),
            lambda n: [],
            lambda a, b: 0,
        )
        self.animator.start()
