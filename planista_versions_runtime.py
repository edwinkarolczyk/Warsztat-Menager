# WM-VERSION: 0.1
# Plik: planista_versions_runtime.py
# version: 1.0
"""Wersja i rewizja produktu bez utraty wcześniejszej definicji BOM."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import simpledialog, ttk


def _archive_name(symbol: str, version: str) -> str:
    safe_symbol = re.sub(r"[^0-9A-Za-z._-]+", "_", str(symbol or "produkt")).strip("_") or "produkt"
    safe_version = re.sub(r"[^0-9A-Za-z._-]+", "_", str(version or "1.0")).strip("_") or "1.0"
    return f"{safe_symbol}__v{safe_version}.json"


def _suggest_next_version(value: str) -> str:
    raw = str(value or "1.0").strip()
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?$", raw)
    if not match:
        return raw
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return f"{major}.{minor + 1}"


def install_planista_versions_runtime() -> None:
    import gui_magazyn_bom as GMB

    Model = GMB.WarehouseModel
    current_add = Model.add_or_update_produkt
    if not getattr(current_add, "_wm_versions", False):
        def versioned_add(self, record):
            rec = dict(record)
            symbol = str(rec.get("symbol") or "").strip()
            current = self.produkty.get(symbol)
            new_version = str(rec.get("version") or "1.0").strip() or "1.0"
            rec["version"] = new_version
            rec.setdefault("revision", 1)
            rec["is_default"] = True
            if isinstance(current, dict):
                old_version = str(current.get("version") or "1.0").strip() or "1.0"
                if old_version != new_version:
                    archived = dict(current)
                    archived["version"] = old_version
                    archived["is_default"] = False
                    GMB._save_json(self.prd_dir / _archive_name(symbol, old_version), archived)
            result = current_add(self, rec)
            self.produkty[symbol] = rec
            return result
        versioned_add._wm_versions = True
        versioned_add._wm_original = current_add
        Model.add_or_update_produkt = versioned_add

    UI = GMB.MagazynBOM
    if getattr(UI, "_wm_versions", False):
        return

    old_build = UI._build_produkty
    old_new = UI._new_produkt
    old_select = UI._on_pr_select

    def new_product(self):
        old_new(self)
        if hasattr(self, "pr_vars"):
            self.pr_vars.get("version", tk.StringVar()).set("1.0")
            self.pr_vars.get("revision", tk.StringVar()).set("1")

    def select_product(self, event=None):
        old_select(self, event)
        sel = self.tree_pr.selection()
        if not sel or not hasattr(self, "pr_vars"):
            return
        symbol = str(self.tree_pr.item(sel[0], "values")[0])
        rec = self.model.produkty.get(symbol, {})
        self.pr_vars["version"].set(str(rec.get("version") or "1.0"))
        self.pr_vars["revision"].set(str(rec.get("revision", rec.get("rewizja", 1)) or 1))

    def save_product(self):
        symbol = self.pr_vars["symbol"].get().strip()
        name = self.pr_vars["nazwa"].get().strip()
        version = self.pr_vars["version"].get().strip()
        revision = self.pr_vars["revision"].get().strip()
        if not symbol or not name:
            GMB._msg_error(self, "Produkty", "Wymagane pola: oznaczenie produktu i nazwa.")
            return
        if not version:
            GMB._msg_error(self, "Produkty", "Wersja produktu nie może być pusta.")
            return
        if not revision:
            GMB._msg_error(self, "Produkty", "Rewizja składu nie może być pusta.")
            return
        if not self._product_bom_rows:
            GMB._msg_error(self, "Produkty", "Dodaj przynajmniej jeden półprodukt do składu produktu.")
            return
        rec = {
            "symbol": symbol,
            "nazwa": name,
            "version": version,
            "revision": revision,
            "is_default": True,
            "BOM": [dict(row) for row in self._product_bom_rows],
        }
        self.model.add_or_update_produkt(rec)
        self._load_produkty()
        new_product(self)

    def prepare_new_version(self):
        symbol = self.pr_vars["symbol"].get().strip() if hasattr(self, "pr_vars") else ""
        if not symbol:
            GMB._msg_error(self, "Produkty", "Najpierw wybierz zapisany produkt.")
            return
        current = self.pr_vars["version"].get().strip() or "1.0"
        value = simpledialog.askstring(
            "Nowa wersja produktu",
            "Podaj numer nowej wersji. Obecna wersja zostanie zachowana jako archiwalna.",
            initialvalue=_suggest_next_version(current),
            parent=self,
        )
        if value is None:
            return
        value = value.strip()
        if not value or value == current:
            GMB._msg_error(self, "Produkty", "Nowa wersja musi różnić się od obecnej.")
            return
        self.pr_vars["version"].set(value)
        self.pr_vars["revision"].set("1")

    def build_products(self, parent):
        old_build(self, parent)
        form = None
        for child in parent.winfo_children():
            try:
                if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "Karta produktu":
                    form = child
                    break
            except Exception:
                continue
        if form is None:
            return
        self.pr_vars.setdefault("version", tk.StringVar(value="1.0"))
        self.pr_vars.setdefault("revision", tk.StringVar(value="1"))
        for child in form.winfo_children():
            try:
                if isinstance(child, ttk.LabelFrame) and str(child.cget("text")) == "Półprodukty w produkcie":
                    child.grid_configure(row=4)
                    break
            except Exception:
                continue
        ttk.Label(form, text="Wersja").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["version"], width=16).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self._help(form, 2, "Numer wersji produktu, np. 1.0 lub 2.0. Zmiana wersji zachowuje poprzednią definicję BOM dla istniejących zleceń.")
        ttk.Label(form, text="Rewizja składu").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["revision"], width=16).grid(row=3, column=1, sticky="w", padx=4, pady=2)
        self._help(form, 3, "Rewizja oznacza kolejną zmianę składu w tej samej wersji. Zwiększ ją, gdy zmieniasz BOM bez tworzenia nowej wersji produktu.")
        bar = next((child for child in parent.winfo_children() if isinstance(child, ttk.Frame)), None)
        if bar is not None:
            ttk.Button(bar, text="Nowa wersja", command=prepare_new_version.__get__(self, UI)).pack(side="left", padx=(6, 0))
            from ui_context_help import add_help_button
            add_help_button(bar, "Tworzy nową wersję na bazie aktualnego produktu. Po zapisie poprzednia wersja pozostaje dostępna dla zleceń, które ją wskazują.", command_only=False).pack(side="left", padx=(2, 0))
        new_product(self)

    UI._new_produkt = new_product
    UI._on_pr_select = select_product
    UI._save_produkt = save_product
    UI._build_produkty = build_products
    UI._wm_versions = True


__all__ = ["install_planista_versions_runtime", "_archive_name", "_suggest_next_version"]
