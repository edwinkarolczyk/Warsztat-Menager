from __future__ import annotations

"""Prosty interfejs wyboru trybu dla widoku hali.

Moduł udostępnia klasę :class:`HalaModeSelector` prezentującą zestaw
przycisków radiowych, które pozwalają na zmianę trybu pracy kontrolera.
"""

import tkinter as tk
from tkinter import ttk

from controller import Controller


class HalaModeSelector(ttk.Frame):
    """UI zawierający radiobuttony do wyboru trybu."""

    def __init__(self, parent, controller: Controller, modes=None):
        super().__init__(parent)
        if modes is None:
            modes = ["select", "move", "add", "delete"]
        self.controller = controller
        self.var = tk.StringVar(value=self.controller.mode)
        for mode in modes:
            ttk.Radiobutton(
                self,
                text=mode.capitalize(),
                value=mode,
                variable=self.var,
                command=self._on_change,
            ).pack(side="left", padx=4)

    def _on_change(self):
        self.controller.set_mode(self.var.get())
