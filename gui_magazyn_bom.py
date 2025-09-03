"""GUI for editing BOM items with technological operations."""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager
from ui_theme import apply_theme_tree


DATA_DIR = os.path.join("data", "polprodukty")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _write_json(path: str, data: dict) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


class MagazynBOMWindow(tk.Toplevel):
    """Window for managing warehouse and BOM items."""

    def __init__(self, master: tk.Misc | None = None):
        super().__init__(master)
        self.title("Ustawienia – Magazyn i BOM")
        frame = make_window(self)
        frame.pack(fill="both", expand=True)
        apply_theme_tree(self)

