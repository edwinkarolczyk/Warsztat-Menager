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

    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=(0, 8))

    canvas = tk.Canvas(frame, bg=bg, bd=0, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    ctrl = HalaController(canvas, style)

    halls = sorted({m.hala for m in ctrl.machines})
    hala_var = tk.StringVar(value=ctrl.active_hala or (halls[0] if halls else ""))
    hall_cb = ttk.Combobox(
        controls, textvariable=hala_var, values=halls, state="readonly", width=10
    )
    hall_cb.pack(side="left", padx=(0, 10))

    def _on_hall_change(event: tk.Event | None = None) -> None:
        ctrl.active_hala = hala_var.get()
        ctrl.redraw()

    hall_cb.bind("<<ComboboxSelected>>", _on_hall_change)

    mode_var = tk.StringVar(value="view")
    for mode in ("view", "edit", "delete"):
        ttk.Radiobutton(
            controls,
            text=mode,
            value=mode,
            variable=mode_var,
            command=lambda m=mode: ctrl.set_mode(m),
        ).pack(side="left")

    return win


if __name__ == "__main__":  # pragma: no cover
    root = tk.Tk()
    open_hala_window(root)
    root.mainloop()
