"""Helpers and dialog for recording goods receipts (PZ) in the GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import logging
import math

from ui_theme import apply_theme_safe as apply_theme
from services.profile_service import authenticate
import logika_magazyn as LM
import magazyn_io

try:  # pragma: no cover - logger optional
    import logger

    _log_mag = getattr(
        logger, "log_magazyn", lambda a, d: logging.info(f"[MAGAZYN] {a}: {d}")
    )
except Exception:  # pragma: no cover - logger fallback
    def _log_mag(akcja, dane):
        logging.info(f"[MAGAZYN] {akcja}: {dane}")


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
        msg = f"Brak pozycji {item_id} w magazynie"
        logging.error(msg)
        raise KeyError(msg)

    qty_f = float(qty)
    jm = items[item_id].get("jednostka", "")
    if jm.lower() == "szt" and not float(qty_f).is_integer():
        choice = messagebox.askyesnocancel(
            "Zaokrąglanie",
            f"Ilość {qty_f} szt jest ułamkowa. Zaokrąglić w górę?",
        )
        if choice is None:
            logging.info("Anulowano PZ - zaokrąglanie ilości")
            return
        qty_f = float(math.ceil(qty_f) if choice else math.floor(qty_f))
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
    name = items[item_id].get("nazwa", item_id)
    jm = items[item_id].get("jednostka", "")
    _log_mag(
        "PZ",
        {
            "item_id": item_id,
            "nazwa": name,
            "qty": qty_f,
            "jm": jm,
            "by": user,
            "comment": comment,
        },
    )
    logging.info(
        "Zapisano PZ %s: %s, %s %s, wystawił: %s",
        item_id,
        name,
        qty_f,
        jm,
        user,
    )


class MagazynPZDialog:
    """Dialog for registering goods receipts (PZ)."""

    def __init__(
        self,
        master,
        config,
        profiles=None,
        preselect_id=None,
        on_saved=None,
    ):
        self.master = master
        self.config = config
        self.profiles = profiles
        self.preselect_id = preselect_id
        self.on_saved = on_saved

        self._vars = {
            "id": tk.StringVar(value=self.preselect_id or ""),
            "qty": tk.StringVar(),
            "comment": tk.StringVar(),
        }

        self.top = tk.Toplevel(master)
        apply_theme(self.top)
        self.top.title("Przyjęcie towaru (PZ)")
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=12, style="WM.TFrame")
        frm.grid(row=0, column=0, sticky="nsew")
        self.top.columnconfigure(0, weight=1)

        data = LM.load_magazyn()
        items = data.get("items") or {}
        ids = sorted(items.keys())

        ttk.Label(frm, text="Pozycja:", style="WM.TLabel").grid(
            row=0, column=0, sticky="w", pady=2
        )
        ttk.Combobox(
            frm,
            textvariable=self._vars["id"],
            values=ids,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Ilość:", style="WM.TLabel").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Entry(frm, textvariable=self._vars["qty"]).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        ttk.Label(frm, text="Komentarz:", style="WM.TLabel").grid(
            row=2, column=0, sticky="w", pady=2
        )
        ttk.Entry(frm, textvariable=self._vars["comment"]).grid(
            row=2, column=1, sticky="ew", pady=2
        )
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

    def _cancel(self) -> None:
        logging.info("Anulowano przyjęcie towaru (PZ)")
        self.top.destroy()

    def _submit(self) -> None:
        iid = self._vars["id"].get().strip()
        try:
            qty = float(self._vars["qty"].get())
        except ValueError:
            logging.error("Ilość musi być liczbą")
            messagebox.showerror("Błąd", "Ilość musi być liczbą", parent=self.top)
            return

        if qty <= 0 or not iid:
            logging.error("Uzupełnij poprawnie wszystkie pola")
            messagebox.showerror(
                "Błąd", "Uzupełnij poprawnie wszystkie pola", parent=self.top
            )
            return

        user_login = getattr(self.top.winfo_toplevel(), "login", "")
        if self.config.get("magazyn.require_reauth", True):
            login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=self.top)
            if login is None:
                logging.info("Przerwano re-autoryzację - brak loginu")
                return
            pin = simpledialog.askstring(
                "Re-autoryzacja", "PIN:", show="*", parent=self.top
            )
            if pin is None:
                logging.info("Przerwano re-autoryzację - brak PIN-u")
                return
            user = authenticate(login, pin)
            if not user:
                logging.error("Nieprawidłowy login lub PIN")
                messagebox.showerror(
                    "Błąd", "Nieprawidłowy login lub PIN", parent=self.top
                )
                return
            user_login = user.get("login", login)

        comment = self._vars["comment"].get().strip()

        try:
            data = LM.load_magazyn()
            items = data.get("items") or {}
            if iid not in items:
                raise KeyError(f"Brak pozycji {iid} w magazynie")
            jm = items[iid].get("jednostka", "")
            if jm.lower() == "szt" and not float(qty).is_integer():
                choice = messagebox.askyesnocancel(
                    "Zaokrąglanie",
                    f"Ilość {qty} szt jest ułamkowa. Zaokrąglić w górę?",
                    parent=self.top,
                )
                if choice is None:
                    logging.info("Anulowano PZ - zaokrąglanie ilości")
                    return
                qty = float(math.ceil(qty) if choice else math.floor(qty))

            items[iid]["stan"] = float(items[iid].get("stan", 0)) + qty
            magazyn_io.append_history(
                items,
                iid,
                user=user_login,
                op="PZ",
                qty=qty,
                comment=comment,
            )
            LM.save_magazyn(data)
            name = items[iid].get("nazwa", iid)
            jm = items[iid].get("jednostka", "")
            _log_mag(
                "PZ",
                {
                    "item_id": iid,
                    "nazwa": name,
                    "qty": qty,
                    "jm": jm,
                    "by": user_login,
                    "comment": comment,
                },
            )
            logging.info(
                "Zapisano PZ %s: %s, %s %s, wystawił: %s",
                iid,
                name,
                qty,
                jm,
                user_login,
            )
        except Exception as exc:
            logging.error("Błąd zapisu PZ: %s", exc)
            messagebox.showerror("Błąd", str(exc), parent=self.top)
            return

        if callable(self.on_saved):
            self.on_saved()

        self.top.destroy()


# ⏹ KONIEC KODU

