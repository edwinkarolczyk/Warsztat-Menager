"""Okno wizualizacji hal korzystające z modułu ``widok_hali``."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

try:
    from ui_theme import apply_theme_safe as apply_theme
except Exception:  # pragma: no cover - fallback
    def apply_theme(widget):  # type: ignore
        return None

try:
    from widok_hali import storage as HST
except Exception:  # pragma: no cover - awaryjne dane

    class _Dummy:
        @staticmethod
        def load_machines() -> tuple[list, dict]:
            return [], {"path": None, "label": "missing", "count": 0}

    HST = _Dummy()

from widok_hali import HalaController


def build_hala_view(parent: tk.Widget) -> HalaController:
    """Zbuduj widok hali w przekazanym ``parent`` i zwróć kontroler."""
    frame = ttk.Frame(parent, padding=12, style="WM.Card.TFrame")
    frame.pack(fill="both", expand=True)

    style = ttk.Style(parent)
    bg = style.lookup("WM.Card.TFrame", "background")

    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=(0, 8))

    _, src_meta = HST.load_machines()
    diag_bar = tk.Frame(frame, bg=bg)
    diag_bar.pack(fill="x", padx=8, pady=(8, 4))
    path_txt = src_meta.get("path") or "(nie znaleziono pliku)"
    label_txt = src_meta.get("label")
    count_txt = src_meta.get("count", 0)
    summary_txt = (
        f"Maszyny: {count_txt}  •  źródło: {path_txt}  •  wariant: {label_txt}"
    )
    tk.Label(
        diag_bar,
        text=summary_txt,
        anchor="w",
        bg=bg,
    ).pack(side="left", fill="x", expand=True)

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

    return ctrl


def open_hala_window(parent: tk.Tk | tk.Toplevel | None = None) -> tk.Toplevel:
    """Utwórz i zwróć pływające okno z wizualizacją hal."""
    win = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    win.title("Hale")
    apply_theme(win)
    build_hala_view(win)
    return win


if __name__ == "__main__":  # pragma: no cover
    root = tk.Tk()
    open_hala_window(root)
    root.mainloop()
