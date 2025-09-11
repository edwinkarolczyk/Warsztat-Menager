"""Helpers and dialog for recording goods receipts (PZ) in the GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import re

from ui_theme import apply_theme_safe as apply_theme
from services.profile_service import authenticate
import logika_magazyn as LM
import magazyn_io


def record_pz(item_id: str, qty: float, user: str, comment: str = "") -> None:
    """Register a goods receipt for ``item_id``.

    Parameters
    ----------
    item_id:
        Identifier of the item in the warehouse.
    qty:
        Received quantity (positive).
    user:
        Login of the user performing the operation.
    comment:
        Optional free-form comment.
    """

    data = LM.load_magazyn()
    items = data.get("items") or {}
    if item_id not in items:
        raise KeyError(f"Brak pozycji {item_id} w magazynie")

    qty_f = float(qty)
    items[item_id]["stan"] = float(items[item_id].get("stan", 0)) + qty_f

    magazyn_io.append_history(
        items,
        item_id,
        user=user,
        op="PZ",
        qty=qty_f,
        comment=comment,
    )
    LM.save_magazyn(data)


class MagazynPZDialog:
    """Dialog do rejestrowania przyjęć (PZ) nowych materiałów."""

    _KAT_VALUES = ["Profil", "Rura", "Półprodukt"]
    _JM_VALUES = ["mb", "szt"]
    _MAT_VALUES = ["S235", "S355", "Inny"]

    def __init__(
        self,
        master,
        config,
        profiles=None,
        preselect_id=None,  # zachowane dla zgodności
        on_saved=None,
    ):
        self.master = master
        self.config = config
        self.profiles = profiles
        self.on_saved = on_saved

        self.vars = {
            "kategoria": tk.StringVar(value=self._KAT_VALUES[0]),
            "typ_materialu": tk.StringVar(),
            "jm": tk.StringVar(),
            "qty": tk.StringVar(),
            "rodzaj_profilu": tk.StringVar(),
            "wymiar": tk.StringVar(),
            "fi": tk.StringVar(),
            "grubosc_scianki": tk.StringVar(),
            "nazwa": tk.StringVar(),
        }

        self.top = tk.Toplevel(master)
        apply_theme(self.top)
        self.top.title("Przyjęcie towaru (PZ)")
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=12, style="WM.TFrame")
        frm.grid(row=0, column=0, sticky="nsew")
        self.top.columnconfigure(0, weight=1)

        ttk.Label(frm, text="Kategoria:", style="WM.TLabel").grid(
            row=0, column=0, sticky="w", pady=2
        )
        cb_kat = ttk.Combobox(
            frm,
            textvariable=self.vars["kategoria"],
            values=self._KAT_VALUES,
            state="readonly",
        )
        cb_kat.grid(row=0, column=1, sticky="ew", pady=2)
        cb_kat.bind("<<ComboboxSelected>>", lambda _e: self._on_cat_change())

        ttk.Label(frm, text="Typ materiału:", style="WM.TLabel").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Combobox(
            frm,
            textvariable=self.vars["typ_materialu"],
            values=self._MAT_VALUES,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="J.m.:", style="WM.TLabel").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.cb_jm = ttk.Combobox(
            frm,
            textvariable=self.vars["jm"],
            values=self._JM_VALUES,
            state="readonly",
        )
        self.cb_jm.grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Ilość:", style="WM.TLabel").grid(
            row=3, column=0, sticky="w", pady=2
        )
        ttk.Entry(frm, textvariable=self.vars["qty"]).grid(
            row=3, column=1, sticky="ew", pady=2
        )

        self.frm_cat = ttk.Frame(frm, style="WM.TFrame")
        self.frm_cat.grid(row=4, column=0, columnspan=2, sticky="ew")

        frm.columnconfigure(1, weight=1)

        btns = ttk.Frame(self.top, style="WM.TFrame")
        btns.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="e")
        ttk.Button(
            btns, text="Zapisz", command=self._submit, style="WM.Side.TButton"
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            btns, text="Anuluj", command=self._cancel, style="WM.Side.TButton"
        ).pack(side="right")

        self.top.transient(master)
        self.top.grab_set()

        self._on_cat_change()

    # ------------------------------------------------------------------
    def _on_cat_change(self) -> None:
        cat = self.vars["kategoria"].get()
        self.vars["jm"].set("mb" if cat in ("Profil", "Rura") else "szt")
        for child in self.frm_cat.winfo_children():
            child.destroy()
        if cat == "Profil":
            ttk.Label(self.frm_cat, text="Rodzaj profilu:", style="WM.TLabel").grid(
                row=0, column=0, sticky="w", pady=2
            )
            ttk.Entry(
                self.frm_cat, textvariable=self.vars["rodzaj_profilu"]
            ).grid(row=0, column=1, sticky="ew", pady=2)
            ttk.Label(self.frm_cat, text="Wymiar:", style="WM.TLabel").grid(
                row=1, column=0, sticky="w", pady=2
            )
            ttk.Entry(
                self.frm_cat, textvariable=self.vars["wymiar"]
            ).grid(row=1, column=1, sticky="ew", pady=2)
        elif cat == "Rura":
            ttk.Label(self.frm_cat, text="Fi:", style="WM.TLabel").grid(
                row=0, column=0, sticky="w", pady=2
            )
            ttk.Entry(self.frm_cat, textvariable=self.vars["fi"]).grid(
                row=0, column=1, sticky="ew", pady=2
            )
            ttk.Label(
                self.frm_cat, text="Grubość ścianki:", style="WM.TLabel"
            ).grid(row=1, column=0, sticky="w", pady=2)
            ttk.Entry(
                self.frm_cat, textvariable=self.vars["grubosc_scianki"]
            ).grid(row=1, column=1, sticky="ew", pady=2)
        else:  # Półprodukt
            ttk.Label(self.frm_cat, text="Nazwa:", style="WM.TLabel").grid(
                row=0, column=0, sticky="w", pady=2
            )
            ttk.Entry(self.frm_cat, textvariable=self.vars["nazwa"]).grid(
                row=0, column=1, sticky="ew", pady=2
            )
        self.frm_cat.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    def _cancel(self) -> None:
        self.top.destroy()

    # ------------------------------------------------------------------
    def _generate_name_code(self) -> tuple[str, str]:
        cat = self.vars["kategoria"].get()
        typ = self.vars["typ_materialu"].get().strip()
        if cat == "Profil":
            rodzaj = self.vars["rodzaj_profilu"].get().strip()
            wymiar = self.vars["wymiar"].get().strip()
            nazwa = f"Profil {rodzaj} {wymiar} {typ}".strip()
        elif cat == "Rura":
            fi = self.vars["fi"].get().strip()
            scianka = self.vars["grubosc_scianki"].get().strip()
            dop = f"x{scianka}" if scianka else ""
            nazwa = f"Rura fi{fi}{dop} {typ}".strip()
        else:
            nazwa = self.vars["nazwa"].get().strip()
        kod = LM.peek_next_material_id("materiał") or "PZ-0001"
        return kod, nazwa

    # ------------------------------------------------------------------
    def _submit(self) -> None:
        cat = self.vars["kategoria"].get()
        typ = self.vars["typ_materialu"].get().strip()
        jm = self.vars["jm"].get().strip()

        try:
            qty = float(self.vars["qty"].get())
        except ValueError:
            messagebox.showerror("Błąd", "Ilość musi być liczbą", parent=self.top)
            return

        if qty <= 0 or not typ:
            messagebox.showerror(
                "Błąd", "Uzupełnij poprawnie wszystkie pola", parent=self.top
            )
            return

        if cat == "Profil":
            rodzaj = self.vars["rodzaj_profilu"].get().strip()
            wymiar = self.vars["wymiar"].get().strip()
            if not rodzaj or not wymiar:
                messagebox.showerror(
                    "Błąd", "Wypełnij dane profilu", parent=self.top
                )
                return
            if not re.fullmatch(r"\d{1,4}x\d{1,4}x\d{1,3}", wymiar):
                messagebox.showerror(
                    "Błąd",
                    "Wymiar musi mieć format np. 100x50x5",
                    parent=self.top,
                )
                return
        elif cat == "Rura":
            fi = self.vars["fi"].get().strip()
            if not fi:
                messagebox.showerror(
                    "Błąd", "Podaj średnicę rury", parent=self.top
                )
                return
        else:  # Półprodukt
            nazwa = self.vars["nazwa"].get().strip()
            if not nazwa:
                messagebox.showerror(
                    "Błąd", "Podaj nazwę półproduktu", parent=self.top
                )
                return

        if jm == "mb":
            qty = round(qty, 3)
        elif jm == "szt":
            qty_int = int(round(qty))
            if abs(qty_int - qty) > 1e-9:
                if not messagebox.askyesno(
                    "Zaokrąglenie",
                    f"Zaokrąglić ilość do {qty_int} szt?",
                    parent=self.top,
                ):
                    return
            qty = qty_int

        kod, nazwa = self._generate_name_code()

        user_login = getattr(self.top.winfo_toplevel(), "login", "")
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

        record = {
            "kod": kod,
            "nazwa": nazwa,
            "kategoria": cat,
            "typ_materialu": typ,
            "jm": jm,
            "ilosc": qty,
            "user": user_login,
        }
        if cat == "Profil":
            record["rodzaj_profilu"] = self.vars["rodzaj_profilu"].get().strip()
            record["wymiar"] = self.vars["wymiar"].get().strip()
        elif cat == "Rura":
            record["fi"] = self.vars["fi"].get().strip()
            scianka = self.vars["grubosc_scianki"].get().strip()
            if scianka:
                record["grubosc_scianki"] = scianka

        try:
            pz_id = magazyn_io.save_pz(record)

            data = LM.load_magazyn()
            items = data.setdefault("items", {})
            item = items.get(kod)
            if not item:
                items[kod] = {
                    "id": kod,
                    "nazwa": nazwa,
                    "typ": "półprodukt" if cat == "Półprodukt" else "materiał",
                    "jednostka": jm,
                    "stan": 0,
                    "min_poziom": 0,
                    "rezerwacje": 0,
                    "historia": [],
                    "komentarz": "",
                    "progi_alertow_pct": [100.0],
                }
                LM.bump_material_seq_if_matches(kod)
                item = items[kod]

            item["stan"] = float(item.get("stan", 0)) + qty
            magazyn_io.append_history(
                items,
                kod,
                user=user_login,
                op="PZ",
                qty=qty,
                comment="",
                write_pz=False,
            )
            LM.save_magazyn(data)
        except Exception as exc:
            messagebox.showerror("Błąd", str(exc), parent=self.top)
            return

        messagebox.showinfo(
            "Zapisano",
            f"Przyjęcie zapisane jako {pz_id}",
            parent=self.top,
        )
        if callable(self.on_saved):
            self.on_saved()
        self.top.destroy()


# ⏹ KONIEC KODU

