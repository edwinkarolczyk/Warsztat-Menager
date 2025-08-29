# Wersja pliku: 1.0.0
# Plik: gui_settings_shifts.py
# Zmiany:
# - Panel ustawień grafiku zmian

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from utils import error_dialogs

from grafiki.shifts_schedule import _load_users, TRYBY, set_user_mode, set_anchor_monday

MODES_FILE = os.path.join("data", "grafiki", "tryby_userow.json")


def _load_modes():
    try:
        with open(MODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"anchor_monday": "2025-01-06", "modes": {}}


class ShiftsSettingsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        modes = _load_modes()
        self.anchor_var = tk.StringVar(value=modes.get("anchor_monday", "2025-01-06"))

        anchor = ttk.Frame(self)
        anchor.pack(fill="x", padx=8, pady=8)
        ttk.Label(anchor, text="Kotwica poniedziałek (YYYY-MM-DD):").pack(side="left")
        ttk.Entry(anchor, textvariable=self.anchor_var, width=12).pack(side="left", padx=5)
        ttk.Button(anchor, text="Zapisz kotwicę", command=self._save_anchor).pack(side="left", padx=5)

        cols = ("id", "name", "mode")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Użytkownik")
        self.tree.heading("mode", text="Tryb")
        self.tree.column("id", width=100)
        self.tree.column("name", width=200)
        self.tree.column("mode", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=5)
        ttk.Button(btns, text="Odśwież", command=self._populate).pack(side="left", padx=5)
        ttk.Button(btns, text="Zamknij", command=self._close).pack(side="right", padx=5)

        self.tree.bind("<Double-1>", self._edit_mode)
        self._populate()

    def _close(self):
        self.winfo_toplevel().destroy()

    def _save_anchor(self):
        try:
            set_anchor_monday(self.anchor_var.get())
        except ValueError as e:
            error_dialogs.show_error_dialog("Błąd", str(e))

    def _populate(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        modes = _load_modes().get("modes", {})
        for u in _load_users():
            if not u.get("active"):
                continue
            mode = modes.get(u["id"], "B")
            self.tree.insert("", "end", iid=u["id"], values=(u["id"], u["name"], mode))

    def _edit_mode(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        x, y, width, height = self.tree.bbox(item, column="mode")
        value = self.tree.set(item, "mode")
        cb = ttk.Combobox(self.tree, values=TRYBY, state="readonly")
        cb.set(value)
        cb.place(x=x, y=y, width=width, height=height)
        cb.focus()

        def _on_select(_):
            new_mode = cb.get()
            set_user_mode(item, new_mode)
            cb.destroy()
            self._populate()

        cb.bind("<<ComboboxSelected>>", _on_select)
        cb.bind("<FocusOut>", lambda e: cb.destroy())
# ⏹ KONIEC KODU
