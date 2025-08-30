"""Renderowanie siatki i hal na kanwie."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable

from .const import BG_GRID_COLOR, HALL_OUTLINE, CANVAS_LAYERS
from .models import Hala


class HalaRenderer:
    """Rysuje siatkę oraz prostokątne hale."""

    def __init__(
        self,
        canvas: tk.Canvas,
        style: ttk.Style,
        *,
        grid_step_px: int,
        show_grid: bool,
    ):
        self.canvas = canvas
        self.style = style
        self.grid_step_px = grid_step_px
        self.show_grid = show_grid

    def draw(self, hale: Iterable[Hala]) -> None:
        """Narysuj siatkę i wszystkie hale."""
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if self.show_grid:
            for x in range(0, w, self.grid_step_px):
                self.canvas.create_line(
                    x, 0, x, h, fill=BG_GRID_COLOR, tags=CANVAS_LAYERS["grid"]
                )
            for y in range(0, h, self.grid_step_px):
                self.canvas.create_line(
                    0, y, w, y, fill=BG_GRID_COLOR, tags=CANVAS_LAYERS["grid"]
                )
        fg = self.style.lookup("WM.TLabel", "foreground")
        for hala in hale:
            self.canvas.create_rectangle(
                hala.x1,
                hala.y1,
                hala.x2,
                hala.y2,
                outline=HALL_OUTLINE,
                width=2,
                tags=CANVAS_LAYERS["halls"],
            )
            self.canvas.create_text(
                (hala.x1 + hala.x2) / 2,
                (hala.y1 + hala.y2) / 2,
                text=hala.nazwa,
                fill=fg,
                tags=CANVAS_LAYERS["halls"],
            )
