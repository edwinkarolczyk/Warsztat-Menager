# WM-VERSION: 0.5
# Plik: planista_excel_runtime.py
# version: 1.6
# 1.6: dodano automatyczną pracę na wybranym Excelu z analizą wyłącznie odłączonej kopii i kolejką Do akceptacji.
# 1.5: dodano wyszukiwarkę w podglądzie analizy Excel → Produkty WM.
# 1.4: dodano wejście do kontrolowanego podglądu i zatwierdzania synchronizacji zleceń WM.
# 1.3: znalezione Produkty WM są wyróżniane na zielono i pokazywane na górze podglądu.
# 1.2: zapisuje snapshot pod WM_ROOT i wykrywa zmiany między kolejnymi analizami planu.
# 1.1: po imporcie porównuje każdą pozycję Excel z aktualną kartoteką Produktów WM.
"""UI importu, dopasowania i bezpiecznej analizy zmian planu Excel."""

from __future__ import annotations

from datetime import datetime
from functools import wraps
from pathlib import Path
import threading
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
from planista_excel_auto_runtime import (
    DEFAULT_INTERVAL_MS,
    load_auto_state,
    parse_from_detached_copy,
    save_auto_state,
)
from planista_excel_match import (
    STATUS_AMBIGUOUS,
    STATUS_FOUND,
    STATUS_MISSING,
    match_production_plan,
)
from planista_excel_orders import ACTION_CREATE, ACTION_UPDATE, build_order_sync_plan
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
    """Czytaj zawsze z odłączonej kopii; snapshot zachowuje ścieżkę oryginału."""
    original = Path(path).expanduser().resolve()

    def _parse(copy_path: Path) -> dict:
        payload = load_production_plan(str(copy_path), sheet_name="PLAN 2026")
        # Parser widzi kopię tymczasową, ale biznesowo źródłem pozostaje oryginał.
        payload["source_name"] = original.name
        payload["source_path"] = str(original)
        return payload

    payload = parse_from_detached_copy(original, _parse)
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


def _preview_row_search_text(row: dict) -> str:
    """Tekst przeszukiwany w oknie analizy planu Excel."""
    wm_symbol = str(row.get("wm_symbol") or "").strip()
    wm_name = str(row.get("wm_nazwa") or "").strip()
    notes = " ".join(
        part
        for part in (
            str(row.get("excel_change_note") or "").strip(),
            str(row.get("match_note") or "").strip(),
        )
        if part
    )
    parts = (
        row.get("source_row", ""),
        row.get("nr_zlec", ""),
        row.get("excel_oznaczenie", ""),
        row.get("produkt", ""),
        row.get("ilosc", ""),
        row.get("data_wysylki", ""),
        row.get("proces", ""),
        row.get("excel_change_status", ""),
        row.get("match_status", ""),
        wm_symbol,
        wm_name,
        notes,
    )
    return " ".join(str(value or "") for value in parts).casefold()


def _preview_row_matches_search(row: dict, query: str) -> bool:
    needle = str(query or "").strip().casefold()
    return not needle or needle in _preview_row_search_text(row)


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

    search_bar = ttk.Frame(dlg, padding=(10, 0, 10, 6))
    search_bar.pack(fill="x")
    search_var = tk.StringVar()
    visible_var = tk.StringVar()
    ttk.Label(search_bar, text="Szukaj:").pack(side="left")
    search_entry = ttk.Entry(search_bar, textvariable=search_var, width=44)
    search_entry.pack(side="left", padx=(6, 8))
    ttk.Button(
        search_bar,
        text="Wyczyść",
        command=lambda: search_var.set(""),
    ).pack(side="left")
    ttk.Label(
        search_bar,
        text="Nr zlecenia, oznaczenie, produkt, status, Produkt WM…",
    ).pack(side="left", padx=(10, 0))
    ttk.Label(search_bar, textvariable=visible_var).pack(side="right")

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

    def render_rows(*_args) -> None:
        tree.delete(*tree.get_children())
        query = search_var.get()
        filtered = [
            row
            for row in display_rows
            if _preview_row_matches_search(row, query)
        ]
        for idx, row in enumerate(filtered):
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
        visible_var.set(f"Widoczne: {len(filtered)} / {len(display_rows)}")

    search_var.trace_add("write", render_rows)
    render_rows()
    search_entry.focus_set()

    ttk.Button(dlg, text="Zamknij", command=dlg.destroy).pack(anchor="e", padx=10, pady=(0, 10))


