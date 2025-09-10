"""Helpers and dialog for recording goods receipts (PZ) in the GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager
from services.profile_service import authenticate
import logika_magazyn as LM
import magazyn_io
from logger import log_akcja

_CFG = ConfigManager()


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
    """Dialog for registering goods receipts (PZ)."""

    def __init__(
        self,
        parent: tk.Misc,
        *_args,
        preselect_id: str | None = None,
        on_saved: callable | None = None,
        **_kwargs,
    ) -> None:
        self._parent = parent
        self._on_saved = on_saved

        self._vars = {
            "id": tk.StringVar(value=preselect_id or ""),
            "qty": tk.StringVar(),
            "comment": tk.StringVar(),
        }

        win = self.win = tk.Toplevel(parent)
        self.top = self.win
        apply_theme(win)
        win.title("Przyjęcie towaru (PZ)")
        win.resizable(False, False)

        frm = ttk.Frame(win, padding=12, style="WM.TFrame")
        frm.grid(row=0, column=0, sticky="nsew")
        win.columnconfigure(0, weight=1)

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

        btns = ttk.Frame(win, style="WM.TFrame")
        btns.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="e")

        ttk.Button(
            btns, text="Zapisz", command=self._submit, style="WM.Side.TButton"
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            btns, text="Anuluj", command=self._cancel, style="WM.Side.TButton"
        ).pack(side="right")

        win.transient(parent)
        win.grab_set()

    def _cancel(self) -> None:
        self.win.destroy()

    def _submit(self) -> None:
        iid = self._vars["id"].get().strip()
        try:
            qty = float(self._vars["qty"].get())
        except ValueError:
            messagebox.showerror("Błąd", "Ilość musi być liczbą", parent=self.win)
            return

        if qty <= 0 or not iid:
            messagebox.showerror(
                "Błąd", "Uzupełnij poprawnie wszystkie pola", parent=self.win
            )
            return

        user_login = getattr(self.win.winfo_toplevel(), "login", "")
        if _CFG.get("magazyn.require_reauth", True):
            login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=self.win)
            if login is None:
                return
            pin = simpledialog.askstring(
                "Re-autoryzacja", "PIN:", show="*", parent=self.win
            )
            if pin is None:
                return
            user = authenticate(login, pin)
            if not user:
                messagebox.showerror(
                    "Błąd", "Nieprawidłowy login lub PIN", parent=self.win
                )
                return
            user_login = user.get("login", login)

        comment = self._vars["comment"].get().strip()

        try:
            data = LM.load_magazyn()
            items = data.get("items") or {}
            if iid not in items:
                raise KeyError(f"Brak pozycji {iid} w magazynie")

            items[iid]["stan"] = float(items[iid].get("stan", 0)) + qty
            log_akcja("[WM-DBG] przed zapisem PZ")
            magazyn_io.append_history(
                items,
                iid,
                user=user_login,
                op="PZ",
                qty=qty,
                comment=comment,
            )
            LM.save_magazyn(data)
            log_akcja("[WM-DBG] po zapisie PZ")
        except Exception as exc:
            messagebox.showerror("Błąd", str(exc), parent=self.win)
            return

        if callable(self._on_saved):
            self._on_saved()

        self.win.destroy()


# ⏹ KONIEC KODU

