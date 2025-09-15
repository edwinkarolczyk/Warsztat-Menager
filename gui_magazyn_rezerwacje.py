# ===============================================
# Plik: gui_magazyn_rezerwacje.py
# ===============================================
# Wersja: 1.0.0
# Zmiany:
# - Nowe okno dialogowe do rezerwowania i zwalniania rezerwacji magazynowych.
# - Obsługa pól: item_id, ilość, komentarz, historia.
# - Integracja z magazyn_io / logika_magazyn.
# ===============================================

import tkinter as tk
from tkinter import messagebox, ttk

import magazyn_io
import logika_magazyn as LM


def open_rezerwuj_dialog(master, item_id):
    win = tk.Toplevel(master)
    win.title("Rezerwuj materiał")
    win.resizable(False, False)

    frm = ttk.Frame(win, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")

    ttk.Label(frm, text=f"Rezerwacja pozycji: {item_id}").grid(
        row=0, column=0, columnspan=2, pady=4
    )

    ttk.Label(frm, text="Ilość:").grid(row=1, column=0, sticky="w")
    var_qty = tk.StringVar()
    ttk.Entry(frm, textvariable=var_qty).grid(row=1, column=1, sticky="ew")

    ttk.Label(frm, text="Komentarz:").grid(row=2, column=0, sticky="w")
    var_comment = tk.StringVar()
    ttk.Entry(frm, textvariable=var_comment).grid(row=2, column=1, sticky="ew")

    def do_save():
        try:
            qty = float(var_qty.get())
        except ValueError:
            messagebox.showerror("Błąd", "Ilość musi być liczbą.", parent=win)
            return
        data = magazyn_io.load()
        items = data.get("items", {})
        it = items.get(item_id)
        if it is None:
            messagebox.showerror(
                "Błąd", "Nie znaleziono pozycji w magazynie.", parent=win
            )
            return
        it["rezerwacje"] = it.get("rezerwacje", 0) + qty
        LM.append_history(
            items, item_id, user="", op="REZERWUJ", qty=qty,
            comment=var_comment.get()
        )
        magazyn_io.save(data)
        win.destroy()

    ttk.Button(frm, text="OK", command=do_save).grid(row=3, column=0, pady=8)
    ttk.Button(frm, text="Anuluj", command=win.destroy).grid(row=3, column=1, pady=8)

    win.transient(master)
    win.grab_set()
    master.wait_window(win)


def open_zwolnij_rezerwacje_dialog(master, item_id):
    win = tk.Toplevel(master)
    win.title("Zwolnij rezerwację")
    win.resizable(False, False)

    frm = ttk.Frame(win, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")

    ttk.Label(frm, text=f"Zwolnienie pozycji: {item_id}").grid(
        row=0, column=0, columnspan=2, pady=4
    )

    ttk.Label(frm, text="Ilość:").grid(row=1, column=0, sticky="w")
    var_qty = tk.StringVar()
    ttk.Entry(frm, textvariable=var_qty).grid(row=1, column=1, sticky="ew")

    ttk.Label(frm, text="Komentarz:").grid(row=2, column=0, sticky="w")
    var_comment = tk.StringVar()
    ttk.Entry(frm, textvariable=var_comment).grid(row=2, column=1, sticky="ew")

    def do_save():
        try:
            qty = float(var_qty.get())
        except ValueError:
            messagebox.showerror("Błąd", "Ilość musi być liczbą.", parent=win)
            return
        data = magazyn_io.load()
        items = data.get("items", {})
        it = items.get(item_id)
        if it is None:
            messagebox.showerror(
                "Błąd", "Nie znaleziono pozycji w magazynie.", parent=win
            )
            return
        it["rezerwacje"] = max(0, it.get("rezerwacje", 0) - qty)
        LM.append_history(
            items, item_id, user="", op="ZWOLNIJ", qty=qty,
            comment=var_comment.get()
        )
        magazyn_io.save(data)
        win.destroy()

    ttk.Button(frm, text="OK", command=do_save).grid(row=3, column=0, pady=8)
    ttk.Button(frm, text="Anuluj", command=win.destroy).grid(row=3, column=1, pady=8)

    win.transient(master)
    win.grab_set()
    master.wait_window(win)