def _auto_source_from_owner(owner) -> str:
    value = str(getattr(owner, "_excel_auto_source_path", "") or "").strip()
    if value:
        return value
    payload = getattr(owner, "_excel_plan_import", None)
    if isinstance(payload, dict):
        value = str(payload.get("source_path") or "").strip()
        if value:
            return value
    try:
        state = load_auto_state()
        value = str(state.get("source_path") or "").strip()
        if value:
            return value
    except Exception:
        pass
    try:
        return str(last_plan_source_path() or "").strip()
    except Exception:
        return ""


def _remember_auto_source(owner, path: str, *, persist: bool = True) -> str:
    source = str(Path(path).expanduser().resolve()) if path else ""
    owner._excel_auto_source_path = source
    label = getattr(owner, "_excel_auto_source_label", None)
    if label is not None:
        try:
            label.configure(
                text=(Path(source).name if source else "brak wybranego pliku")
            )
        except Exception:
            pass
    if persist:
        try:
            enabled_var = getattr(owner, "_excel_auto_var", None)
            enabled = bool(enabled_var.get()) if enabled_var is not None else False
            save_auto_state(enabled=enabled, source_path=source)
        except Exception:
            pass
    return source


def _pending_sync_count(payload: dict) -> int:
    try:
        plan = build_order_sync_plan(payload)
    except Exception:
        return 0
    return sum(
        1
        for item in list(plan.get("items") or [])
        if isinstance(item, dict) and item.get("action") in {ACTION_CREATE, ACTION_UPDATE}
    )


def _cancel_blink(owner) -> None:
    job = getattr(owner, "_excel_auto_blink_job", None)
    if job:
        try:
            owner.after_cancel(job)
        except Exception:
            pass
    owner._excel_auto_blink_job = None


def _blink_acceptance(owner) -> None:
    button = getattr(owner, "_excel_auto_accept_button", None)
    count = int(getattr(owner, "_excel_auto_pending_count", 0) or 0)
    if button is None or count <= 0:
        _cancel_blink(owner)
        return
    on = not bool(getattr(owner, "_excel_auto_blink_on", False))
    owner._excel_auto_blink_on = on
    try:
        button.configure(
            bg=("#f59e0b" if on else "#b45309"),
            activebackground=("#f59e0b" if on else "#b45309"),
        )
        owner._excel_auto_blink_job = owner.after(650, lambda: _blink_acceptance(owner))
    except Exception:
        owner._excel_auto_blink_job = None


def _set_pending_count(owner, count: int) -> None:
    count = max(0, int(count or 0))
    owner._excel_auto_pending_count = count
    button = getattr(owner, "_excel_auto_accept_button", None)
    if button is None:
        return
    _cancel_blink(owner)
    try:
        button.configure(
            text=f"Do akceptacji ({count})",
            state=("normal" if count > 0 else "disabled"),
            bg=("#f59e0b" if count > 0 else "#374151"),
            activebackground=("#f59e0b" if count > 0 else "#374151"),
        )
    except Exception:
        return
    if count > 0:
        owner._excel_auto_blink_on = False
        _blink_acceptance(owner)


def _refresh_auto_pending(owner) -> None:
    payload = getattr(owner, "_excel_plan_import", None)
    if not isinstance(payload, dict):
        _set_pending_count(owner, 0)
        return
    _set_pending_count(owner, _pending_sync_count(payload))


def _set_manual_excel_controls(owner, *, enabled: bool) -> None:
    state = "normal" if enabled else "disabled"
    for button in list(getattr(owner, "_excel_manual_buttons", []) or []):
        try:
            button.configure(state=state)
        except Exception:
            pass


def _set_auto_status(owner, text: str) -> None:
    var = getattr(owner, "_excel_auto_status_var", None)
    if var is not None:
        try:
            var.set(text)
        except Exception:
            pass


def _cancel_auto_job(owner) -> None:
    job = getattr(owner, "_excel_auto_job", None)
    if job:
        try:
            owner.after_cancel(job)
        except Exception:
            pass
    owner._excel_auto_job = None


