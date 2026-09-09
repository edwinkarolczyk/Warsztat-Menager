# Plik: ui_context_help.py
# version: 1.2
# 1.2: dymki mieszczą się na ekranie i przy prawej krawędzi otwierają się w lewo.
"""Wspólne widgety pomocy kontekstowej i wyszukiwania dla Warsztat Menager."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def _popup_position(owner_x, owner_y, owner_width, popup_width, popup_height,
                    screen_width, screen_height, gap=6, margin=8):
    """Zwróć pozycję dymka mieszczącą go na ekranie."""
    x = owner_x + owner_width + gap
    if x + popup_width > screen_width - margin:
        x = owner_x - popup_width - gap
    x = max(margin, min(x, screen_width - popup_width - margin))
    y = max(margin, min(owner_y, screen_height - popup_height - margin))
    return int(x), int(y)


class _HelpPopup:
    def __init__(self, owner: tk.Misc, text: str):
        self.owner = owner
        self.text = str(text or "").strip()
        self.window = None

    def show(self) -> None:
        if not self.text or self.window is not None:
            return
        try:
            win = tk.Toplevel(self.owner)
            win.wm_overrideredirect(True)
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
            win.update_idletasks()
            x, y = _popup_position(
                self.owner.winfo_rootx(),
                self.owner.winfo_rooty(),
                self.owner.winfo_width(),
                win.winfo_reqwidth(),
                win.winfo_reqheight(),
                self.owner.winfo_screenwidth(),
                self.owner.winfo_screenheight(),
            )
            win.wm_geometry(f"+{x}+{y}")
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
    btn = ttk.Button(parent, text="!", width=2)
    popup = _HelpPopup(btn, text)
    btn.configure(command=popup.show)
    if not command_only:
        btn.bind("<Enter>", lambda _e: popup.show(), add="+")
        btn.bind("<Leave>", lambda _e: popup.hide(), add="+")
        btn.bind("<FocusOut>", lambda _e: popup.hide(), add="+")
    btn._wm_help_popup = popup
    if grid_kwargs:
        btn.grid(**grid_kwargs)
    return btn


def bind_help(widget: tk.Misc, text: str) -> None:
    """Dodaje dymek pomocy do istniejącego widgetu bez tworzenia przycisku."""
    popup = _HelpPopup(widget, text)
    widget.bind("<Enter>", lambda _e: popup.show(), add="+")
    widget.bind("<Leave>", lambda _e: popup.hide(), add="+")
    widget._wm_help_popup = popup


class SearchableCombobox(ttk.Combobox):
    """Combobox, który filtruje podpowiedzi w trakcie pisania."""

    def __init__(self, master=None, *, values=(), **kwargs):
        super().__init__(master, values=values, **kwargs)
        self._all_values = [str(value) for value in values]
        self.bind("<KeyRelease>", self._filter_values, add="+")
        self.bind("<FocusIn>", self._restore_values, add="+")

    def set_values(self, values) -> None:
        self._all_values = [str(value) for value in values]
        self.configure(values=self._all_values)

    def _restore_values(self, _event=None) -> None:
        self.configure(values=self._all_values)

    def _filter_values(self, event=None) -> None:
        if event is not None and getattr(event, "keysym", "") in {
            "Up", "Down", "Left", "Right", "Return", "Escape", "Tab"
        }:
            return
        query = self.get().strip().casefold()
        if not query:
            matches = self._all_values
        else:
            matches = [value for value in self._all_values if query in value.casefold()]
        self.configure(values=matches)
        if matches and query:
            try:
                self.event_generate("<Down>")
            except Exception:
                pass
