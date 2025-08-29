# Plik: gui_settings.py
# Panel ustawień powiadomień.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager


class NotificationsSettingsFrame(ttk.Frame):
    """Frame allowing configuration of event notifications."""

    def __init__(self, parent):
        super().__init__(parent)
        cfg = ConfigManager()
        self.enabled_var = tk.BooleanVar(
            value=cfg.get("notifications.enabled", True)
        )
        self.method_var = tk.StringVar(
            value=cfg.get("notifications.method", "messagebox")
        )

        ttk.Checkbutton(
            self,
            text="Włącz powiadomienia",
            variable=self.enabled_var,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=8)

        ttk.Label(self, text="Typ powiadomień:").grid(
            row=1, column=0, sticky="w", padx=8
        )
        ttk.Combobox(
            self,
            values=["toast", "messagebox"],
            state="readonly",
            textvariable=self.method_var,
            width=12,
        ).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 8))

        ttk.Button(self, text="Zapisz", command=self._save).grid(
            row=3, column=0, sticky="e", padx=8, pady=8
        )

    def _save(self) -> None:
        cfg = ConfigManager()
        cfg.set("notifications.enabled", bool(self.enabled_var.get()), who="user")
        cfg.set("notifications.method", self.method_var.get(), who="user")
        cfg.save_all()