def _schedule_auto_tick(owner, delay_ms: int = DEFAULT_INTERVAL_MS) -> None:
    _cancel_auto_job(owner)
    try:
        owner._excel_auto_job = owner.after(
            max(250, int(delay_ms)),
            lambda: _auto_tick(owner),
        )
    except Exception:
        owner._excel_auto_job = None


def _finish_auto_scan(owner, payload: dict | None, error: str, source: str) -> None:
    owner._excel_auto_running = False
    auto_var = getattr(owner, "_excel_auto_var", None)
    if auto_var is None or not bool(auto_var.get()):
        return
    if error:
        _set_auto_status(owner, f"Automat: błąd — {error}")
        return
    if not isinstance(payload, dict):
        _set_auto_status(owner, "Automat: brak danych")
        return

    owner._excel_plan_import = payload
    _remember_auto_source(owner, source, persist=True)
    count = _pending_sync_count(payload)
    _set_pending_count(owner, count)
    stamp = datetime.now().strftime("%H:%M:%S")
    _set_auto_status(
        owner,
        f"Automat: sprawdzono {stamp} • do akceptacji: {count}",
    )


def _auto_scan_worker(owner, source: str) -> None:
    payload = None
    error = ""
    try:
        payload = _load_match_and_compare(source)
    except Exception as exc:
        error = str(exc)
    try:
        owner.after(
            0,
            lambda: _finish_auto_scan(owner, payload, error, source),
        )
    except Exception:
        owner._excel_auto_running = False


def _auto_tick(owner) -> None:
    auto_var = getattr(owner, "_excel_auto_var", None)
    if auto_var is None or not bool(auto_var.get()):
        _cancel_auto_job(owner)
        return
    try:
        if not owner.winfo_exists():
            _cancel_auto_job(owner)
            return
    except Exception:
        _cancel_auto_job(owner)
        return

    source = _auto_source_from_owner(owner)
    if not source:
        _set_auto_status(owner, "Automat: brak wybranego pliku")
        _schedule_auto_tick(owner)
        return
    if not Path(source).is_file():
        _set_auto_status(owner, "Automat: wybrany plik nie istnieje")
        _schedule_auto_tick(owner)
        return

    if not bool(getattr(owner, "_excel_auto_running", False)):
        owner._excel_auto_running = True
        _set_auto_status(owner, "Automat: kopiowanie i sprawdzanie…")
        threading.Thread(
            target=_auto_scan_worker,
            args=(owner, source),
            daemon=True,
            name="WM-Planista-Excel-Auto",
        ).start()
    _schedule_auto_tick(owner)


def _toggle_auto_mode(owner) -> None:
    auto_var = getattr(owner, "_excel_auto_var", None)
    if auto_var is None:
        return
    enabled = bool(auto_var.get())
    source = _auto_source_from_owner(owner)

    if enabled and not source:
        auto_var.set(False)
        messagebox.showinfo(
            "Automatyczny plan Excel",
            "Najpierw wybierz plan przez „Wczytaj plan Excel…”.",
            parent=getattr(owner, "root", owner),
        )
        return

    if enabled and not Path(source).is_file():
        auto_var.set(False)
        messagebox.showerror(
            "Automatyczny plan Excel",
            f"Wybrany plik nie istnieje:\n{source}",
            parent=getattr(owner, "root", owner),
        )
        return

    _remember_auto_source(owner, source, persist=False)
    save_auto_state(enabled=enabled, source_path=source)
    _set_manual_excel_controls(owner, enabled=not enabled)

    if enabled:
        _set_auto_status(owner, "Automat: uruchamianie…")
        _auto_tick(owner)
    else:
        _cancel_auto_job(owner)
        _set_auto_status(owner, "Automat wyłączony")
        _refresh_auto_pending(owner)


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
    _remember_auto_source(owner, path, persist=True)
    _refresh_auto_pending(owner)
    _show_excel_import_preview(owner, payload)


def _import_excel_plan(owner) -> None:
    path = filedialog.askopenfilename(
        parent=owner.root,
        title="Wybierz zewnętrzny plan produkcji Excel",
        filetypes=(("Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")),
    )
    if path:
        _remember_auto_source(owner, path, persist=True)
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


