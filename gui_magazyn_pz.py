# Wersja pliku: 1.0.0
# Moduł: gui_magazyn_pz
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from services.profile_service import authenticate

import magazyn_io


def open_window(parent: tk.Widget, item_id: str) -> None:
    """Dialog przyjęcia magazynowego (PZ) dla ``item_id``."""

    data = magazyn_io.load()
    item = (data.get("items") or {}).get(item_id, {})
    name = item.get("nazwa", item_id)
    stan = float(item.get("stan", 0))

    win = tk.Toplevel(parent)
    win.title("Przyjęcie")

    tk.Label(win, text=name).grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(win, text=f"Stan: {stan}").grid(row=1, column=0, columnspan=2, sticky="w")

    tk.Label(win, text="Ilość").grid(row=2, column=0, sticky="e")
    entry_qty = tk.Entry(win)
    entry_qty.grid(row=2, column=1, padx=5, pady=2)

    tk.Label(win, text="Komentarz").grid(row=3, column=0, sticky="e")
    entry_com = tk.Entry(win)
    entry_com.grid(row=3, column=1, padx=5, pady=2)

    def _save() -> None:
        login = simpledialog.askstring("Autoryzacja", "Login:", parent=win)
        if login is None:
            return
        pin = simpledialog.askstring("Autoryzacja", "PIN:", parent=win, show="*")
        if pin is None:
            return
        user = authenticate(login.strip().lower(), pin.strip())
        if not user:
            messagebox.showerror("Błąd", "Błędne dane logowania")
            return

        try:
            qty = float(entry_qty.get())
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Błąd", "Nieprawidłowa ilość")
            return

        comment = entry_com.get().strip()
        magazyn = magazyn_io.load()
        items = magazyn.setdefault("items", {})
        record = items.setdefault(item_id, {})
        record["nazwa"] = record.get("nazwa", name)
        record["stan"] = float(record.get("stan", 0)) + qty
        magazyn_io.save(magazyn)
        magazyn_io.append_history(items, item_id, login, "PZ", qty, comment)
        print(f"[WM-DBG] PZ {item_id} +{qty} by {login}")
        win.destroy()

    def _cancel() -> None:
        win.destroy()

    tk.Button(win, text="Zapisz", command=_save).grid(row=4, column=0, pady=5)
    tk.Button(win, text="Anuluj", command=_cancel).grid(row=4, column=1, pady=5)

    win.transient(parent)
    win.grab_set()
    parent.wait_window(win)


# ⏹ KONIEC KODU

