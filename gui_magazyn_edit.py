# Plik: gui_magazyn_edit.py
# Wersja: 1.0.0
# - Nowy dialog edycji pozycji magazynowej
# - Pola: rozmiar (string), zadania (lista, rozdzielana przecinkami)

import tkinter as tk
from tkinter import ttk, messagebox
import magazyn_io
import logika_magazyn as LM


class MagazynEditDialog:
    def __init__(self, master, item_id, on_saved=None):
        self.master = master
        self.item_id = item_id
        self.on_saved = on_saved

        self.data = LM.load_magazyn()
        self.item = self.data.get("items", {}).get(item_id, {})

        self.win = tk.Toplevel(master)
        self.win.title(f"Edycja pozycji {item_id}")
        self.win.resizable(False, False)

        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)

        # Rozmiar
        ttk.Label(frm, text="Rozmiar:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.var_roz = tk.StringVar(value=self.item.get("rozmiar", ""))
        ttk.Entry(
            frm, textvariable=self.var_roz, width=40
        ).grid(row=0, column=1, sticky="ew", pady=2)

        # Zadania
        ttk.Label(
            frm,
            text="Zadania tech. (rozdziel przecinkami):",
        ).grid(row=1, column=0, sticky="w", pady=2)

        zadania_raw = self.item.get("zadania")
        if isinstance(zadania_raw, list):
            zadania_txt = ", ".join(zadania_raw)
        else:
            zadania_txt = str(zadania_raw or "")

        self.var_zad = tk.StringVar(value=zadania_txt)
        ttk.Entry(frm, textvariable=self.var_zad, width=40).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        # Przyciski
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(
            btns, text="Zapisz", command=self.on_save
        ).pack(side="right", padx=5)
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(
            side="right"
        )

        frm.columnconfigure(1, weight=1)
        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def on_save(self):
        rozmiar = self.var_roz.get().strip()
        zadania_raw = self.var_zad.get().strip()
        zadania = (
            [z.strip() for z in zadania_raw.split(",") if z.strip()]
            if zadania_raw
            else []
        )

        self.item["rozmiar"] = rozmiar
        self.item["zadania"] = zadania

        magazyn_io.save(self.data)
        if self.on_saved:
            try:
                self.on_saved(self.item_id)
            except Exception:
                pass
        self.win.destroy()


def open_edit_dialog(master, item_id, on_saved=None):
    MagazynEditDialog(master, item_id, on_saved)
# ⏹ KONIEC KODU
