# Wersja pliku: 1.0.0
# Zmiany: Minimalna funkcja apply_theme(root) – ciemny motyw WM
# ⏹ KONIEC WSTĘPU

from __future__ import annotations
import tkinter as tk
from tkinter import ttk


def apply_theme(root: tk.Misc) -> None:
    """Apply a dark WM theme to the given root widget."""
    print("[WM-DBG] apply_theme()")
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = "#111418"
    fg = "#E8E8E8"
    accent = "#C62828"

    style.configure("TNotebook", background=bg, foreground=fg)
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=accent, foreground=fg)
    style.map("TButton", background=[("active", accent)])
    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("TEntry", fieldbackground=bg, foreground=fg)
    style.configure("TCombobox", fieldbackground=bg, foreground=fg)
    style.configure(
        "Treeview",
        background=bg,
        foreground=fg,
        fieldbackground=bg,
    )
    style.map(
        "Treeview",
        background=[("selected", accent)],
        foreground=[("selected", fg)],
    )

    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=bg)

# ⏹ KONIEC KODU
