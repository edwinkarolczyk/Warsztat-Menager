"""Kontroler widoku hali."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import List, Optional

from .a_star import find_path
from .animator import RouteAnimator
from .models import Machine, WallSegment
from .renderer import (
    draw_background,
    draw_grid,
    draw_machine,
    draw_status_overlay,
    draw_walls,
)
from .storage import (
    load_config_hala,
    load_machines,
    load_walls,
    save_machines,
)


class HalaController:
    """Zarządza kanwą i interakcją użytkownika."""

    def __init__(self, canvas: tk.Canvas, style: ttk.Style) -> None:
        self.canvas = canvas
        self.style = style
        self.cfg = load_config_hala()
        self.drag_snap_px = int(self.cfg.get("drag_snap_px", 4))
        self.triple_confirm_delete = bool(
            self.cfg.get("triple_confirm_delete", False)
        )
        self.workshop_start = tuple(self.cfg.get("workshop_start", [0, 0]))
        self.anim_interval_ms = int(self.cfg.get("anim_interval_ms", 20))

        self.machines: List[Machine] = load_machines()
        self.walls: List[WallSegment] = load_walls()
        self.active_hala: Optional[str] = (
            self.machines[0].hala if self.machines else None
        )

        self.mode = "view"
        self.dragged: Optional[Machine] = None
        self.drag_last_x = 0
        self.drag_last_y = 0

        self.animator = RouteAnimator(canvas)

        canvas.bind("<Configure>", lambda e: self.redraw())
        canvas.bind("<Button-1>", self.on_click)
        canvas.bind("<B1-Motion>", self.on_drag)
        canvas.bind("<ButtonRelease-1>", self.on_drop)

        self.redraw()
        self.check_for_awaria()

    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.dragged = None

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Zapisz dane i przerysuj widok."""

        save_machines(self.machines)
        self.redraw()

    # ------------------------------------------------------------------
    def redraw(self) -> None:
        """Przerysuj halę i wszystkie obiekty."""

        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        bg_path = ""
        bgs = self.cfg.get("backgrounds", [])
        if isinstance(bgs, list):
            for bg in bgs:
                if isinstance(bg, dict) and bg.get("hala") == self.active_hala:
                    bg_path = str(bg.get("file", ""))
                    break
                if isinstance(bg, str) and not bg_path:
                    bg_path = bg
        draw_background(self.canvas, bg_path, w, h)

        if self.cfg.get("show_grid", True):
            draw_grid(self.canvas, w, h)

        walls = [w for w in self.walls if w.hala == self.active_hala]
        draw_walls(self.canvas, walls)

        for m in self.machines:
            if m.hala != self.active_hala:
                continue
            draw_machine(self.canvas, m)
            draw_status_overlay(self.canvas, m)

    # ------------------------------------------------------------------
    def on_click(self, event: tk.Event) -> None:
        if self.mode == "edit":
            self.dragged = self._machine_at(event.x, event.y)
            self.drag_last_x, self.drag_last_y = event.x, event.y
        elif self.mode == "delete":
            m = self._machine_at(event.x, event.y)
            if m is not None:
                self.delete_machine_with_triple_confirm(m.id)

    # ------------------------------------------------------------------
    def on_drag(self, event: tk.Event) -> None:
        if self.mode == "edit" and self.dragged is not None:
            dx = event.x - self.drag_last_x
            dy = event.y - self.drag_last_y
            self.dragged.x += dx
            self.dragged.y += dy
            self.drag_last_x, self.drag_last_y = event.x, event.y
            self.redraw()

    # ------------------------------------------------------------------
    def on_drop(self, event: tk.Event) -> None:
        if self.mode == "edit" and self.dragged is not None:
            snap = self.drag_snap_px
            self.dragged.x = round(self.dragged.x / snap) * snap
            self.dragged.y = round(self.dragged.y / snap) * snap
            self.dragged = None
            self.refresh()
            self.check_for_awaria()

    # ------------------------------------------------------------------
    def _machine_at(self, x: int, y: int) -> Optional[Machine]:
        for m in reversed(self.machines):
            if m.hala != self.active_hala:
                continue
            if abs(m.x - x) <= 5 and abs(m.y - y) <= 5:
                return m
        return None

    # ------------------------------------------------------------------
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
        self.machines = [m for m in self.machines if m.id != machine_id]
        if len(self.machines) == before:
            return False
        self.refresh()
        return True

    # ------------------------------------------------------------------
    def check_for_awaria(self) -> None:
        for m in self.machines:
            if m.status == "AWARIA" and m.hala == self.active_hala:
                self._route_and_animate(m)

    # ------------------------------------------------------------------
    def _route_and_animate(self, machine: Machine) -> None:
        walls = [
            (w.x1, w.y1, w.x2, w.y2)
            for w in self.walls
            if w.hala == machine.hala
        ]
        path = find_path(self.workshop_start, (machine.x, machine.y), walls)
        self.animator.start(path, machine=machine, overlay=self, step_ms=self.anim_interval_ms)


__all__ = ["HalaController"]

