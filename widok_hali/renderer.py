from __future__ import annotations

"""Moduł rysujący siatkę hali, maszyny i ściany."""

import json
import os
import tkinter as tk
from tkinter import ttk, simpledialog

DATA_DIR = os.path.join("data", "widok_hali")
HALA_FILE = os.path.join(DATA_DIR, "hale.json")
MASZYNY_FILE = os.path.join(DATA_DIR, "maszyny.json")
SCIANY_FILE = os.path.join(DATA_DIR, "sciany.json")

STATUS_COLORS = {
    "ok": "#4caf50",
    "w_toku": "#2196f3",
    "awaria": "#ff4b4b",
    "nieznany": "#888888",
}


def _ensure_file(path: str, default):
    """Zapewnia istnienie pliku danych i zwraca wczytaną zawartość."""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_hale() -> list[dict]:
    return _ensure_file(HALA_FILE, [])


def save_hale(hale_list: list[dict]) -> None:
    os.makedirs(os.path.dirname(HALA_FILE), exist_ok=True)
    with open(HALA_FILE, "w", encoding="utf-8") as f:
        json.dump(hale_list, f, indent=2, ensure_ascii=False)


def load_machines() -> list[dict]:
    return _ensure_file(MASZYNY_FILE, [])


def load_walls() -> list[dict]:
    return _ensure_file(SCIANY_FILE, [])


class HalaRenderer(ttk.Frame):
    """Widok hali z siatką, maszynami i ścianami."""

    def __init__(self, parent, *, edit_mode: bool = False):
        super().__init__(parent, style="WM.Card.TFrame", padding=12)
        self.edit_mode = edit_mode
        self.hale = load_hale()
        self.machines = load_machines()
        self.walls = load_walls()
        self.start_x: int | None = None
        self.start_y: int | None = None

        self.style = ttk.Style()
        bg = self.style.lookup("WM.Card.TFrame", "background")
        self.cv = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        self.cv.bind("<Configure>", self._on_resize)
        if self.edit_mode:
            self.cv.bind("<Button-1>", self._on_click)
            self.cv.bind("<B1-Motion>", self._on_drag)
            self.cv.bind("<ButtonRelease-1>", self._on_release)

        self.redraw()

    # ------------------ drawing ------------------
    def _on_resize(self, _event):
        self.redraw()

    def redraw(self):
        self.cv.delete("all")
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        step = 40
        for x in range(0, w, step):
            self.cv.create_line(x, 0, x, h, fill="#2e323c")
        for y in range(0, h, step):
            self.cv.create_line(0, y, w, y, fill="#2e323c")

        self._draw_walls()
        self._draw_halls()
        self._draw_machines()

    def _draw_halls(self):
        for hala in self.hale:
            x1, y1, x2, y2 = (
                hala.get("x1", 0),
                hala.get("y1", 0),
                hala.get("x2", 0),
                hala.get("y2", 0),
            )
            self.cv.create_rectangle(x1, y1, x2, y2, outline="#ff4b4b", width=2)
            fg = self.style.lookup("WM.TLabel", "foreground")
            self.cv.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=hala.get("nazwa", ""),
                fill=fg,
            )

    def _draw_machines(self):
        fg = self.style.lookup("WM.TLabel", "foreground")
        for m in self.machines:
            x = m.get("x", 0)
            y = m.get("y", 0)
            size = m.get("size", 20)
            status = m.get("status", "nieznany").lower()
            color = STATUS_COLORS.get(status, STATUS_COLORS["nieznany"])
            self.cv.create_rectangle(
                x,
                y,
                x + size,
                y + size,
                outline=color,
                fill=color,
            )
            self.cv.create_text(x + size / 2, y - 6, text=m.get("nazwa", ""), fill=fg)

    def _draw_walls(self):
        for wall in self.walls:
            x1, y1, x2, y2 = (
                wall.get("x1", 0),
                wall.get("y1", 0),
                wall.get("x2", 0),
                wall.get("y2", 0),
            )
            self.cv.create_line(x1, y1, x2, y2, fill="#888888", width=4)

    # ------------------ editing halls ------------------
    def _on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def _on_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
        self.redraw()
        self.cv.create_rectangle(
            self.start_x,
            self.start_y,
            event.x,
            event.y,
            outline="#ff4b4b",
            dash=(4, 2),
        )

    def _on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
        name = simpledialog.askstring("Nowa hala", "Podaj nazwę hali:")
        if name:
            self.hale.append(
                {
                    "nazwa": name,
                    "x1": self.start_x,
                    "y1": self.start_y,
                    "x2": event.x,
                    "y2": event.y,
                }
            )
            save_hale(self.hale)
        self.start_x = None
        self.start_y = None
        self.redraw()
