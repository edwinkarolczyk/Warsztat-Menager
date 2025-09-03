"""GUI helpers for magazyn BOM with alert colouring."""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager


DATA_DIR = os.path.join("data", "polprodukty")
STOCK_PATH = os.path.join("data", "magazyn", "polprodukty.json")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _write_json(path: str, data: dict) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_tree(tree: ttk.Treeview) -> None:
    """Load stock info and colour alert rows."""
    cfg = ConfigManager()
    progi_pct = cfg.get("progi_alertow_pct", [100])
    progi_surowce = cfg.get("progi_alertow_surowce", {})
    default_prog = float(progi_pct[0]) if progi_pct else 0.0

    try:
        with open(STOCK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    tree.delete(*tree.get_children())
    for kod, info in data.items():
        ilosc = float(info.get("stan", 0))
        prog = float(progi_surowce.get(kod, default_prog))
        tags = ("alert",) if ilosc <= prog else ()
        tree.insert("", "end", values=(kod, ilosc, prog), tags=tags)

    tree.tag_configure("alert", background="#ffb3b3")


def make_window(root: tk.Misc) -> ttk.Frame:
    cfg = ConfigManager()
    ops = cfg.get("czynnosci_technologiczne", [])

    frame = ttk.Frame(root)
    ttk.Label(frame, text="Kod").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    var_kod = tk.StringVar()
    ttk.Entry(frame, textvariable=var_kod).grid(
        row=0, column=1, sticky="ew", padx=6, pady=4
    )

    ttk.Label(frame, text="Czynności").grid(row=1, column=0, sticky="nw", padx=6, pady=4)
    lb = tk.Listbox(frame, selectmode="multiple", height=min(6, len(ops)))
    for op in ops:
        lb.insert("end", op)
    lb.grid(row=1, column=1, sticky="nsew", padx=6, pady=4)
    frame.columnconfigure(1, weight=1)

    tree = ttk.Treeview(
        frame,
        columns=("kod", "ilosc", "prog"),
        show="headings",
        height=6,
    )
    tree.heading("kod", text="Kod")
    tree.heading("ilosc", text="Ilość")
    tree.heading("prog", text="Próg alertu")
    tree.column("kod", width=80, anchor="w")
    tree.column("ilosc", width=80, anchor="e")
    tree.column("prog", width=80, anchor="e")
    tree.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
    frame.rowconfigure(3, weight=1)
    _load_tree(tree)

    def _save() -> None:
        sel = [ops[int(i)] for i in lb.curselection()]
        rec = {"kod": var_kod.get(), "czynnosci": sel}
        path = os.path.join(DATA_DIR, f"{var_kod.get()}.json")
        _write_json(path, rec)
        messagebox.showinfo("Zapis", "Zapisano dane")

    ttk.Button(frame, text="Zapisz", command=_save).grid(
        row=2, column=1, sticky="e", padx=6, pady=4
    )
    return frame

