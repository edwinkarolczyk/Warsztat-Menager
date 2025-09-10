"""Helpers and dialog for recording goods receipts (PZ) in the GUI."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager
from services.profile_service import authenticate
import logika_magazyn as LM
import magazyn_io

logger = logging.getLogger(__name__)


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

    logger.debug("[WM-DBG][MAGAZYN][PZ] saving")
    magazyn_io.append_history(
        items,
        item_id,
        user=user,
        op="PZ",
        qty=qty_f,
        comment=comment,
    )
    logger.debug("[WM-DBG][MAGAZYN][PZ] history updated")
    LM.save_magazyn(data)
    logger.debug("[WM-DBG][MAGAZYN][PZ] saved")


class MagazynPZDialog:
    """Dialog for registering goods receipts (PZ)."""

    def __init__(
        self,
        master: tk.Misc,
        config: ConfigManager,
        profiles: dict | None = None,
        preselect_id: str | None = None,
        on_saved: callable | None = None,
    ) -> None:
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
        self.top.destroy()

    def _submit(self) -> None:
        iid = self._vars["id"].get().strip()
        try:
            qty = float(self._vars["qty"].get())
        except ValueError:
            messagebox.showerror("Błąd", "Ilość musi być liczbą", parent=self.top)
            return

        if qty <= 0 or not iid:
            messagebox.showerror(
                "Błąd", "Uzupełnij poprawnie wszystkie pola", parent=self.top
            )
            return

        user_login = getattr(self.top.winfo_toplevel(), "login", "")
        if self.config.get("magazyn.require_reauth", True):
            login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=self.top)
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

        comment = self._vars["comment"].get().strip()

        try:
            data = LM.load_magazyn()
            items = data.get("items") or {}
            if iid not in items:
                raise KeyError(f"Brak pozycji {iid} w magazynie")

            items[iid]["stan"] = float(items[iid].get("stan", 0)) + qty
            logger.debug("[WM-DBG][MAGAZYN][PZ] saving")
            magazyn_io.append_history(
                items,
                iid,
                user=user_login,
                op="PZ",
                qty=qty,
                comment=comment,
            )
            logger.debug("[WM-DBG][MAGAZYN][PZ] history updated")
            LM.save_magazyn(data)
            logger.debug("[WM-DBG][MAGAZYN][PZ] saved")
        except Exception as exc:
            messagebox.showerror("Błąd", str(exc), parent=self.top)
            return

        if callable(self.on_saved):
            self.on_saved()

        self.top.destroy()


# ⏹ KONIEC KODU

