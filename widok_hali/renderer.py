"""Renderowanie siatki i hal na kanwie."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Iterable

from .const import (
    GRID_STEP,
    BG_GRID_COLOR,
    HALL_OUTLINE,
    LAYER_BACKGROUND,
    LAYER_GRID,
    LAYER_MACHINES,
    LAYER_OVERLAY,
)
from .models import Hala


class HalaRenderer:
    """Rysuje siatkę oraz prostokątne hale."""

    def __init__(self, canvas: tk.Canvas, style: ttk.Style):
        self.canvas = canvas
        self.style = style
        self._bg_image: tk.PhotoImage | None = None

    # --- background -------------------------------------------------
    def draw_background(self, path: str | None) -> None:
        """Narysuj tło z pliku lub siatkę szachownicy, gdy plik nie istnieje."""
        self.canvas.delete(LAYER_BACKGROUND)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if path:
            p = Path(path)
            if p.is_file():
                try:
                    self._bg_image = tk.PhotoImage(file=str(p))
                except tk.TclError:
                    self._bg_image = None
                if self._bg_image is not None:
                    self.canvas.create_image(
                        0,
                        0,
                        anchor="nw",
                        image=self._bg_image,
                        tags=LAYER_BACKGROUND,
                    )
                    return

        # fallback – szachownica
        colors = ("#3a3e48", "#404450")
        step = GRID_STEP
        for y in range(0, h, step):
            for x in range(0, w, step):
                color = colors[(x // step + y // step) % 2]
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + step,
                    y + step,
                    outline="",
                    fill=color,
                    tags=LAYER_BACKGROUND,
                )

    # --- machines ---------------------------------------------------
    def draw_machine(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        fill: str = "#5c5f6a",
    ) -> int:
        """Narysuj prostokątną maszynę na odpowiedniej warstwie."""
        return self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            outline="black",
            fill=fill,
            tags=LAYER_MACHINES,
        )

    # --- overlay ----------------------------------------------------
    def draw_status_overlay(
        self, x: int, y: int, text: str, fill: str = "white"
    ) -> int:
        """Dodaj nakładkę statusu dla maszyny."""
        return self.canvas.create_text(
            x,
            y,
            text=text,
            fill=fill,
            tags=LAYER_OVERLAY,
        )

    def draw(self, hale: Iterable[Hala]) -> None:
        """Narysuj siatkę i wszystkie hale."""
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        for x in range(0, w, GRID_STEP):
            self.canvas.create_line(
                x, 0, x, h, fill=BG_GRID_COLOR, tags=LAYER_GRID
            )
        for y in range(0, h, GRID_STEP):
            self.canvas.create_line(
                0, y, w, y, fill=BG_GRID_COLOR, tags=LAYER_GRID
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
                tags=LAYER_MACHINES,
            )
            self.canvas.create_text(
                (hala.x1 + hala.x2) / 2,
                (hala.y1 + hala.y2) / 2,
                text=hala.nazwa,
                fill=fg,
                tags=LAYER_OVERLAY,
            )
