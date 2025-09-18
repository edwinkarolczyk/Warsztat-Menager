"""Okno szczegółów zlecenia."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from zlecenia_utils import save_order, statuses_for

try:  # pragma: no cover - motyw nie jest krytyczny podczas testów
    from ui_theme import apply_theme_safe as apply_theme  # type: ignore
except Exception:  # pragma: no cover - fallback gdy motyw nie istnieje
    def apply_theme(widget):  # type: ignore
        return None


def open_order_detail(master: tk.Widget, order: dict[str, Any]) -> tk.Toplevel:
    window = tk.Toplevel(master)
    window.title(f"Szczegóły {order.get('id', '')}")
    window.geometry("600x400")
    apply_theme(window)

    frame = ttk.Frame(window, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text=f"ID: {order.get('id', '–')}  | Rodzaj: {order.get('rodzaj', '–')}",
        style="WM.H1.TLabel",
    ).pack(anchor="w")
    ttk.Label(frame, text=f"Status: {order.get('status', '–')}").pack(anchor="w", pady=(0, 8))

    if order.get("rodzaj") == "ZW":
        produkt = order.get("produkt", "–")
        ilosc = order.get("ilosc", "–")
        ttk.Label(frame, text=f"Produkt: {produkt}  Ilość: {ilosc}").pack(anchor="w")
        zap = order.get("zapotrzebowanie") or {}
        if zap:
            ttk.Label(frame, text="Zapotrzebowanie:").pack(anchor="w")
            for kod, qty in zap.items():
                ttk.Label(frame, text=f" - {kod}: {qty}").pack(anchor="w")
    elif order.get("rodzaj") == "ZN":
        ttk.Label(frame, text=f"Narzędzie: {order.get('narzedzie_id', '–')}").pack(anchor="w")
        ttk.Label(frame, text=f"Komentarz: {order.get('komentarz', '')}").pack(anchor="w")
    elif order.get("rodzaj") == "ZM":
        ttk.Label(frame, text=f"Maszyna: {order.get('maszyna_id', '–')}").pack(anchor="w")
        ttk.Label(frame, text=f"Awaria: {order.get('awaria', '')}").pack(anchor="w")
        ttk.Label(frame, text=f"Pilność: {order.get('pilnosc', '')}").pack(anchor="w")

    ttk.Label(frame, text="Historia:").pack(anchor="w", pady=(12, 0))
    historia = order.get("historia", []) or []
    if not historia:
        ttk.Label(frame, text="(brak wpisów)").pack(anchor="w")
    else:
        for entry in historia:
            ts = entry.get("ts", "")
            kto = entry.get("kto", "")
            operacja = entry.get("operacja", "")
            szczegoly = entry.get("szczegoly", "")
            ttk.Label(
                frame,
                text=f"{ts} | {kto} | {operacja} {szczegoly}",
            ).pack(anchor="w")

    ttk.Label(frame, text="Zmień status:").pack(anchor="w", pady=(12, 0))
    statuses = statuses_for(order.get("rodzaj", ""))
    cb_status = ttk.Combobox(frame, values=statuses, state="readonly")
    if statuses:
        cb_status.set(order.get("status", statuses[0]))
    cb_status.pack(anchor="w")

    def _change_status() -> None:
        new_status = cb_status.get()
        if not new_status:
            window.destroy()
            return
        order["status"] = new_status
        try:
            save_order(order)
        finally:
            window.destroy()

    ttk.Button(frame, text="Zapisz status", command=_change_status).pack(anchor="w", pady=(8, 0))

    window.transient(master.winfo_toplevel())
    window.grab_set()
    return window
