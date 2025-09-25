"""Panel zleceń – prosta lista z obsługą kreatora i szczegółów."""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from config.paths import join_path
from zlecenia_utils import load_orders

try:  # pragma: no cover - środowiska testowe nie wymagają motywu
    from gui_zlecenia_creator import open_order_creator  # type: ignore
except Exception:  # pragma: no cover - fallback gdy kreator niedostępny
    open_order_creator = None  # type: ignore

try:  # pragma: no cover - opcjonalny moduł szczegółów
    from gui_zlecenia_detail import open_order_detail  # type: ignore
except Exception:  # pragma: no cover - fallback gdy moduł nie istnieje
    open_order_detail = None  # type: ignore


def panel_zlecenia(parent: tk.Widget) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=8)
    frame.pack(fill="both", expand=True)

    toolbar = ttk.Frame(frame)
    toolbar.pack(fill="x", pady=(0, 6))

    btn_add = ttk.Button(toolbar, text="Dodaj zlecenie (Kreator)")
    if open_order_creator:
        btn_add.configure(command=lambda: open_order_creator(frame, "uzytkownik"))
    else:
        btn_add.state(["disabled"])
    btn_add.pack(side="left")

    columns = ("rodzaj", "status", "opis")
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    for column in columns:
        tree.heading(column, text=column.capitalize())
        tree.column(column, anchor="center")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for item in tree.get_children():
            tree.delete(item)
        for order in load_orders():
            tree.insert(
                "",
                "end",
                values=(order.get("rodzaj"), order.get("status"), order.get("opis")),
                iid=str(order.get("id")),
            )

    _refresh()

    def _on_double_click(event: Any) -> None:
        if not open_order_detail:
            return
        selection = tree.selection()
        if not selection:
            return
        order_id = selection[0]
        path = join_path("paths.orders_dir", f"{order_id}.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                order_data = json.load(handle)
        except Exception:
            return
        open_order_detail(frame, order_data)

    tree.bind("<Double-1>", _on_double_click)

    def _auto_refresh() -> None:
        if not frame.winfo_exists():
            return
        _refresh()
        frame.after(5000, _auto_refresh)

    _auto_refresh()
    return frame