def _open_excel_sync(owner, *, preselect_safe: bool = False) -> None:
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
    show_excel_sync_preview(owner, payload, preselect_safe=preselect_safe)


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

        state = load_auto_state()
        self._excel_auto_var = tk.BooleanVar(value=bool(state.get("enabled")))
        self._excel_auto_source_path = str(state.get("source_path") or "").strip()
        self._excel_auto_running = False
        self._excel_auto_pending_count = 0
        self._excel_auto_job = None
        self._excel_auto_blink_job = None
        self._excel_manual_buttons = []

        excel_bar = ttk.Frame(parent)
        excel_bar.pack(fill="x", pady=(6, 0))
        ttk.Label(excel_bar, text="Plan zewnętrzny:").pack(side="left")

        import_button = ttk.Button(
            excel_bar,
            text="Wczytaj plan Excel…",
            command=lambda: _import_excel_plan(self),
        )
        import_button.pack(side="left", padx=(6, 4))
        self._excel_manual_buttons.append(import_button)
        add_help_button(excel_bar, _IMPORT_HELP, command_only=False).pack(side="left")

        check_button = ttk.Button(
            excel_bar,
            text="Sprawdź zmiany",
            command=lambda: _check_excel_changes(self),
        )
        check_button.pack(side="left", padx=(12, 4))
        self._excel_manual_buttons.append(check_button)
        add_help_button(excel_bar, _CHECK_HELP, command_only=False).pack(side="left")

        sync_button = ttk.Button(
            excel_bar,
            text="Synchronizuj z WM…",
            command=lambda: _open_excel_sync(self),
        )
        sync_button.pack(side="left", padx=(12, 4))
        self._excel_manual_buttons.append(sync_button)
        add_help_button(excel_bar, _SYNC_HELP, command_only=False).pack(side="left")

        ttk.Label(
            excel_bar,
            text="Ręcznie: analiza i synchronizacja po zatwierdzeniu",
        ).pack(side="left", padx=(10, 0))

        auto_bar = ttk.Frame(parent)
        auto_bar.pack(fill="x", pady=(5, 0))
        ttk.Checkbutton(
            auto_bar,
            text="Niech WM pracuje automatycznie na pliku:",
            variable=self._excel_auto_var,
            command=lambda: _toggle_auto_mode(self),
        ).pack(side="left")
        self._excel_auto_source_label = ttk.Label(
            auto_bar,
            text=(
                Path(self._excel_auto_source_path).name
                if self._excel_auto_source_path
                else "brak wybranego pliku"
            ),
        )
        self._excel_auto_source_label.pack(side="left", padx=(5, 12))

        self._excel_auto_accept_button = tk.Button(
            auto_bar,
            text="Do akceptacji (0)",
            command=lambda: _open_excel_sync(self, preselect_safe=True),
            state="disabled",
            bg="#374151",
            fg="white",
            disabledforeground="#9ca3af",
            disabledbackground="#374151",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self._excel_auto_accept_button.pack(side="left", padx=(0, 10))

        self._excel_auto_status_var = tk.StringVar(
            value="Automat: uruchamianie…" if self._excel_auto_var.get() else "Automat wyłączony"
        )
        ttk.Label(auto_bar, textvariable=self._excel_auto_status_var).pack(side="left")

        self._excel_auto_recount = lambda: _refresh_auto_pending(self)
        _set_manual_excel_controls(self, enabled=not bool(self._excel_auto_var.get()))

        if self._excel_auto_var.get():
            if not self._excel_auto_source_path or not Path(self._excel_auto_source_path).is_file():
                self._excel_auto_var.set(False)
                save_auto_state(enabled=False, source_path=self._excel_auto_source_path)
                _set_manual_excel_controls(self, enabled=True)
                _set_auto_status(self, "Automat wyłączony — brak pliku")
            else:
                self.after(250, lambda: _auto_tick(self))
        return result

    cls._build_orders = build_orders
    cls.import_excel_plan = _import_excel_plan
    cls.check_excel_changes = _check_excel_changes
    cls.open_excel_sync = _open_excel_sync
    cls._show_excel_import_preview = _show_excel_import_preview
    cls.excel_auto_recount = _refresh_auto_pending
    cls._wm_excel_import_runtime = True
