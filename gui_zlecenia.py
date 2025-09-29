"""Panel zleceń – prosta lista z obsługą kreatora i szczegółów."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from config.paths import prefer_config_file
from domain.orders import (
    ensure_orders_dir,
    load_order,
    load_orders,
    order_path,
    save_order,
)
from utils.io_json import load_or_seed_json
from seeds import SEEDS

ORDERS_FILE = prefer_config_file("orders.file", "zlecenia/_seed.json")
_SEEDED_ORDERS = load_or_seed_json(ORDERS_FILE, SEEDS["zlecenia"])


def _ensure_seed_orders() -> None:
    ensure_orders_dir()
    existing = [
        name
        for name in os.listdir(ensure_orders_dir())
        if name.endswith(".json") and not name.startswith("_")
    ]
    if existing:
        return
    if not isinstance(_SEEDED_ORDERS, list):
        return
    for entry in _SEEDED_ORDERS:
        if not isinstance(entry, dict):
            continue
        order_id = str(entry.get("id") or "").strip()
        if not order_id:
            continue
        path = order_path(order_id)
        if os.path.exists(path):
            continue
        try:
            save_order(dict(entry))
        except Exception:
            continue


_ensure_seed_orders()

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
        try:
            order_data = load_order(order_id)
        except Exception:
            return
        if not order_data:
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
