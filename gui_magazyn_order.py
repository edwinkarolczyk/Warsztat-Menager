"""Dialog okna zamówień magazynowych."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from ui_theme import apply_theme_safe as apply_theme
from logika_zakupy import add_item_to_orders, load_pending_orders

logger = logging.getLogger(__name__)


class MagazynOrderDialog:
    """Prosty dialog dodawania pozycji do oczekujących zamówień."""

    def __init__(
        self,
        parent: tk.Misc,
        config=None,
        preselect_id: str | None = None,
        on_saved=None,
    ):
        self.parent = parent
        self.config = config
        self.preselect_id = preselect_id or ""
        self.on_saved = on_saved

        self.top = tk.Toplevel(parent)
        apply_theme(self.top)
        self.top.title("Dodaj do zamówienia")
        self.top.resizable(False, False)

        ttk.Label(self.top, text="ID:").grid(
            row=0, column=0, padx=8, pady=8, sticky="e"
        )
        self.var_id = tk.StringVar(value=self.preselect_id)
        ent_id = ttk.Entry(self.top, textvariable=self.var_id, state="readonly")
        ent_id.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ttk.Label(self.top, text="Ilość:").grid(
            row=1, column=0, padx=8, pady=8, sticky="e"
        )
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

        logger.debug("[WM-DBG][MAG][ORDER] zapis pozycji %s", self.var_id.get())
        if not add_item_to_orders(
            self.var_id.get(), qty, comment="Magazyn - dialog"
        ):
            messagebox.showerror(
                "Błąd", "Nie udało się zapisać zamówienia do pliku oczekujących."
            )
            return
        if callable(self.on_saved):
            self.on_saved()
        self.top.destroy()


def open_pending_orders_window(parent=None):
    """Proste okno listy oczekujących zamówień z Magazynu."""

    top = tk.Toplevel(parent)
    apply_theme(top)
    top.title("Zamówienia oczekujące")
    top.geometry("600x320")
    top.minsize(480, 240)

    frame = ttk.Frame(top)
    frame.pack(fill="both", expand=True, padx=8, pady=8)

    tree = ttk.Treeview(
        frame,
        columns=("id", "qty", "comment", "ts"),
        show="headings",
        selectmode="browse",
    )
    tree.heading("id", text="ID")
    tree.heading("qty", text="Ilość")
    tree.heading("comment", text="Komentarz")
    tree.heading("ts", text="Dodano")
    tree.column("id", width=120, anchor="w")
    tree.column("qty", width=100, anchor="center")
    tree.column("comment", width=220, anchor="w")
    tree.column("ts", width=160, anchor="w")

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, side="left")

    for row in load_pending_orders():
        qty = row.get("qty")
        qty_txt = "" if qty is None else f"{qty:g}"
        tree.insert(
            "",
            "end",
            values=(
                row.get("id", ""),
                qty_txt,
                row.get("comment", ""),
                row.get("ts", ""),
            ),
        )

    ttk.Button(top, text="Zamknij", command=top.destroy).pack(pady=(4, 8))
