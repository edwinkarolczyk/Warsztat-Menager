"""Dialog okna zamówień magazynowych."""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from ui_theme import apply_theme_safe as apply_theme

ORDERS_PATH = Path("data/zamowienia_oczekujace.json")
logger = logging.getLogger(__name__)


class MagazynOrderDialog:
    """Prosty dialog dodawania pozycji do oczekujących zamówień."""

    def __init__(self, parent: tk.Misc, config=None, preselect_id: str | None = None, on_saved=None):
        self.parent = parent
        self.config = config
        self.preselect_id = preselect_id or ""
        self.on_saved = on_saved

        self.top = tk.Toplevel(parent)
        apply_theme(self.top)
        self.top.title("Dodaj do zamówienia")
        self.top.resizable(False, False)

        ttk.Label(self.top, text="ID:").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.var_id = tk.StringVar(value=self.preselect_id)
        ent_id = ttk.Entry(self.top, textvariable=self.var_id, state="readonly")
        ent_id.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ttk.Label(self.top, text="Ilość:").grid(row=1, column=0, padx=8, pady=8, sticky="e")
        self.var_qty = tk.StringVar()
        ent_qty = ttk.Entry(self.top, textvariable=self.var_qty)
        ent_qty.grid(row=1, column=1, padx=8, pady=8, sticky="w")

        btn = ttk.Button(self.top, text="Zapisz", command=self._save)
        btn.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 8))

    def _save(self) -> None:
        """Zapisz rekord do pliku zamówień."""
        try:
            qty = float(self.var_qty.get().replace(",", "."))
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Błąd", "Podaj poprawną dodatnią ilość.")
            return

        logger.debug("[WM-DBG][MAG][ORDER] start")
        data: list[dict[str, object]] = []
        if ORDERS_PATH.exists():
            try:
                raw = ORDERS_PATH.read_text(encoding="utf-8") or "[]"
                data = json.loads(raw)
                if not isinstance(data, list):
                    raise ValueError("Invalid structure")
            except Exception as e:
                logger.exception("Failed to read pending orders: %s", e)
                data = []

        data.append({"id": self.var_id.get(), "ilosc": qty})
        try:
            ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
            ORDERS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            check = json.loads(ORDERS_PATH.read_text(encoding="utf-8") or "[]")
            if not isinstance(check, list):
                raise ValueError("Invalid structure after save")
        except Exception as e:
            logger.exception("Failed to write pending orders: %s", e)
            messagebox.showerror("Błąd", f"Nie zapisano zamówienia: {e}")
            return

        logger.debug("[WM-DBG][MAG][ORDER] finish")
        if callable(self.on_saved):
            self.on_saved()
        self.top.destroy()
