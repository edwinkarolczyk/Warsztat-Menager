"""Prosty edytor konfiguracji zadań narzędzi."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk


class ToolsConfigDialog(tk.Toplevel):
    """Minimalne okno do edycji pliku ``zadania_narzedzia.json``."""

    def __init__(self, master: tk.Widget | None = None, *, path: str, on_save=None) -> None:
        super().__init__(master)
        self.title("Konfiguracja zadań narzędzi")
        self.resizable(True, True)
        self.path = path
        self.on_save = on_save

        self.text = tk.Text(self, width=80, height=25)
        self.text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=4, pady=(0, 4))
        ttk.Button(buttons, text="Zapisz", command=self._save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Anuluj", command=self.destroy).pack(side=tk.LEFT)

        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            data = {"collections": {}}
        self.text.insert("1.0", json.dumps(data, ensure_ascii=False, indent=2))

    def _save(self) -> None:
        """Zapisz plik i wywołaj ``on_save`` po sukcesie."""

        raw = self.text.get("1.0", tk.END).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Błąd", f"Niepoprawny JSON: {exc}")
            return

        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

        try:
            from logika_zadan import invalidate_cache
        except Exception:  # pragma: no cover - optional import
            invalidate_cache = None
        if callable(invalidate_cache):
            invalidate_cache()

        if callable(self.on_save):
            self.on_save()
        self.destroy()

