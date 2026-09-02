# WM-VERSION: 0.1
# Plik: planista_operations_runtime.py
# version: 1.0
"""Konfigurowalny słownik operacji technologicznych Planisty."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from config_manager import ConfigManager
from ui_context_help import add_help_button
from ui_utils import _msg_error

DEFAULT_OPERATIONS = ["Cięcie", "Wiercenie", "Szlifowanie", "Gratowanie"]


def _ops_path() -> Path:
    value = ConfigManager().path_data()
    root = Path(value) if value else Path("data")
    return root / "magazyn" / "operacje_technologiczne.json"


def _load_operations() -> list[str]:
    path = _ops_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = DEFAULT_OPERATIONS
    except Exception:
        payload = []
    if isinstance(payload, dict):
        payload = payload.get("operacje") or []
    out = []
    for value in payload if isinstance(payload, list) else []:
        name = str(value.get("nazwa") if isinstance(value, dict) else value or "").strip()
        if name and name.casefold() not in {x.casefold() for x in out}:
            out.append(name)
    return out


def _save_operations(values: list[str]) -> None:
    path = _ops_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")


def _used_operations(model) -> set[str]:
    used = set()
    for rec in getattr(model, "polprodukty", {}).values():
        if isinstance(rec, dict):
            used.update(str(x).strip() for x in (rec.get("czynnosci") or []) if str(x).strip())
    return used


def install_planista_operations_runtime() -> None:
    import gui_magazyn_bom as GMB
    import gui_planista_panel as GPP

    if "Operacje technologiczne" not in GPP.PlanistaPanel._CATALOG_TABS:
        GPP.PlanistaPanel._CATALOG_TABS["Operacje technologiczne"] = 4

    original_build = GPP.PlanistaPanel._build
    if not getattr(original_build, "_wm_operations_tab", False):
        def build_panel(self):
            original_build(self)
            if "Operacje technologiczne" not in self._catalog_hosts:
                host = ttk.Frame(self.nb)
                self.nb.add(host, text="Operacje technologiczne")
                self._catalog_hosts["Operacje technologiczne"] = host
        build_panel._wm_operations_tab = True
        GPP.PlanistaPanel._build = build_panel

    UI = GMB.MagazynBOM
    if getattr(UI, "_wm_operations_dictionary", False):
        return

    old_build_ui = UI._build_ui
    old_build_pp = UI._build_polprodukty
    old_load_pp = UI._on_pp_select

    def build_ui(self):
        old_build_ui(self)
        frm_ops = ttk.Frame(self.nb)
        self.nb.add(frm_ops, text="Operacje technologiczne")
        self._build_operations_dictionary(frm_ops)

    def build_operations_dictionary(self, parent):
        top = ttk.Frame(parent, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Nazwa operacji").grid(row=0, column=0, sticky="w")
        self.operation_name = tk.StringVar()
        ttk.Entry(top, textvariable=self.operation_name).grid(row=1, column=0, sticky="ew")
        ttk.Button(top, text="Dodaj", command=self._add_operation).grid(row=1, column=1, padx=(8, 0))
        add_help_button(top, "Dodaj operację technologiczną używaną przy półproduktach, np. Cięcie, Wiercenie lub Spawanie. Po dodaniu pojawi się ona na liście Operacje w karcie półproduktu.", row=1, column=2, padx=(4, 0))
        top.columnconfigure(0, weight=1)
        self.tree_operations = ttk.Treeview(parent, columns=("nazwa",), show="headings", height=12)
        self.tree_operations.heading("nazwa", text="Operacja technologiczna")
        self.tree_operations.column("nazwa", width=360, anchor="w")
        self.tree_operations.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        bottom = ttk.Frame(parent)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bottom, text="Usuń zaznaczoną", command=self._delete_operation).pack(side="right")
        add_help_button(bottom, "Usuwa operację ze słownika, jeśli nie jest używana przez żaden półprodukt. Operacje zapisane w istniejących półproduktach są chronione przed przypadkowym usunięciem.", command_only=False).pack(side="right", padx=(0, 4))
        self._refresh_operations_tree()

    def refresh_operations_tree(self):
        if not hasattr(self, "tree_operations"):
            return
        self.tree_operations.delete(*self.tree_operations.get_children())
        for idx, name in enumerate(_load_operations()):
            self.tree_operations.insert("", "end", iid=str(idx), values=(name,))

    def refresh_pp_operations(self, selected=None):
        if not hasattr(self, "pp_lb"):
            return
        selected = set(selected or [])
        operations = _load_operations()
        # Zachowaj starsze operacje używane już przez kartę, nawet jeśli słownik był pusty.
        for name in selected:
            if name and name.casefold() not in {x.casefold() for x in operations}:
                operations.append(name)
        self.pp_ops = operations
        self.pp_lb.delete(0, tk.END)
        for op in operations:
            self.pp_lb.insert(tk.END, op)
        for idx, op in enumerate(operations):
            if op in selected:
                self.pp_lb.selection_set(idx)

    def add_operation(self):
        name = self.operation_name.get().strip()
        if not name:
            _msg_error(self, "Operacje technologiczne", "Podaj nazwę operacji.")
            return
        values = _load_operations()
        if any(x.casefold() == name.casefold() for x in values):
            _msg_error(self, "Operacje technologiczne", "Taka operacja już istnieje.")
            return
        values.append(name)
        _save_operations(values)
        self.operation_name.set("")
        self._refresh_operations_tree()
        self._refresh_pp_operations()

    def delete_operation(self):
        selection = self.tree_operations.selection()
        if not selection:
            _msg_error(self, "Operacje technologiczne", "Zaznacz operację do usunięcia.")
            return
        values = _load_operations()
        idx = int(selection[0])
        if idx < 0 or idx >= len(values):
            return
        name = values[idx]
        used = _used_operations(self.model)
        if name in used:
            _msg_error(self, "Operacje technologiczne", "Nie można usunąć operacji używanej przez półprodukt.")
            return
        _save_operations([x for pos, x in enumerate(values) if pos != idx])
        self._refresh_operations_tree()
        self._refresh_pp_operations()

    def build_pp(self, parent):
        old_build_pp(self, parent)
        self._refresh_pp_operations()

    def load_pp(self, event=None):
        old_load_pp(self, event)
        sel = self.tree_pp.selection() if hasattr(self, "tree_pp") else ()
        if not sel:
            return
        code = str(self.tree_pp.item(sel[0], "values")[-1])
        rec = self.model.polprodukty.get(code, {})
        self._refresh_pp_operations(rec.get("czynnosci", []) if isinstance(rec, dict) else [])

    UI._build_ui = build_ui
    UI._build_operations_dictionary = build_operations_dictionary
    UI._refresh_operations_tree = refresh_operations_tree
    UI._refresh_pp_operations = refresh_pp_operations
    UI._add_operation = add_operation
    UI._delete_operation = delete_operation
    UI._build_polprodukty = build_pp
    UI._on_pp_select = load_pp
    UI._wm_operations_dictionary = True


__all__ = ["install_planista_operations_runtime", "_load_operations", "_save_operations", "_used_operations"]
