# WM-VERSION: 0.5
# Plik: planista_excel_runtime.py
# version: 1.4
# 1.4: dodano wejście do kontrolowanego podglądu i zatwierdzania synchronizacji zleceń WM.
# 1.3: znalezione Produkty WM są wyróżniane na zielono i pokazywane na górze podglądu.
# 1.2: zapisuje snapshot pod WM_ROOT i wykrywa zmiany między kolejnymi analizami planu.
# 1.1: po imporcie porównuje każdą pozycję Excel z aktualną kartoteką Produktów WM.
"""UI importu, dopasowania i bezpiecznej analizy zmian planu Excel."""

from __future__ import annotations

from functools import wraps
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from planista_excel_changes import (
    CHANGE_BASELINE,
    CHANGE_CHANGED,
    CHANGE_NEW_ORDER,
    CHANGE_NEW_ROW,
    CHANGE_NONE,
    CHANGE_REMOVED,
    PlanChangeError,
    analyze_and_store_plan_changes,
    last_plan_source_path,
)
from planista_excel_import import PlanExcelError, load_production_plan
from planista_excel_match import (
    STATUS_AMBIGUOUS,
    STATUS_FOUND,
    STATUS_MISSING,
    match_production_plan,
)
from planista_excel_sync_runtime import show_excel_sync_preview
from ui_context_help import add_help_button
from ui_theme import get_theme_color


_IMPORT_HELP = (
    "Wczytuje plan, dopasowuje oznaczenia do Produktów WM i porównuje go z poprzednim snapshotem. "
    "Nie zmienia pliku Excel ani zleceń WM."
)
_CHECK_HELP = (
    "Ponownie odczytuje ostatnio analizowany plik i pokazuje, co zmieniło się od poprzedniego sprawdzenia. "
    "Po analizie zapisuje nowy snapshot pod aktywnym WM_ROOT, ale nie zmienia zleceń."
)
_SYNC_HELP = (
    "Pokazuje, które pozycje mogą utworzyć lub zaktualizować zlecenia WM, a które wymagają wyjaśnienia. "
    "Samo otwarcie podglądu niczego nie zapisuje; zapis wymaga jawnego zaznaczenia i potwierdzenia."
)


def _match_with_current_catalog(payload: dict) -> dict:
    """Porównaj plan z Produktami z aktywnego WM data root."""
    from gui_magazyn_bom import WarehouseModel

    products = WarehouseModel().produkty
    return match_production_plan(payload, products)


def _load_match_and_compare(path: str) -> dict:
    payload = load_production_plan(path, sheet_name="PLAN 2026")
    payload = _match_with_current_catalog(payload)
    return analyze_and_store_plan_changes(payload)


def _change_summary_text(payload: dict) -> str:
    summary = payload.get("change_summary") if isinstance(payload.get("change_summary"), dict) else {}
    if payload.get("baseline_created"):
        return (
            f"{CHANGE_BASELINE}: {summary.get(CHANGE_BASELINE, 0)} — zapisano pierwszy punkt odniesienia."
        )
    return (
        f"{CHANGE_CHANGED}: {summary.get(CHANGE_CHANGED, 0)}   |   "
        f"{CHANGE_NEW_ORDER}: {summary.get(CHANGE_NEW_ORDER, 0)}   |   "
        f"{CHANGE_NEW_ROW}: {summary.get(CHANGE_NEW_ROW, 0)}   |   "
        f"{CHANGE_REMOVED}: {summary.get(CHANGE_REMOVED, 0)}   |   "
        f"{CHANGE_NONE}: {summary.get(CHANGE_NONE, 0)}"
    )


def _preview_row_sort_key(row: dict) -> int:
    """Znalezione Produkty WM pokazuj pierwsze, zachowując kolejność w obrębie grup."""
    return 0 if str(row.get("match_status") or "").strip() == STATUS_FOUND else 1


