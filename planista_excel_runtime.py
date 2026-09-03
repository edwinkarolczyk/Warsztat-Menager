# WM-VERSION: 0.2
# Plik: planista_excel_runtime.py
# version: 1.1
# 1.1: po imporcie porównuje każdą pozycję Excel z aktualną kartoteką Produktów WM.
"""UI importu i bezpiecznej analizy zewnętrznego planu Excel."""

from __future__ import annotations

from functools import wraps
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from planista_excel_import import PlanExcelError, load_production_plan
from planista_excel_match import (
    STATUS_AMBIGUOUS,
    STATUS_FOUND,
    STATUS_MISSING,
    match_production_plan,
)
from ui_context_help import add_help_button


_IMPORT_HELP = (
    "Po odczycie porównuje oznaczenie każdej pozycji z aktualną kartoteką Produktów WM. "
    "Nazwa/wariant służą tylko do potwierdzenia; import nadal nie tworzy zleceń."
)


def _match_with_current_catalog(payload: dict) -> dict:
    """Porównaj plan z Produktami z aktywnego WM data root."""
    from gui_magazyn_bom import WarehouseModel

    products = WarehouseModel().produkty
    return match_production_plan(payload, products)


def _show_excel_import_preview(owner, payload: dict) -> None:
    rows = list(payload.get("rows") or [])
    summary = payload.get("match_summary") if isinstance(payload.get("match_summary"), dict) else {}
    dlg = tk.Toplevel(owner.root)
    dlg.title("Planista — analiza Excel ↔ Produkty WM")
    dlg.transient(owner.root)
    dlg.geometry("1520x700")

    top = ttk.Frame(dlg, padding=10)
    top.pack(fill="x")
    ttk.Label(
        top,
        text=(
            f"Plik: {payload.get('source_name', '')}   |   Arkusz: {payload.get('sheet', '')}   |   "
            f"Pozycje: {len(rows)}   |   Produkty WM: {payload.get('product_catalog_size', 0)}"
        ),
        font=("Arial", 10, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        top,
        text=(
            f"{STATUS_FOUND}: {summary.get(STATUS_FOUND, 0)}   |   "
            f"{STATUS_MISSING}: {summary.get(STATUS_MISSING, 0)}   |   "
            f"{STATUS_AMBIGUOUS}: {summary.get(STATUS_AMBIGUOUS, 0)}"
        ),
    ).pack(anchor="w", pady=(3, 0))
    ttk.Label(
        top,
        text="To jest analiza odczytu. Dane nie zostały zapisane do zleceń WM ani do pliku Excel.",
    ).pack(anchor="w", pady=(3, 0))

    body = ttk.Frame(dlg, padding=(10, 0, 10, 10))
    body.pack(fill="both", expand=True)
    cols = (
        "row",
        "order",
        "excel_code",
        "product",
        "qty",
        "date",
        "process",
        "status",
        "wm_product",
        "note",
    )
    labels = {
        "row": "Wiersz Excel",
        "order": "Nr zlec.",
        "excel_code": "Oznaczenie Excel",
        "product": "Produkt / opis z Excel",
        "qty": "Ilość",
        "date": "Data wysyłki",
        "process": "Proces",
        "status": "Status dopasowania",
        "wm_product": "Produkt WM",
        "note": "Uwagi",
    }
    widths = {
        "row": 85,
        "order": 90,
        "excel_code": 135,
        "product": 330,
        "qty": 75,
        "date": 105,
        "process": 105,
        "status": 155,
        "wm_product": 250,
        "note": 420,
    }
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for col in cols:
        tree.heading(col, text=labels[col])
        tree.column(col, width=widths[col], anchor="w", stretch=col in {"product", "note"})

    yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    for idx, row in enumerate(rows):
        qty = row.get("ilosc")
        if isinstance(qty, float) and qty.is_integer():
            qty = int(qty)
        wm_symbol = str(row.get("wm_symbol") or "").strip()
        wm_name = str(row.get("wm_nazwa") or "").strip()
        wm_product = " | ".join(part for part in (wm_symbol, wm_name) if part)
        tree.insert(
            "",
            "end",
            iid=str(idx),
            values=(
                row.get("source_row", ""),
                row.get("nr_zlec", ""),
                row.get("excel_oznaczenie", ""),
                row.get("produkt", ""),
                "" if qty is None else qty,
                row.get("data_wysylki", ""),
                row.get("proces", ""),
                row.get("match_status", ""),
                wm_product,
                row.get("match_note", ""),
            ),
        )

    ttk.Button(dlg, text="Zamknij", command=dlg.destroy).pack(anchor="e", padx=10, pady=(0, 10))


def _import_excel_plan(owner) -> None:
    path = filedialog.askopenfilename(
        parent=owner.root,
        title="Wybierz zewnętrzny plan produkcji Excel",
        filetypes=(("Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")),
    )
    if not path:
        return

    try:
        payload = load_production_plan(path, sheet_name="PLAN 2026")
        payload = _match_with_current_catalog(payload)
    except PlanExcelError as exc:
        messagebox.showerror("Import planu Excel", str(exc), parent=owner)
        return
    except Exception as exc:  # pragma: no cover - ochrona UI przed nieoczekiwanym błędem pliku/kartoteki
        messagebox.showerror("Import planu Excel", f"Nie udało się przeanalizować planu:\n{exc}", parent=owner)
        return

    owner._excel_plan_import = payload
    _show_excel_import_preview(owner, payload)


def install_planista_excel_runtime() -> None:
    """Dodaj import i analizę Excel bez ingerowania w konfigurację tabeli Zleceń."""
    import gui_planista_panel as gp

    cls = gp.PlanistaPanel
    if getattr(cls, "_wm_excel_import_runtime", False):
        return

    original_build_orders = cls._build_orders

    @wraps(original_build_orders)
    def build_orders(self, parent):
        result = original_build_orders(self, parent)
        excel_bar = ttk.Frame(parent)
        excel_bar.pack(fill="x", pady=(6, 0))
        ttk.Label(excel_bar, text="Plan zewnętrzny:").pack(side="left")
        ttk.Button(
            excel_bar,
            text="Wczytaj plan Excel…",
            command=lambda: _import_excel_plan(self),
        ).pack(side="left", padx=(6, 4))
        add_help_button(excel_bar, _IMPORT_HELP, command_only=False).pack(side="left")
        ttk.Label(
            excel_bar,
            text="odczyt + dopasowanie Produktów — bez tworzenia zleceń",
        ).pack(side="left", padx=(10, 0))
        return result

    cls._build_orders = build_orders
    cls.import_excel_plan = _import_excel_plan
    cls._show_excel_import_preview = _show_excel_import_preview
    cls._wm_excel_import_runtime = True
