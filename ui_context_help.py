# Plik: ui_context_help.py
# version: 1.0
"""Wspólny system pomocy kontekstowej „!” dla formularzy Warsztat Menager."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class _HelpPopup:
    def __init__(self, owner: tk.Misc, text: str):
        self.owner = owner
        self.text = str(text or "").strip()
        self.window = None

    def show(self) -> None:
        if not self.text or self.window is not None:
            return
        try:
            x = self.owner.winfo_rootx() + self.owner.winfo_width() + 6
            y = self.owner.winfo_rooty()
            win = tk.Toplevel(self.owner)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            label = tk.Label(
                win,
                text=self.text,
                justify="left",
                relief="solid",
                borderwidth=1,
                padx=8,
                pady=6,
                wraplength=360,
            )
            label.pack()
            self.window = win
        except Exception:
            self.window = None

    def hide(self) -> None:
        if self.window is None:
            return
        try:
            self.window.destroy()
        except Exception:
            pass
        self.window = None


def add_help_button(parent: tk.Misc, text: str, *, command_only: bool = False, **grid_kwargs):
    """Tworzy mały przycisk „!” z krótką pomocą na hover i po kliknięciu.

    ``grid_kwargs`` są przekazywane bezpośrednio do ``grid``. Tekst powinien
    mieć maksymalnie dwa krótkie zdania.
    """
    popup = _HelpPopup(parent, text)
    btn = ttk.Button(parent, text="!", width=2, command=popup.show)
    if not command_only:
        btn.bind("<Enter>", lambda _e: popup.show(), add="+")
        btn.bind("<Leave>", lambda _e: popup.hide(), add="+")
        btn.bind("<FocusOut>", lambda _e: popup.hide(), add="+")
    btn._wm_help_popup = popup  # utrzymuje referencję przez cały czas życia widgetu
    if grid_kwargs:
        btn.grid(**grid_kwargs)
    return btn


def bind_help(widget: tk.Misc, text: str) -> None:
    """Dodaje dymek pomocy do istniejącego widgetu bez tworzenia przycisku."""
    popup = _HelpPopup(widget, text)
    widget.bind("<Enter>", lambda _e: popup.show(), add="+")
    widget.bind("<Leave>", lambda _e: popup.hide(), add="+")
    widget._wm_help_popup = popup
