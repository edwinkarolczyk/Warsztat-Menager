# Plik: gui_magazyn_edit.py
# Wersja: 1.0.1
# - FIX: bezpieczny zapis (_safe_save) – fallback do logika_magazyn.save_magazyn,
#        jeśli magazyn_io.save nie istnieje.
# - Bez zmian w strukturze danych. Edytuje tylko: item["rozmiar"], item["zadania"].

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM


def _safe_load():
    """Czyta magazyn: preferuj magazyn_io.load(),
    fallback do LM.load_magazyn().
    """
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            return magazyn_io.load()
        return LM.load_magazyn()
    except Exception:
        return {"items": {}, "meta": {}}


def _safe_save(data: dict):
    """Zapis magazynu: magazyn_io.save() jeśli istnieje,
    inaczej LM.save_magazyn().
    """
    if HAVE_MAG_IO and hasattr(magazyn_io, "save"):
        return magazyn_io.save(data)
    if hasattr(LM, "save_magazyn"):
        return LM.save_magazyn(data)
    raise RuntimeError(
        "Brak implementacji zapisu magazynu "
        "(magazyn_io.save ani logika_magazyn.save_magazyn)"
    )


class MagazynEditDialog:
    def __init__(self, master, item_id, on_saved=None):
        self.master = master
        self.item_id = item_id
        self.on_saved = on_saved

        self.data = _safe_load()
        self.items = self.data.setdefault("items", {})
        self.item = self.items.get(item_id, {})

        self.win = tk.Toplevel(master)
        self.win.title(f"Edycja pozycji: {item_id}")
        self.win.resizable(False, False)

        frm = ttk.Frame(self.win, padding=12)
        frm.grid(sticky="nsew")
        self.win.columnconfigure(0, weight=1)

        # --- Pola ---
        ttk.Label(frm, text="Rozmiar:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.var_roz = tk.StringVar(
            value=str(self.item.get("rozmiar", ""))
        )
        ttk.Entry(frm, textvariable=self.var_roz, width=42).grid(
            row=0, column=1, sticky="ew", pady=2
        )

        ttk.Label(frm, text="Zadania tech. (oddziel przecinkami):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        zad = self.item.get("zadania", [])
        if isinstance(zad, list):
            zadania_txt = ", ".join(
                str(z).strip() for z in zad if str(z).strip()
            )
        else:
            zadania_txt = str(zad or "")
        self.var_zad = tk.StringVar(value=zadania_txt)
        ttk.Entry(frm, textvariable=self.var_zad, width=42).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        # --- Przyciski ---
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right")

        frm.columnconfigure(1, weight=1)

        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def on_save(self):
        rozmiar = self.var_roz.get().strip()
        zadania_raw = self.var_zad.get().strip()
        zadania = (
            [z.strip() for z in zadania_raw.split(",")]
            if zadania_raw
            else []
        )
        zadania = [z for z in zadania if z]

        # aktualizacja rekordu (tylko te dwa pola)
        self.item["rozmiar"] = rozmiar
        self.item["zadania"] = zadania

        try:
            _safe_save(self.data)
        except Exception as e:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie udało się zapisać magazynu:\n{e}",
                parent=self.win,
            )
            return

        if callable(self.on_saved):
            try:
                self.on_saved(self.item_id)
            except Exception:
                pass

        self.win.destroy()


def open_edit_dialog(master, item_id, on_saved=None):
    MagazynEditDialog(master, item_id, on_saved)
# ⏹ KONIEC KODU

