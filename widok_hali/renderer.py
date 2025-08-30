"""Funkcje rysujące elementy widoku hali na kanwie Tkinter."""

from __future__ import annotations

import tkinter as tk
from typing import Iterable

from .const import BG_GRID_COLOR, GRID_STEP, HALL_OUTLINE
from .models import Machine, WallSegment

try:  # pragma: no cover - logger opcjonalny w testach
    from logger import log_akcja as _log
except Exception:  # pragma: no cover - fallback
    def _log(msg: str) -> None:  # type: ignore
        print(msg)


def draw_background(canvas: tk.Canvas, path: str, width: int, height: int) -> None:
    """Rysuj tło z pliku ``path`` lub szachownicę gdy plik nie istnieje."""

    try:
        img = tk.PhotoImage(file=path)
        canvas.image = img  # type: ignore[attr-defined]
        canvas.create_image(0, 0, image=img, anchor="nw", tags=("background",))
    except Exception:
        _log(f"[HALA][WARN] Brak pliku tła {path}")
        size = 20
        for y in range(0, height, size):
            for x in range(0, width, size):
                fill = "#cccccc" if (x // size + y // size) % 2 == 0 else "#eeeeee"
                canvas.create_rectangle(
                    x,
                    y,
                    x + size,
                    y + size,
                    fill=fill,
                    outline=fill,
                    tags=("background",),
                )
    canvas.tag_lower("background")


def draw_grid(canvas: tk.Canvas, width: int, height: int) -> None:
    """Rysuj siatkę o kroku ``GRID_STEP``."""

    for x in range(0, width, GRID_STEP):
        canvas.create_line(
            x,
            0,
            x,
            height,
            fill=BG_GRID_COLOR,
            tags=("grid",),
        )
    for y in range(0, height, GRID_STEP):
        canvas.create_line(
            0,
            y,
            width,
            y,
            fill=BG_GRID_COLOR,
            tags=("grid",),
        )
    canvas.tag_lower("grid")


def draw_walls(canvas: tk.Canvas, walls: Iterable[WallSegment]) -> None:
    """Rysuj segmenty ścian."""

    for w in walls:
        canvas.create_line(
            w.x1,
            w.y1,
            w.x2,
            w.y2,
            width=2,
            fill=HALL_OUTLINE,
            tags=("walls",),
        )


def draw_machine(canvas: tk.Canvas, machine: Machine) -> int:
    """Rysuj pojedynczą maszynę jako małe kółko."""

    r = 5
    item = canvas.create_oval(
        machine.x - r,
        machine.y - r,
        machine.x + r,
        machine.y + r,
        fill="blue",
        tags=("machines", f"machine:{machine.id}"),
    )
    return item


def draw_status_overlay(canvas: tk.Canvas, machine: Machine) -> None:
    """Rysuj nakładkę informującą o statusie maszyny."""

    if machine.status == "OK":
        return
    color = "red" if machine.status == "AWARIA" else "orange"
    canvas.create_text(
        machine.x,
        machine.y - 10,
        text=machine.status,
        fill=color,
        tags=("overlays",),
    )


__all__ = [
    "draw_background",
    "draw_grid",
    "draw_walls",
    "draw_machine",
    "draw_status_overlay",
]

