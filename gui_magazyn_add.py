# Plik: gui_magazyn_add.py
# Wersja pliku: 1.1.0
# Zmiany 1.1.0:
# - Przepisano okno na klasę ``MagazynAddDialog`` z opcjonalną re-autoryzacją
#   i callbackiem ``on_saved``.
#
# Zmiany 1.0.0:
# - Dodano okno dodawania pozycji magazynowej.

import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui_theme import apply_theme_safe as apply_theme
from services.profile_service import authenticate
import magazyn_io
import logika_magazyn as LM


class MagazynAddDialog:
    """Dialog umożliwiający dodanie nowej pozycji magazynowej."""

    def __init__(self, master, config, profiles=None, on_saved=None):
        self.master = master
        self.config = config
        self.profiles = profiles
        self.on_saved = on_saved

        gm = sys.modules.get("gui_magazyn")
        tk_mod = getattr(gm, "tk", tk) if gm else tk
        self.top = tk_mod.Toplevel(master)
        if hasattr(self.top, "title"):
            self.top.title("Dodaj pozycję")
        if not getattr(self.top, "tk", None):
            return
        apply_theme(self.top)
        self.top.resizable(False, False)

        self.vars = {
            "id": tk.StringVar(),
            "nazwa": tk.StringVar(),
            "typ": tk.StringVar(),
            "jednostka": tk.StringVar(),
            "stan": tk.StringVar(),
            "min_poziom": tk.StringVar(),
        }

        frm = ttk.Frame(self.top, padding=12, style="WM.TFrame")
        frm.grid(row=0, column=0, sticky="nsew")
        self.top.columnconfigure(0, weight=1)

        fields = [
            ("ID", "id"),
            ("Nazwa", "nazwa"),
            ("Typ", "typ"),
            ("J.m.", "jednostka"),
            ("Stan pocz.", "stan"),
            ("Minimum", "min_poziom"),
        ]

        for r, (lbl, key) in enumerate(fields):
            ttk.Label(frm, text=f"{lbl}:", style="WM.TLabel").grid(
                row=r, column=0, sticky="w", pady=2
            )
            ttk.Entry(frm, textvariable=self.vars[key]).grid(
                row=r, column=1, sticky="ew", pady=2
            )
        frm.columnconfigure(1, weight=1)

        btns = ttk.Frame(self.top, style="WM.TFrame")
        btns.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="e")

        ttk.Button(
            btns,
            text="Zapisz",
            command=self.on_save,
            style="WM.Side.TButton",
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            btns,
            text="Anuluj",
            command=self.on_cancel,
            style="WM.Side.TButton",
        ).pack(side="right")

        self.top.transient(master)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self.on_cancel)

    # ------------------------------------------------------------------
    def on_cancel(self):
        self.top.destroy()

    # ------------------------------------------------------------------
    def on_save(self):
        user_login = getattr(self.master.winfo_toplevel(), "login", "")
        if self.config.get("magazyn.require_reauth", True):
            login = simpledialog.askstring(
                "Re-autoryzacja", "Login:", parent=self.top
            )
            if login is None:
                return
            pin = simpledialog.askstring(
                "Re-autoryzacja", "PIN:", show="*", parent=self.top
            )
            if pin is None:
                return
            user = authenticate(login, pin)
            if not user:
                messagebox.showerror(
                    "Błąd", "Nieprawidłowy login lub PIN", parent=self.top
                )
                return
            user_login = user.get("login", login)

        try:
            stan = float(self.vars["stan"].get() or 0)
            minimum = float(self.vars["min_poziom"].get() or 0)
        except ValueError:
            messagebox.showerror(
                "Błąd", "Stan i minimum muszą być liczbami", parent=self.top
            )
            return

        item_id = self.vars["id"].get().strip()
        name = self.vars["nazwa"].get().strip()
        typ = self.vars["typ"].get().strip()
        jm = self.vars["jednostka"].get().strip()

        if not all([item_id, name, typ, jm]):
            messagebox.showerror(
                "Błąd", "Wszystkie pola są wymagane", parent=self.top
            )
            return

        load = getattr(magazyn_io, "load", LM.load_magazyn)
        save = getattr(magazyn_io, "save", LM.save_magazyn)
        data = load()

        if item_id in data.get("items", {}):
            messagebox.showerror(
                "Błąd", "ID już istnieje w magazynie", parent=self.top
            )
            return

        data.setdefault("items", {})[item_id] = {
            "id": item_id,
            "nazwa": name,
            "typ": typ,
            "jednostka": jm,
            "stan": stan,
            "min_poziom": minimum,
            "rezerwacje": 0,
            "historia": [],
            "komentarz": "",
            "progi_alertow_pct": [100.0],
        }
        data.setdefault("meta", {}).setdefault("order", []).append(item_id)

        LM.append_history(
            data["items"],
            item_id,
            user=user_login or "",
            op="CREATE",
            qty=stan,
            comment="",
        )

        print("[WM-DBG][MAGAZYN-ADD] saving")
        save(data)
        print("[WM-DBG][MAGAZYN-ADD] saved")

        if self.on_saved:
            try:
                self.on_saved(item_id)
            except TypeError:
                self.on_saved()

        self.top.destroy()


def open_window(parent, config, profiles=None, on_saved=None):
    """Zachowana dla kompatybilności funkcja otwierająca dialog."""
    return MagazynAddDialog(parent, config, profiles, on_saved=on_saved)


# ⏹ KONIEC KODU
