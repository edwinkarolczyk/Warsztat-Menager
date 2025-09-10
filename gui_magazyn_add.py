# Plik: gui_magazyn_add.py
# Wersja pliku: 1.0.0
# Zmiany 1.0.0:
# - Dodano okno dodawania pozycji magazynowej.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager
from services.profile_service import authenticate
import magazyn_io
import logika_magazyn as LM

_CFG = ConfigManager()


def open_window(parent):
    """Otwórz okno dialogowe dodawania pozycji magazynowej."""
    win = tk.Toplevel(parent)
    apply_theme(win)
    win.title("Dodaj pozycję")
    win.resizable(False, False)

    vars_ = {
        "id": tk.StringVar(),
        "nazwa": tk.StringVar(),
        "typ": tk.StringVar(),
        "jm": tk.StringVar(),
        "stan": tk.StringVar(),
        "min": tk.StringVar(),
        "komentarz": tk.StringVar(),
    }

    frm = ttk.Frame(win, padding=12, style="WM.TFrame")
    frm.grid(row=0, column=0, sticky="nsew")
    win.columnconfigure(0, weight=1)

    for r, (lbl, key) in enumerate(
        [
            ("ID", "id"),
            ("Nazwa", "nazwa"),
            ("Typ", "typ"),
            ("J.m.", "jm"),
            ("Stan pocz.", "stan"),
            ("Minimum", "min"),
            ("Komentarz", "komentarz"),
        ]
    ):
        ttk.Label(frm, text=f"{lbl}:", style="WM.TLabel").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=vars_[key]).grid(row=r, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    btns = ttk.Frame(win, style="WM.TFrame")
    btns.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="e")

    def on_cancel():
        win.destroy()

    def on_save():
        user_login = getattr(parent.winfo_toplevel(), "login", "")
        if _CFG.get("magazyn.require_reauth", True):
            login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=win)
            if login is None:
                return
            pin = simpledialog.askstring("Re-autoryzacja", "PIN:", show="*", parent=win)
            if pin is None:
                return
            user = authenticate(login, pin)
            if not user:
                messagebox.showerror("Błąd", "Nieprawidłowy login lub PIN", parent=win)
                return
            user_login = user.get("login", login)

        try:
            stan = float(vars_["stan"].get() or 0)
            minimum = float(vars_["min"].get() or 0)
        except ValueError:
            messagebox.showerror("Błąd", "Stan i minimum muszą być liczbami", parent=win)
            return

        item_id = vars_["id"].get().strip()
        name = vars_["nazwa"].get().strip()
        typ = vars_["typ"].get().strip()
        jm = vars_["jm"].get().strip()
        comment = vars_["komentarz"].get().strip()

        if not all([item_id, name, typ, jm]):
            messagebox.showerror(
                "Błąd", "Wszystkie pola oprócz komentarza są wymagane", parent=win
            )
            return

        load = getattr(magazyn_io, "load", LM.load_magazyn)
        save = getattr(magazyn_io, "save", LM.save_magazyn)
        data = load()

        if item_id in data.get("items", {}):
            messagebox.showerror("Błąd", "ID już istnieje w magazynie", parent=win)
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
            "komentarz": comment,
            "progi_alertow_pct": [100.0],
        }
        data.setdefault("meta", {}).setdefault("order", []).append(item_id)

        magazyn_io.append_history(
            data["items"], item_id, user_login or "", "CREATE", stan, comment
        )

        print("[WM-DBG] przed zapisem")
        save(data)
        print("[WM-DBG] po zapisie")

        win.destroy()

    ttk.Button(btns, text="Zapisz", command=on_save, style="WM.Side.TButton").pack(
        side="right", padx=(8, 0)
    )
    ttk.Button(btns, text="Anuluj", command=on_cancel, style="WM.Side.TButton").pack(side="right")

    win.transient(parent)
    win.grab_set()
    win.wait_window(win)


# ⏹ KONIEC KODU
