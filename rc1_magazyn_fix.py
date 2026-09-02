# version: 1.2
# -*- coding: utf-8 -*-
# RC1: guard przed podwójnym przyciskiem 'Zamówienia' w Magazynie.
# 1.1: po zbudowaniu istniejącego toolbara dodaje pojedynczy przycisk PZ.
# 1.2: blokada działa dla instancji panelu, więc nowy ekran Magazynu dostaje własny toolbar.

from functools import wraps
from tkinter import messagebox, ttk

def _open_selected_pz(owner):
    try:
        import gui_magazyn as gm
        if hasattr(gm, "_can") and not gm._can(owner, "pz"):
            messagebox.showwarning("Uprawnienia", "Brak uprawnień do przyjęcia PZ.")
            return
    except Exception:
        pass

    item_id = ""
    getter = getattr(owner, "_selected_item_id", None)
    if callable(getter):
        try:
            item_id = str(getter() or "").strip()
        except Exception:
            item_id = ""
    if not item_id:
        messagebox.showinfo("PZ", "Najpierw wybierz pozycję w Magazynie.")
        return

    try:
        from gui_magazyn_pz import open_pz_dialog
        open_pz_dialog(owner, item_id, on_saved=lambda _id=None: owner.refresh())
    except Exception as exc:
        messagebox.showerror("PZ", f"Nie udało się otworzyć przyjęcia PZ:\n{exc}")


def _append_pz_button(toolbar, owner):
    if getattr(owner, "_wm_pz_toolbar_button", None) is not None:
        return
    try:
        button = ttk.Button(
            toolbar,
            text="PZ / Przyjęcie",
            command=lambda: _open_selected_pz(owner),
            style="WM.Side.TButton",
        )
        button.pack(side="right", padx=(0, 6))
        owner._wm_pz_toolbar_button = button
    except Exception:
        pass


def ensure_magazyn_toolbar_once(build_fn):
    @wraps(build_fn)
    def wrapper(*args, **kwargs):
        owner = args[1] if len(args) >= 2 else kwargs.get("owner")
        if owner is not None and getattr(owner, "_wm_magazyn_toolbar_built", False):
            return
        result = build_fn(*args, **kwargs)
        if owner is not None:
            owner._wm_magazyn_toolbar_built = True
        if len(args) >= 2:
            _append_pz_button(args[0], owner)
        return result
    return wrapper
