# version: 1.0
"""
GUI: prosty dialog wyboru użytkownika do przypisania.
Użycie:
    from gui.assign_dialog import ask_user_to_assign
    login = ask_user_to_assign(self)  # parent = okno/Frame
    if login: ... (wykonaj przypisanie)
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

try:
    # lokalny import bez cyklu
    from services.profile_service import ProfileService
except Exception:  # pragma: no cover
    ProfileService = None  # type: ignore


def ask_user_to_assign(parent) -> Optional[str]:
    """Zwraca login wybranego użytkownika lub None (Anuluj)."""
    root = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
    dlg = tk.Toplevel(root)
    dlg.title("Przypisz do użytkownika")
    dlg.transient(root)
    dlg.grab_set()
    dlg.resizable(False, False)
    try:
        dlg.lift()
        dlg.attributes("-topmost", True)
        dlg.after(200, lambda: dlg.attributes("-topmost", False))
    except Exception:
        pass

    # dane
    all_profiles = ProfileService.list_profiles() if ProfileService else []
    profiles = list(all_profiles)
    items = [f'{p["name"]}  —  {p["login"]} ({p["role"]})'.strip() for p in profiles]

    # UI
    frm = ttk.Frame(dlg, padding=10)
    frm.grid(row=0, column=0)
    ttk.Label(frm, text="Szukaj:").grid(row=0, column=0, sticky="w")
    q = tk.StringVar()
    ent = ttk.Entry(frm, textvariable=q, width=40)
    ent.grid(row=0, column=1, sticky="ew", padx=(6, 0))
    frm.grid_columnconfigure(1, weight=1)

    lst = tk.Listbox(frm, width=48, height=10, activestyle="dotbox")
    lst.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(6, 6))
    for it in items:
        lst.insert(tk.END, it)
    lst.selection_set(0) if items else None

    btns = ttk.Frame(frm)
    btns.grid(row=2, column=0, columnspan=2, sticky="e")
    chosen: list[str] = []

    def _ok(*_):
        if not items:
            dlg.destroy()
            return
        i = lst.curselection()
        if not i:
            return
        idx = int(i[0])
        chosen.append(profiles[idx]["login"])
        dlg.destroy()

    def _cancel(*_):
        dlg.destroy()

    ttk.Button(btns, text="OK", command=_ok, width=10).grid(row=0, column=0, padx=4)
    ttk.Button(btns, text="Anuluj", command=_cancel, width=10).grid(row=0, column=1, padx=4)

    # filtrowanie
    def _refilter(*_):
        nonlocal profiles, items
        needle = q.get().strip().lower()
        lst.delete(0, tk.END)
        filtered = []
        for p in all_profiles:
            text = f'{p["name"]}  —  {p["login"]} ({p["role"]})'
            if needle in text.lower():
                filtered.append(p)
                lst.insert(tk.END, text)
        # zachowaj mapowanie
        profiles = filtered
        items = [f'{p["name"]}  —  {p["login"]} ({p["role"]})' for p in profiles]
        if items:
            lst.selection_clear(0, tk.END)
            lst.selection_set(0)

    ent.bind("<KeyRelease>", _refilter)
    lst.bind("<Return>", _ok)
    lst.bind("<Double-1>", _ok)
    dlg.bind("<Escape>", _cancel)

    ent.focus_set()
    root.wait_window(dlg)
    return chosen[0] if chosen else None