def _show_excel_import_preview(owner, payload: dict) -> None:
    rows = list(payload.get("rows") or [])
    removed_rows = list(payload.get("removed_rows") or [])
    summary = payload.get("match_summary") if isinstance(payload.get("match_summary"), dict) else {}
    dlg = tk.Toplevel(owner.root)
    dlg.title("Planista — analiza Excel ↔ Produkty WM")
    dlg.transient(owner.root)
    dlg.geometry("1600x730")

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
    ttk.Label(top, text=_change_summary_text(payload)).pack(anchor="w", pady=(3, 0))
    ttk.Label(
        top,
        text=(
            "Analiza nie zmieniła zleceń WM ani pliku Excel. "
            f"Snapshot: {payload.get('snapshot_path', '')}"
        ),
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
        "change",
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
        "change": "Zmiana Excel",
        "status": "Status dopasowania",
        "wm_product": "Produkt WM",
        "note": "Uwagi",
    }
    widths = {
        "row": 85,
        "order": 90,
        "excel_code": 130,
        "product": 310,
        "qty": 70,
        "date": 105,
        "process": 95,
        "change": 145,
        "status": 145,
        "wm_product": 230,
        "note": 470,
    }
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for col in cols:
        tree.heading(col, text=labels[col])
        tree.column(col, width=widths[col], anchor="w", stretch=col in {"product", "note"})

    tree.tag_configure(
        "wm_found",
        background=get_theme_color("success", fallback="#29a36a"),
        foreground=get_theme_color("fg", fallback="#ffffff"),
    )

    yscroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    display_rows = sorted(rows, key=_preview_row_sort_key) + removed_rows
    for idx, row in enumerate(display_rows):
        qty = row.get("ilosc")
        if isinstance(qty, float) and qty.is_integer():
            qty = int(qty)
        wm_symbol = str(row.get("wm_symbol") or "").strip()
        wm_name = str(row.get("wm_nazwa") or "").strip()
        wm_product = " | ".join(part for part in (wm_symbol, wm_name) if part)
        notes = "; ".join(
            part
            for part in (
                str(row.get("excel_change_note") or "").strip(),
                str(row.get("match_note") or "").strip(),
            )
            if part
        )
        found_in_wm = (
            str(row.get("match_status") or "").strip() == STATUS_FOUND
            and str(row.get("excel_change_status") or "").strip() != CHANGE_REMOVED
        )
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
                row.get("excel_change_status", ""),
                row.get("match_status", ""),
                wm_product,
                notes,
            ),
            tags=("wm_found",) if found_in_wm else (),
        )

    ttk.Button(dlg, text="Zamknij", command=dlg.destroy).pack(anchor="e", padx=10, pady=(0, 10))


def _handle_analysis(owner, path: str) -> None:
    try:
        payload = _load_match_and_compare(path)
    except (PlanExcelError, PlanChangeError) as exc:
        messagebox.showerror("Analiza planu Excel", str(exc), parent=owner)
        return
    except Exception as exc:  # pragma: no cover - ochrona UI przed nieoczekiwanym błędem pliku/kartoteki
        messagebox.showerror("Analiza planu Excel", f"Nie udało się przeanalizować planu:\n{exc}", parent=owner)
        return

    owner._excel_plan_import = payload
    _show_excel_import_preview(owner, payload)


def _import_excel_plan(owner) -> None:
    path = filedialog.askopenfilename(
        parent=owner.root,
        title="Wybierz zewnętrzny plan produkcji Excel",
        filetypes=(("Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")),
    )
    if path:
        _handle_analysis(owner, path)


def _check_excel_changes(owner) -> None:
    payload = getattr(owner, "_excel_plan_import", None)
    path = str(payload.get("source_path") or "").strip() if isinstance(payload, dict) else ""
    if not path:
        try:
            path = last_plan_source_path()
        except PlanChangeError as exc:
            messagebox.showerror("Sprawdź zmiany", str(exc), parent=owner)
            return
    if not path:
        messagebox.showinfo(
            "Sprawdź zmiany",
            "Najpierw użyj „Wczytaj plan Excel…”, aby utworzyć punkt odniesienia.",
            parent=owner,
        )
        return
    _handle_analysis(owner, path)


def _open_excel_sync(owner) -> None:
    payload = getattr(owner, "_excel_plan_import", None)
    if not isinstance(payload, dict) or not (
        list(payload.get("rows") or []) or list(payload.get("removed_rows") or [])
    ):
        messagebox.showinfo(
            "Synchronizuj z WM",
            "Najpierw użyj „Wczytaj plan Excel…” albo „Sprawdź zmiany”, aby przygotować aktualną analizę.",
            parent=owner,
        )
        return
    show_excel_sync_preview(owner, payload)


def install_planista_excel_runtime() -> None:
    """Dodaj import, analizę oraz jawne wejście do kontrolowanej synchronizacji."""
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
        ttk.Button(
            excel_bar,
            text="Sprawdź zmiany",
            command=lambda: _check_excel_changes(self),
        ).pack(side="left", padx=(12, 4))
        add_help_button(excel_bar, _CHECK_HELP, command_only=False).pack(side="left")
        ttk.Button(
            excel_bar,
            text="Synchronizuj z WM…",
            command=lambda: _open_excel_sync(self),
        ).pack(side="left", padx=(12, 4))
        add_help_button(excel_bar, _SYNC_HELP, command_only=False).pack(side="left")
        ttk.Label(
            excel_bar,
            text="Wczytaj/Sprawdź: bez tworzenia zleceń | Synchronizuj: zapis dopiero po zatwierdzeniu",
        ).pack(side="left", padx=(10, 0))
        return result

    cls._build_orders = build_orders
    cls.import_excel_plan = _import_excel_plan
    cls.check_excel_changes = _check_excel_changes
    cls.open_excel_sync = _open_excel_sync
    cls._show_excel_import_preview = _show_excel_import_preview
    cls._wm_excel_import_runtime = True
