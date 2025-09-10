"""Helpers for recording goods receipts (PZ) in the warehouse GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager
from services.profile_service import authenticate
import logika_magazyn as LM
import magazyn_io

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


def open_window(parent: tk.Widget) -> None:
    """Open dialog for registering a goods receipt (PZ)."""

    win = tk.Toplevel(parent)
    apply_theme(win)
    win.title("Przyjęcie (PZ)")
    win.resizable(False, False)

    vars_ = {
        "id": tk.StringVar(),
        "qty": tk.StringVar(),
        "comment": tk.StringVar(),
    }

    frm = ttk.Frame(win, padding=12, style="WM.TFrame")
    frm.grid(row=0, column=0, sticky="nsew")
    win.columnconfigure(0, weight=1)

    for r, (lbl, key) in enumerate([
        ("ID", "id"),
        ("Ilość", "qty"),
        ("Komentarz", "comment"),
    ]):
        ttk.Label(frm, text=f"{lbl}:", style="WM.TLabel").grid(
            row=r, column=0, sticky="w", pady=2
        )
        ttk.Entry(frm, textvariable=vars_[key]).grid(
            row=r, column=1, sticky="ew", pady=2
        )
    frm.columnconfigure(1, weight=1)

    btns = ttk.Frame(win, style="WM.TFrame")
    btns.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="e")

    def on_cancel() -> None:
        win.destroy()

    def on_save() -> None:
        user_login = getattr(parent.winfo_toplevel(), "login", "")
        if _CFG.get("magazyn.require_reauth", True):
            login = simpledialog.askstring("Re-autoryzacja", "Login:", parent=win)
            if login is None:
                return
            pin = simpledialog.askstring(
                "Re-autoryzacja", "PIN:", show="*", parent=win
            )
            if pin is None:
                return
            user = authenticate(login, pin)
            if not user:
                messagebox.showerror(
                    "Błąd", "Nieprawidłowy login lub PIN", parent=win
                )
                return
            user_login = user.get("login", login)

        item_id = vars_["id"].get().strip()
        try:
            qty = float(vars_["qty"].get())
            if qty <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror(
                "Błąd", "Ilość musi być dodatnią liczbą", parent=win
            )
            return
        comment = vars_["comment"].get().strip()

        try:
            record_pz(item_id, qty, user_login, comment)
        except Exception as e:  # pragma: no cover - błędy trudne do odwzorowania
            messagebox.showerror("Błąd", str(e), parent=win)
            return

        win.destroy()

    ttk.Button(
        btns, text="Zapisz", command=on_save, style="WM.Side.TButton"
    ).pack(side="right", padx=(8, 0))
    ttk.Button(
        btns, text="Anuluj", command=on_cancel, style="WM.Side.TButton"
    ).pack(side="right")

    win.transient(parent)
    win.grab_set()
    win.wait_window(win)

