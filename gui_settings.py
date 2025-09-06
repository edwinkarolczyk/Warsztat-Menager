# Wersja pliku: 1.5.0
# Plik: gui_settings.py
"""Proste okno ustawień oparte na ConfigManager."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from config_manager import ConfigManager


class SettingsWindow(tk.Toplevel):
    """Minimalne okno konfiguracji z obsługą zapisu i przywracania."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("Ustawienia")
        self.cfg = ConfigManager()
        self.vars: dict[str, tk.Variable] = {}
        self.schema: dict[str, Any] = {}
        self._load_files()
        self._build_ui()

    # ------------------------------------------------------------------
    def _load_files(self) -> None:
        """Load configuration schema and current values."""

        print("[WM-DBG][SETTINGS] loading files")
        self.schema = self.cfg.schema

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build widgets based on the current schema."""

        print("[WM-DBG][SETTINGS] building UI")
        opts = self.schema.get("options", [])
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        for row, opt in enumerate(opts):
            key = opt["key"]
            ttk.Label(body, text=opt.get("label", key)).grid(
                row=row, column=0, sticky="w", padx=5, pady=2
            )
            var = tk.StringVar(
                value=self.cfg.get(key, opt.get("default"))
            )
            entry = ttk.Entry(body, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            body.columnconfigure(1, weight=1)
            self.vars[key] = var

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(
            side="left", padx=5
        )
        ttk.Button(btns, text="Przywróć", command=self.on_restore).pack(
            side="left", padx=5
        )

    # ------------------------------------------------------------------
    def _set_conf_value(self, key: str, value: Any) -> None:
        """Store single configuration value."""

        print(f"[WM-DBG][SETTINGS] set {key}={value}")
        self.cfg.set(key, value)

    # ------------------------------------------------------------------
    def on_save(self) -> None:
        """Persist current values to disk."""

        print("[WM-DBG][SETTINGS] saving")
        for key, var in self.vars.items():
            self._set_conf_value(key, var.get())
        self.cfg.save_all()
        messagebox.showinfo("Zapisano", "Zapisano ustawienia.")

    # ------------------------------------------------------------------
    def on_restore(self) -> None:
        """Reload values from configuration and refresh widgets."""

        print("[WM-DBG][SETTINGS] restoring")
        for key, var in self.vars.items():
            var.set(self.cfg.get(key, ""))
