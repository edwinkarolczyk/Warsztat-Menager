"""Okno wizualizacji hal korzystające z modułu ``widok_hali``."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

try:
    from ui_theme import apply_theme_safe as apply_theme
except Exception:  # pragma: no cover - fallback
    def apply_theme(widget):  # type: ignore
        return None

from widok_hali import HalaController


def open_hala_window(parent: tk.Tk | tk.Toplevel | None = None) -> tk.Toplevel:
    """Utwórz i zwróć pływające okno z wizualizacją hal."""
    win = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    win.title("Hale")
    apply_theme(win)

    frame = ttk.Frame(win, padding=12, style="WM.Card.TFrame")
    frame.pack(fill="both", expand=True)

    style = ttk.Style(win)
    bg = style.lookup("WM.Card.TFrame", "background")
    canvas = tk.Canvas(frame, bg=bg, bd=0, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    HalaController(canvas, style)
    return win


if __name__ == "__main__":  # pragma: no cover
    root = tk.Tk()
    open_hala_window(root)
    root.mainloop()
