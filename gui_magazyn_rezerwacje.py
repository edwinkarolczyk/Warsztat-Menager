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
import config_manager as cfg


def _parse_qty(s: str) -> float:
    try:
        v = float(str(s).replace(",", "."))
        return v
    except Exception:
        return float("nan")


def _validate_and_reserve(var_qty, cel_typ, item_dict):
    qty = _parse_qty(var_qty)
    if not (qty > 0):
        messagebox.showerror("Błąd", "Ilość musi być dodatnia.")
        return False, None

    stan = float(item_dict.get("stan", 0) or 0)
    rez = float(item_dict.get("rezerwacje", 0) or 0)
    if qty > max(0.0, stan - rez):
        messagebox.showerror(
            "Błąd", "Brak wystarczającej dostępności do rezerwacji."
        )
        return False, None

    enforce = cfg.get("magazyn.enforce_surowiec_to_polprodukt", True)
    if enforce:
        typ = (item_dict.get("typ") or "").strip().lower()
        cel_typ = (cel_typ or "").strip().lower()
        if typ == "surowiec" and cel_typ != "półprodukt":
            messagebox.showerror(
                "Błąd", "Surowiec może być rezerwowany wyłącznie do półproduktu."
            )
            return False, None

    return True, qty


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

    var_cel_typ = tk.StringVar(value="półprodukt")
    ttk.Label(frm, text="Cel rezerwacji:").grid(row=2, column=0, sticky="w")
    ttk.Combobox(
        frm,
        textvariable=var_cel_typ,
        values=["półprodukt", "produkt"],
        state="readonly",
    ).grid(row=2, column=1, sticky="ew")

    ttk.Label(frm, text="Komentarz:").grid(row=3, column=0, sticky="w")
    var_comment = tk.StringVar()
    ttk.Entry(frm, textvariable=var_comment).grid(row=3, column=1, sticky="ew")

    def do_save():
        data = magazyn_io.load()
        items = data.get("items", {})
        it = items.get(item_id)
        if it is None:
            messagebox.showerror(
                "Błąd", "Nie znaleziono pozycji w magazynie.", parent=win
            )
            return
        ok, qty = _validate_and_reserve(var_qty.get(), var_cel_typ.get(), it)
        if not ok:
            return
        it["rezerwacje"] = it.get("rezerwacje", 0) + qty
        LM.append_history(
            items,
            item_id,
            user="",
            op="REZERWUJ",
            qty=qty,
            comment=var_comment.get(),
        )
        magazyn_io.save(data)
        win.destroy()

    ttk.Button(frm, text="OK", command=do_save).grid(row=4, column=0, pady=8)
    ttk.Button(frm, text="Anuluj", command=win.destroy).grid(row=4, column=1, pady=8)

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
        if qty <= 0:
            messagebox.showerror(
                "Błąd", "Ilość musi być większa od zera.", parent=win
            )
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
