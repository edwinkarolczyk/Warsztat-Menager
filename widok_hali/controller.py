"""Prosty kontroler widoku hali."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import List

from .const import HALL_OUTLINE
from .models import Hala
from .renderer import HalaRenderer
from .storage import load_hale, save_hale


class HalaController:
    """Zarządza kanwą, rysowaniem i dodawaniem nowych hal."""

    def __init__(self, canvas: tk.Canvas, style: ttk.Style, edit_mode: bool = False):
        self.canvas = canvas
        self.style = style
        self.edit_mode = edit_mode
        self.hale: List[Hala] = load_hale()
        self.renderer = HalaRenderer(canvas, style)
        self.start_x: int | None = None
        self.start_y: int | None = None

        self.canvas.bind("<Configure>", lambda e: self.renderer.draw(self.hale))
        if self.edit_mode:
            self.canvas.bind("<Button-1>", self.on_click)
            self.canvas.bind("<B1-Motion>", self.on_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.renderer.draw(self.hale)

    # --- event handlers ---
    def on_click(self, event: tk.Event) -> None:
        self.start_x, self.start_y = event.x, event.y

    def on_drag(self, event: tk.Event) -> None:
        if self.start_x is None or self.start_y is None:
            return
        self.renderer.draw(self.hale)
        self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            event.x,
            event.y,
            outline=HALL_OUTLINE,
            dash=(4, 2),
        )

    def on_release(self, event: tk.Event) -> None:
        if self.start_x is None or self.start_y is None:
            return
        name = simpledialog.askstring("Nowa hala", "Podaj nazwę hali:")
        if name:
            hala = Hala(name, self.start_x, self.start_y, event.x, event.y)
            self.hale.append(hala)
            save_hale(self.hale)
        self.start_x = None
        self.start_y = None
        self.renderer.draw(self.hale)
