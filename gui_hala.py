"""Prosty widok hali wykorzystujący komponent HalaRenderer."""

from __future__ import annotations

import tkinter as tk

from ui_theme import apply_theme_safe as apply_theme
from widok_hali.renderer import HalaRenderer

APP_TITLE = "Widok Hali"


def run_demo() -> None:
    """Uruchamia okno demonstracyjne widoku hali."""

    root = tk.Tk()
    root.title(APP_TITLE)
    apply_theme(root)
    renderer = HalaRenderer(root)
    renderer.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    run_demo()
