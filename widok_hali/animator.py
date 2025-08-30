"""Proste miejsce na przyszłą animację elementów hali."""

from __future__ import annotations

import tkinter as tk


class Animator:
    """Szkielet klasy animatora – obecnie nie wykonuje żadnych akcji."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
