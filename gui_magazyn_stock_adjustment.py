"""Dialog ręcznej korekty stanu faktycznego Magazynu."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from magazyn_stock_adjustment import adjust_actual_stock


def _stock_text(value) -> str:
    try:
        return f"{float(str(value or 0).replace(',', '.')):g}"
    except (TypeError, ValueError):
        return "0"


class StockAdjustmentDialog:
    def __init__(self, master, item_id, item, author, on_saved=None):
        self.item_id = str(item_id)
        self.item = dict(item or {})
        self.author = str(author or "")
        self.on_saved = on_saved
        current = self.item.get("stan", 0)

        self.win = tk.Toplevel(master)
        self.win.title(f"Korekta stanu faktycznego: {self.item_id}")
        self.win.resizable(False, False)
        self.var_stock = tk.StringVar(value=_stock_text(current))
        self.var_reason = tk.StringVar(value="")

        frm = ttk.Frame(self.win, padding=14)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text="Pozycja:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(
            frm,
            text=f"{self.item_id} — {self.item.get('nazwa', '')}",
        ).grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Aktualny stan:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(
            frm,
            text=f"{_stock_text(current)} {self.item.get('jednostka', '')}",
        ).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Nowy stan faktyczny:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.var_stock, width=34).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Label(frm, text="Powód korekty:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.var_reason, width=34).grid(
            row=3, column=1, sticky="ew", pady=4
        )
        ttk.Label(
            frm,
            text="Korekta zapisze osobę, czas, stan przed i po oraz podany powód.",
            wraplength=480,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 2))

        buttons = ttk.Frame(frm)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Anuluj", command=self.win.destroy).pack(side="right")
        ttk.Button(buttons, text="Zapisz korektę", command=self._save).pack(
            side="right", padx=(0, 8)
        )

        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def _save(self):
        try:
            record = adjust_actual_stock(
                self.item_id,
                self.var_stock.get(),
                current_stock=self.item.get("stan", 0),
                user=self.author,
                reason=self.var_reason.get(),
                item=self.item,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            messagebox.showerror("Korekta stanu", str(exc), parent=self.win)
            return
        if callable(self.on_saved):
            self.on_saved(self.item_id)
        messagebox.showinfo(
            "Korekta stanu",
            f"Stan zmieniono z {record['stan_przed']:g} na {record['stan_po']:g}.",
            parent=self.win,
        )
        self.win.destroy()


def open_stock_adjustment_dialog(master, item_id, item, author, on_saved=None):
    StockAdjustmentDialog(master, item_id, item, author, on_saved=on_saved)
