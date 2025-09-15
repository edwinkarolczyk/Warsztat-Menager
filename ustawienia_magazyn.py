"""Magazyn settings tab."""

import tkinter as tk
from tkinter import ttk


class MagazynSettingsFrame(ttk.Frame):
    """Frame containing warehouse settings."""

    def __init__(self, master, config_manager, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.config_manager = config_manager

        ttk.Label(
            self, text="Ustawienia Magazynu", font=("Arial", 12, "bold")
        ).pack(pady=10)

        self.var_auto_res = tk.BooleanVar(
            value=self.config_manager.get("magazyn.auto_rezerwacje", True)
        )
        ttk.Checkbutton(
            self,
            text="Automatyczne rezerwacje materiałów",
            variable=self.var_auto_res,
        ).pack(anchor="w", padx=10, pady=5)

        self.var_alert = tk.IntVar(
            value=self.config_manager.get("magazyn.alert_procent", 10)
        )
        frm_alert = ttk.Frame(self)
        frm_alert.pack(fill="x", padx=10, pady=5)
        ttk.Label(frm_alert, text="Próg alertu stanu [%]:").pack(side="left")
        ttk.Entry(frm_alert, textvariable=self.var_alert, width=5).pack(side="left")

        ttk.Button(self, text="Zapisz", command=self.save).pack(pady=10)

    def save(self) -> None:
        """Save configuration values."""

        self.config_manager.set(
            "magazyn.auto_rezerwacje", self.var_auto_res.get()
        )
        self.config_manager.set("magazyn.alert_procent", self.var_alert.get())
        self.config_manager.save()

