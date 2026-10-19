# WM-VERSION: 0.1
# Plik: gui_planista_panel.py
# version: 1.13
# 1.13: osobne etykiety A5 poziomo, jedna strona i QR na pozycję WM.
# 1.12: podgląd jednego PDF A4 i wspólny druk zbiorczy jednym poleceniem.
# 1.11: kolumna wydruku A4, zbiorcze drukowanie i historia poleceń.
# Planista osadzony w glownym obszarze WM.
# 1.10: kosmetyka kolumny Termin w Zleceniach: DD miesiąca RR zamiast DD-MM-RR.
# 1.9: w tabeli Zleceń Wersja BOM -> Półprodukty z ilością kompletnych zestawów i sygnalizacją kolorem.
# 1.8: wydruk karty korzysta ze wspólnego generatora i zapisuje kopię w aktywnym ROOT WM.
# 1.7: uporządkowano finalny układ tabeli Zleceń; Zamówienie = ilość, przywrócono Wersję BOM.
# 1.6: doprecyzowano Zlecenie warsztatowe, zachowano źródło ID i zwężono kolumnę.
# 1.5: dodano kolumnę Zlecenie wew z istniejącego pola zlec_wew przed numerem zlecenia.
# 1.3: przywrócono dostęp do Produktów, Półproduktów i Surowców bez osobnego dużego okna.

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

import zlecenia_logika as ZL
import zlecenia_progress as ZP
from config_manager import ConfigManager
from planista_auto_print_runtime import dispatch_work_order_print
from planista_batch_print_runtime import dispatch_batch_print, prepare_batch_pdf
from planista_labels_a5_runtime import dispatch_labels_a5_print, prepare_labels_a5_pdf
from planista_print_history import (
    PRINT_CHANGED, PRINT_ERROR, PRINT_NEW, PRINT_PENDING, PRINT_SENT,
    PRINT_STATES, PRINT_UNKNOWN, ensure_print_registry, load_print_history,
    print_events, print_status,
)
from gui_planista import (
    _display_date,
    _iso_date,
    _open_date_calendar,
    _work_order_html,
    _work_order_output_path,
)


def _fmt_qty(value):
    try:
        n = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(n)) if n.is_integer() else f"{n:.3f}".rstrip("0").rstrip(".")


def _fmt_amount(value, unit=""):
    txt = _fmt_qty(value)
    u = str(unit or "").strip()
    if u.lower() == "mm":
        try:
            return f"{txt} mm ({float(value or 0) / 1000:g} m)"
        except Exception:
            pass
    return f"{txt} {u}".strip()


_MONTHS_PL_GENITIVE = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)


def _display_order_date(value) -> str:
    """Tylko prezentacja w tabeli Zleceń: DD miesiąca RR."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = date.fromisoformat(raw[:10])
    except Exception:
        return _display_date(raw)
    return f"{parsed.day:02d} {_MONTHS_PL_GENITIVE[parsed.month - 1]} {parsed.year % 100:02d}"


def _semi_progress_display(order: dict) -> str:
    """Tylko prezentacja: kompletne zestawy półproduktów / ilość zlecenia."""
    try:
        from planista_semi_progress_runtime import proposed_product_completion

        progress = proposed_product_completion(order)
    except Exception:
        return "—"

    if not progress.get("available"):
        return "—"

    planned = max(0.0, float(progress.get("planned") or 0))
    complete = max(0.0, float(progress.get("complete_sets") or 0))
    if planned <= 0:
        return "—"

    if complete <= 0:
        marker = "🔴"
    elif complete + 1e-9 >= planned:
        marker = "🟢"
    else:
        marker = "🟡"

    return f"{marker} {_fmt_qty(complete)}/{_fmt_qty(planned)}"


class PlanistaPanel(ttk.Frame):
    """Planista wraz z kartotekami produkcyjnymi w jednym panelu WM."""

    _CATALOG_TABS = {
        "Produkty": 2,
        "Półprodukty": 1,
        "Surowce": 0,
        "Rodzaje surowców": 3,
    }

    def __init__(self, parent, *, root=None, login=None, rola=None):
        super().__init__(parent, padding=10)
        self.root = root or parent.winfo_toplevel()
        self.login = str(login or "")
        self.rola = str(rola or "")
        self._orders = {}
        self._catalog_hosts = {}
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="PLANISTA", style="WM.H1.TLabel").pack(side="left")
        ttk.Label(
            top,
            text="Zlecenia oraz kartoteki produktów, półproduktów i surowców.",
        ).pack(side="left", padx=18)
        ttk.Button(top, text="Odśwież", command=self.refresh).pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.orders_tab = ttk.Frame(self.nb)
        self.nb.add(self.orders_tab, text="Zlecenia")

        for label in ("Produkty", "Półprodukty", "Surowce", "Rodzaje surowców"):
            host = ttk.Frame(self.nb)
            self.nb.add(host, text=label)
            self._catalog_hosts[label] = host

        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._build_orders(self.orders_tab)

    def _build_orders(self, parent):
        cols = (
            "wybor",
            "zlec_wew",
            "id",
            "produkt",
            "ilosc",
            "polprodukty",
            "wykonano",
            "pozostalo",
            "termin",
            "status",
            "wydruk",
        )
        self.tree = ttk.Treeview(
            parent, columns=cols, show="headings", height=18, selectmode="extended",
        )
        labels = {
            "wybor": "✓",
            "zlec_wew": "Zlecenie wew",
            "id": "Zlecenie warsztatowe",
            "produkt": "Produkt",
            "ilosc": "Zamówienie",
            "polprodukty": "Półprodukty",
            "wykonano": "Wykonano",
            "pozostalo": "Pozostało",
            "termin": "Termin",
            "status": "Status",
            "wydruk": "Wydruk",
        }
        widths = {
            "wybor": 38,
            "zlec_wew": 120,
            "id": 100,
            "produkt": 250,
            "ilosc": 100,
            "polprodukty": 110,
            "wykonano": 90,
            "pozostalo": 90,
            "termin": 150,
            "status": 120,
            "wydruk": 137,
        }
        for col in cols:
            self.tree.heading(col, text=labels[col])
            self.tree.column(
                col,
                width=widths[col],
                anchor="w",
                stretch=col != "id",
            )
        self.tree.pack(fill="both", expand=True)
        self.tree.bind(
            "<Double-1>",
            lambda event: None if self._open_print_history_on_double_click(event) else self.edit_term(),
        )

        buttons = ttk.Frame(parent)
        self._orders_action_bar = buttons
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Ustaw / zmień termin", command=self.edit_term).pack(side="left")
        ttk.Button(buttons, text="Ilość / rzaz / półprodukty…", command=self.edit_production).pack(side="left", padx=6)
        ttk.Button(buttons, text="Wykonano…", command=self.report_done).pack(side="left")
        ttk.Button(buttons, text="Rozlicz materiał", command=self.settle_material).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Pokaż zapotrzebowanie", command=self.show_requirements).pack(side="left", padx=6)
        self.approve_button = ttk.Button(
            buttons,
            text="Akceptuj zlecenie",
            command=self.approve_selected,
        )
        self.approve_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Drukuj A4", command=self.print_work_order).pack(side="left", padx=(8, 0))
        self.tree.bind("<Button-1>", self._toggle_print_selection, add="+")
        self.tree.bind(
            "<<TreeviewSelect>>",
            lambda _e: (self._refresh_approval_button(), self._update_print_checks()),
        )

        print_bar = ttk.Frame(parent)
        print_bar.pack(fill="x", pady=(6, 0))
        ttk.Label(print_bar, text="Wydruki:").pack(side="left")
        self._print_filter_var = tk.StringVar(value="Wszystkie")
        self._print_filter = ttk.Combobox(
            print_bar, state="readonly", width=18, textvariable=self._print_filter_var,
            values=("Wszystkie", "Do wydrukowania", *PRINT_STATES),
        )
        self._print_filter.pack(side="left", padx=(6, 10))
        self._print_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(
            print_bar, text="Podgląd PDF", command=self.preview_selected_orders,
        ).pack(side="left", padx=(0, 7))
        ttk.Button(
            print_bar, text="Drukuj zaznaczone", command=self.print_selected_orders,
        ).pack(side="left", padx=(0, 7))
        ttk.Button(
            print_bar, text="Drukuj niewydrukowane", command=self.print_unprinted_orders,
        ).pack(side="left", padx=(0, 7))
        ttk.Button(
            print_bar, text="Historia wydruków", command=self.show_print_history,
        ).pack(side="left", padx=(0, 7))
        ttk.Label(
            print_bar,
            text="Wysłano ≠ potwierdzenie wydruku na papierze.",
        ).pack(side="left", padx=(9, 0))

        label_bar = ttk.Frame(parent)
        label_bar.pack(fill="x", pady=(5, 0))
        ttk.Label(label_bar, text="Etykiety A5:").pack(side="left")
        ttk.Button(
            label_bar, text="Podgląd etykiet A5", command=self.preview_labels_a5,
        ).pack(side="left", padx=(8, 7))
        ttk.Button(
            label_bar, text="Drukuj etykiety A5", command=self.print_labels_a5,
        ).pack(side="left", padx=(0, 7))
        ttk.Label(
            label_bar,
            text="Jedna etykieta na pozycję WM • duży numer wewnętrzny • osobny QR",
        ).pack(side="left", padx=(7, 0))

    def _on_tab_changed(self, _event=None):
        try:
            label = self.nb.tab(self.nb.select(), "text")
        except Exception:
            return
        if label == "Zlecenia":
            self.refresh()
            return
        if label in self._CATALOG_TABS:
            self._load_catalog(label)

    def _load_catalog(self, label):
        """Ładuje świeżą kartotekę z aktywnego WM data root przy każdym wejściu w zakładkę."""
        host = self._catalog_hosts[label]
        for child in host.winfo_children():
            child.destroy()
        try:
            import gui_magazyn_bom as GMB

            # Stary edytor BOM używał lokalnego DATA_DIR. Przy osadzeniu w Planiscie
            # wymuszamy dokładnie ten sam katalog danych, którego używa bieżący WM.
            GMB.DATA_DIR = Path(ConfigManager().path_data())
            editor = GMB.MagazynBOM(host)
            editor.pack(fill="both", expand=True)

            inner = next(
                (child for child in editor.winfo_children() if isinstance(child, ttk.Notebook)),
                None,
            )
            if inner is not None:
                wanted = self._CATALOG_TABS[label]
                tabs = list(inner.tabs())
                if 0 <= wanted < len(tabs):
                    wanted_id = tabs[wanted]
                    inner.select(wanted_id)
                    for idx, tab_id in enumerate(tabs):
                        if idx != wanted:
                            inner.hide(tab_id)
        except Exception as exc:
            ttk.Label(
                host,
                text=f"Nie udało się otworzyć kartoteki {label}:\n{exc}",
                justify="left",
            ).pack(anchor="nw", padx=12, pady=12)

    def _selected(self):
        selection = self.tree.selection()
        return self._orders.get(selection[0]) if selection else None

    def _refresh_approval_button(self):
        order = self._selected()
        pending = isinstance(order, dict) and str(order.get("status") or "").strip().lower() == "do akceptacji"
        try:
            self.approve_button.configure(
                state=("normal" if pending else "disabled"),
                text=("✓ Akceptuj zlecenie" if pending else "Akceptuj zlecenie"),
            )
        except Exception:
            pass

    def approve_selected(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Akceptacja", "Wybierz zlecenie oczekujące na akceptację.", parent=self)
            return
        if str(order.get("status") or "").strip().lower() != "do akceptacji":
            messagebox.showinfo("Akceptacja", "Wybrane zlecenie nie oczekuje na akceptację.", parent=self)
            return
        if not messagebox.askyesno(
            "Akceptacja zlecenia",
            f"Zaakceptować zlecenie {order.get('id')}?",
            parent=self,
        ):
            return
        try:
            ZL.approve_zlecenie(order["id"], kto=self.login or "system")
        except Exception as exc:
            messagebox.showerror("Akceptacja", f"Nie udało się zaakceptować zlecenia:\n{exc}", parent=self)
            return
        self.refresh()

    def refresh(self):
        if not hasattr(self, "tree"):
            return
        selected = set(self.tree.selection())
        first_y = self.tree.yview()[0] if self.tree.get_children() else 0.0
        orders = list(ZL.list_zlecenia())
        try:
            registry = ensure_print_registry(orders)
        except Exception as exc:
            messagebox.showerror(
                "Historia wydruków",
                f"Nie udało się odczytać rejestru wydruków:\n{exc}",
                parent=self,
            )
            registry = None
        self.tree.delete(*self.tree.get_children())
        self._orders = {}
        mode = (
            self._print_filter_var.get()
            if hasattr(self, "_print_filter_var") else "Wszystkie"
        )
        for order in orders:
            oid = str(order.get("id") or "")
            if not oid:
                continue
            qty = float(order.get("ilosc", 0) or 0)
            done = float(order.get("wykonano", 0) or 0)
            self._orders[oid] = order
            state = print_status(order, registry) if registry is not None else PRINT_UNKNOWN
            if mode == "Do wydrukowania":
                if state not in {PRINT_NEW, PRINT_CHANGED, PRINT_ERROR}:
                    continue
            elif mode != "Wszystkie" and state != mode:
                continue
            self.tree.insert(
                "",
                "end",
                iid=oid,
                values=(
                    "☑" if oid in selected else "☐",
                    order.get("zlec_wew", ""),
                    oid,
                    order.get("produkt", ""),
                    _fmt_qty(qty),
                    _semi_progress_display(order),
                    _fmt_qty(done),
                    _fmt_qty(max(0, qty - done)),
                    _display_order_date(order.get("termin", "")),
                    order.get("status", ""),
                    {
                        PRINT_NEW: "○ Nie drukowano",
                        PRINT_PENDING: "… W kolejce",
                        PRINT_SENT: "✓ Wysłano",
                        PRINT_CHANGED: "↻ Zmieniono",
                        PRINT_ERROR: "✕ Błąd",
                        PRINT_UNKNOWN: "? Brak informacji",
                    }.get(state, state),
                ),
            )
        chosen = [oid for oid in selected if self.tree.exists(oid)]
        if chosen:
            self.tree.selection_set(chosen)
        if self.tree.get_children():
            self.tree.yview_moveto(first_y)
        self._refresh_approval_button()

    def _toggle_print_selection(self, event):
        if self.tree.identify_column(event.x) != "#1":
            return None
        oid = self.tree.identify_row(event.y)
        if not oid:
            return "break"
        if oid in self.tree.selection():
            self.tree.selection_remove(oid)
        else:
            self.tree.selection_add(oid)
        self._update_print_checks()
        return "break"

    def _update_print_checks(self):
        if not hasattr(self, "tree"):
            return
        selected = set(self.tree.selection())
        for oid in self.tree.get_children():
            mark = "☑" if oid in selected else "☐"
            if self.tree.set(oid, "wybor") != mark:
                self.tree.set(oid, "wybor", mark)

    def focus_object(self, order_id: str) -> bool:
        """Zaznacz wskazane zlecenie po przejściu z Dyspozycji."""
        wanted = str(order_id or "").strip()
        if not wanted:
            return False
        if wanted not in self._orders:
            self.refresh()
        if wanted not in self._orders:
            return False
        try:
            self.nb.select(self.orders_tab)
            self.tree.selection_set(wanted)
            self.tree.focus(wanted)
            self.tree.see(wanted)
            self.tree.focus_set()
            self._refresh_approval_button()
            return True
        except Exception:
            return False

    def edit_term(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Termin zlecenia")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Zlecenie: {order.get('id')} | Produkt: {order.get('produkt')}").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        ttk.Label(frm, text="Termin:").grid(row=1, column=0, sticky="w")
        var = tk.StringVar(value=_display_date(order.get("termin")) or date.today().strftime("%d-%m-%y"))
        tk.Entry(
            frm,
            textvariable=var,
            width=16,
            state="readonly",
            readonlybackground="#2e7d32",
            fg="white",
            relief="solid",
            bd=1,
            justify="center",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Button(frm, text="📅 Kalendarz", command=lambda: _open_date_calendar(dlg, var)).grid(
            row=1, column=2, sticky="w", padx=(8, 0)
        )

        def save():
            try:
                ZP.update_zlecenie(
                    order["id"],
                    termin=_iso_date(var.get()),
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Planista", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=2, sticky="e", pady=(10, 0))

    def edit_production(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Parametry zlecenia")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(
            frm,
            text=f"Zlecenie {order.get('id')} — {order.get('produkt')}",
            font=("Arial", 11, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frm, text="Ilość produktu:").grid(row=1, column=0, sticky="w")
        qty = tk.StringVar(value=_fmt_qty(order.get("ilosc", 0)))
        ttk.Entry(frm, textvariable=qty, width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Rzaz na sztukę [mm]:").grid(row=2, column=0, sticky="w")
        cut = tk.StringVar(value=_fmt_qty(order.get("rzaz_mm", 2)))
        ttk.Entry(frm, textvariable=cut, width=10).grid(row=2, column=1, sticky="w")
        ttk.Label(frm, text="Półprodukt").grid(row=3, column=0, sticky="w", pady=(10, 2))
        ttk.Label(frm, text="Wyliczono").grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="Do zlecenia").grid(row=3, column=2, sticky="w")
        variables = {}
        for row, (code, rec) in enumerate((order.get("plan_polprodukty") or {}).items(), start=4):
            if not isinstance(rec, dict):
                continue
            ttk.Label(frm, text=str(rec.get("nazwa") or code)).grid(row=row, column=0, sticky="w", padx=(0, 16))
            ttk.Label(frm, text=_fmt_qty(rec.get("wyliczone", rec.get("potrzeba", 0)))).grid(row=row, column=1, sticky="w")
            var = tk.StringVar(value=_fmt_qty(rec.get("potrzeba", 0)))
            variables[code] = var
            ttk.Entry(frm, textvariable=var, width=12).grid(row=row, column=2, sticky="w", pady=1)

        def save():
            try:
                qty_value = float(qty.get().replace(",", "."))
                cut_value = float(cut.get().replace(",", "."))
                overrides = {key: float(var.get().replace(",", ".")) for key, var in variables.items()}
                if qty_value < 0 or cut_value < 0 or any(value < 0 for value in overrides.values()):
                    raise ValueError("Ilość, rzaz i półprodukty nie mogą być ujemne.")
                ZP.update_zlecenie(
                    order["id"],
                    ilosc=qty_value,
                    rzaz_mm=cut_value,
                    korekty_polproduktow=overrides,
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Planista", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz i przelicz", command=save).grid(row=999, column=2, sticky="e", pady=(12, 0))

    def report_done(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Rozlicz wykonanie")
        dlg.transient(self.root)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        current = float(order.get("wykonano", 0) or 0)
        ttk.Label(frm, text=f"Dotychczas wykonano: {_fmt_qty(current)}").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, text="Nowa łączna ilość wykonana:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        var = tk.StringVar(value=_fmt_qty(current))
        ttk.Entry(frm, textvariable=var, width=16).grid(row=1, column=1, padx=(8, 0), pady=(8, 0))

        def save():
            try:
                ZP.report_wykonano(
                    order["id"],
                    float(var.get().replace(",", ".")),
                    kto=self.login or "system",
                )
            except Exception as exc:
                messagebox.showerror("Rozliczenie", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=1, sticky="e", pady=(10, 0))

    def settle_material(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        done = float(order.get("wykonano", 0) or 0)
        settled = float(order.get("materialy_rozliczono_do", 0) or 0)
        if done <= settled:
            messagebox.showinfo(
                "Rozliczenie materiału",
                "Nie ma nowego wykonania do rozliczenia.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Rozliczenie materiału",
            f"Rozliczyć materiał dla wykonania od {_fmt_qty(settled)} do {_fmt_qty(done)} szt.?\n"
            "Ta operacja zmieni stan i rezerwacje magazynu.",
            parent=self,
        ):
            return
        try:
            ZP.rozlicz_material(order["id"], kto=self.login or "system")
        except Exception as exc:
            messagebox.showerror("Rozliczenie materiału", str(exc), parent=self)
            return
        self.refresh()

    def show_requirements(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        lines = []
        for code, rec in (order.get("plan_polprodukty") or {}).items():
            if isinstance(rec, dict):
                lines.append(
                    f"{rec.get('nazwa') or code}: potrzeba {_fmt_qty(rec.get('potrzeba', 0))} | "
                    f"z magazynu {_fmt_qty(rec.get('z_magazynu', 0))} | "
                    f"do wykonania {_fmt_qty(rec.get('do_wykonania', 0))}"
                )
        raw = order.get("zapotrzebowanie_surowce") or {}
        if raw:
            lines += ["", "SUROWIEC:"] + [
                f"{code}: {_fmt_amount(rec.get('ilosc', 0), rec.get('jednostka', ''))}"
                for code, rec in raw.items()
                if isinstance(rec, dict)
            ]
        if order.get("braki"):
            lines += ["", "BRAKI SUROWCA:"] + [
                f"{rec.get('nazwa') or rec.get('kod')}: brakuje {_fmt_amount(rec.get('brakuje', 0), rec.get('jednostka', ''))}"
                for rec in order["braki"]
            ]
        messagebox.showinfo("Zapotrzebowanie", "\n".join(lines) if lines else "Brak danych.", parent=self)

    def print_work_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        status = print_status(order)
        if status in {PRINT_SENT, PRINT_PENDING}:
            if not messagebox.askyesno(
                "Ponowny wydruk",
                f"Zlecenie {order['id']} ma status „{status}”. Wysłać ponownie?",
                parent=self,
            ):
                return
        self._print_orders([str(order["id"])], single=True)

    def preview_selected_orders(self):
        order_ids = self._selected_ids_for_pdf()
        if not order_ids:
            messagebox.showinfo(
                "Podgląd PDF", "Zaznacz zlecenia w kolumnie ✓.", parent=self,
            )
            return
        self._print_orders(order_ids, preview=True)

    def preview_labels_a5(self):
        order_ids = self._selected_ids_for_pdf()
        if not order_ids:
            messagebox.showinfo(
                "Etykiety A5", "Zaznacz pozycje na liście zleceń.", parent=self,
            )
            return
        self._print_orders(order_ids, preview=True, labels=True)

    def print_labels_a5(self):
        order_ids = self._selected_ids_for_pdf()
        if not order_ids:
            messagebox.showinfo(
                "Etykiety A5", "Zaznacz pozycje na liście zleceń.", parent=self,
            )
            return
        if not messagebox.askyesno(
            "Drukuj etykiety A5",
            f"Przygotować jeden PDF z {len(order_ids)} etykietami A5 poziomo "
            "i wysłać go do drukarki?\n\n"
            "Każda pozycja otrzyma własny QR. "
            "Drukowanie etykiet nie zmienia statusów kart A4.",
            parent=self,
        ):
            return
        self._print_orders(order_ids, labels=True)

    def _selected_ids_for_pdf(self):
        # Zachowaj kolejność zleceń z tabeli na stronach PDF.
        selected = set(self.tree.selection())
        return [oid for oid in self.tree.get_children() if oid in selected]

    def print_selected_orders(self):
        order_ids = self._selected_ids_for_pdf()
        if not order_ids:
            messagebox.showinfo(
                "Drukowanie zbiorcze", "Zaznacz zlecenia w kolumnie ✓.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Drukowanie zbiorcze A4",
            f"Połączyć {len(order_ids)} kart A4 w jeden PDF i wysłać "
            "jedno polecenie drukowania do Windows?\n\n"
            "Zlecenia już drukowane będą drukowane ponownie.",
            parent=self,
        ):
            return
        self._print_orders(order_ids)

    def print_unprinted_orders(self):
        try:
            registry = load_print_history()
        except Exception as exc:
            messagebox.showerror("Wydruki", str(exc), parent=self)
            return
        order_ids = [
            oid for oid in self.tree.get_children()
            if print_status(self._orders[oid], registry) == PRINT_NEW
        ]
        if not order_ids:
            messagebox.showinfo(
                "Drukowanie zbiorcze",
                "Brak zleceń ze statusem „Nie drukowano” w bieżącym widoku. "
                "Historyczne „Brak informacji” można zaznaczyć i wydrukować ręcznie.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Drukowanie niewydrukowanych A4",
            f"Połączyć {len(order_ids)} niewydrukowanych kart A4 "
            "w jeden PDF i wysłać jedno polecenie drukowania?\n\n"
            "Każde zlecenie zostanie sprawdzone ponownie.",
            parent=self,
        ):
            return
        self._print_orders(order_ids, only_unprinted=True)

    def _print_orders(
        self, order_ids, *, only_unprinted=False, preview=False, single=False,
        labels=False,
    ):
        """Zbiorczo: najpierw jeden PDF, później jedno polecenie drukowania."""
        if getattr(self, "_print_job_active", False):
            messagebox.showinfo(
                "Drukowanie", "Trwa przygotowanie lub wydruk poprzedniego PDF.",
                parent=self,
            )
            return
        orders = [
            dict(self._orders[oid]) for oid in dict.fromkeys(order_ids)
            if oid in self._orders
        ]
        if not orders:
            return
        self._print_job_active = True
        responses = queue.Queue()
        username = self.login or "brygadzista"

        def worker():
            try:
                filtered = []
                for order in orders:
                    if only_unprinted and print_status(order) != PRINT_NEW:
                        continue
                    filtered.append(order)
                if not filtered:
                    responses.put(("pominięto", [], "", "Nie ma już niewydrukowanych kart."))
                    return
                ids = [str(order["id"]) for order in filtered]
                if labels:
                    if preview:
                        path = prepare_labels_a5_pdf(filtered)
                        responses.put(("podgląd_etykiet", ids, str(path), ""))
                    else:
                        path = dispatch_labels_a5_print(filtered)
                        responses.put(("wysłano_etykiety", ids, str(path), ""))
                elif preview:
                    path = prepare_batch_pdf(filtered)
                    responses.put(("podgląd", ids, str(path), ""))
                elif single:
                    # Pojedyncza karta zachowuje dotychczasową obsługę.
                    responses.put(("kolejka", ids, "", ""))
                    path = dispatch_work_order_print(
                        filtered[0], user=username, source="Planista – pojedyncze A4",
                    )
                    responses.put(("wysłano_pojedynczo", ids, str(path), ""))
                else:
                    responses.put(("kolejka", ids, "", ""))
                    path = dispatch_batch_print(
                        filtered, user=username, source="Planista – zbiorczy PDF",
                    )
                    responses.put(("wysłano", ids, str(path), ""))
            except Exception as exc:
                responses.put(("błąd_etykiet" if labels else "błąd", [], "", str(exc)))
            finally:
                responses.put(("koniec", [], "", ""))

        threading.Thread(target=worker, daemon=True).start()
        outcome = {"status": "", "ids": [], "path": "", "error": ""}

        def poll():
            while True:
                try:
                    kind, ids, pdf_path, details = responses.get_nowait()
                except queue.Empty:
                    break
                if kind == "kolejka":
                    for oid in ids:
                        if self.tree.exists(oid):
                            self.tree.set(oid, "wydruk", "… W kolejce")
                elif kind == "koniec":
                    self._print_job_active = False
                    self.refresh()
                    if outcome["status"] in {"podgląd", "podgląd_etykiet"}:
                        try:
                            if os.name == "nt":
                                os.startfile(outcome["path"])
                            else:
                                import webbrowser
                                webbrowser.open(Path(outcome["path"]).as_uri())
                        except Exception as exc:
                            messagebox.showerror(
                                "Podgląd PDF",
                                f"PDF został zapisany, ale nie można go otworzyć:\n"
                                f"{outcome['path']}\n{exc}",
                                parent=self,
                            )
                    elif outcome["status"] == "wysłano_etykiety":
                        messagebox.showinfo(
                            "Etykiety A5",
                            f"Wysłano jeden dokument PDF do drukarki.\n"
                            f"Liczba etykiet A5: {len(outcome['ids'])}\n"
                            f"Plik: {outcome['path']}\n\n"
                            "Statusy wydruków kart A4 pozostały bez zmian.",
                            parent=self,
                        )
                    elif outcome["status"] == "wysłano_pojedynczo":
                        messagebox.showinfo(
                            "Wydruk A4",
                            f"Zlecenie {outcome['ids'][0]} wysłano do drukarki Windows.",
                            parent=self,
                        )
                    elif outcome["status"] == "wysłano":
                        messagebox.showinfo(
                            "Wydruk zbiorczy A4",
                            f"Wysłano jeden PDF do systemowej obsługi drukowania.\n"
                            f"Karty zleceń: {len(outcome['ids'])}\n"
                            f"Plik: {outcome['path']}\n\n"
                            "Status „Wysłano” nie potwierdza wydruku na papierze.",
                            parent=self,
                        )
                    elif outcome["status"] == "pominięto":
                        messagebox.showinfo(
                            "Drukowanie zbiorcze", outcome["error"], parent=self,
                        )
                    elif outcome["status"] == "błąd_etykiet":
                        messagebox.showerror(
                            "Etykiety A5",
                            f"Nie udało się przygotować lub wydrukować etykiet:\n"
                            f"{outcome['error']}",
                            parent=self,
                        )
                    elif outcome["status"] == "błąd":
                        messagebox.showerror(
                            "Wydruk zbiorczy A4",
                            f"Nie udało się przygotować lub wysłać PDF:\n"
                            f"{outcome['error']}\n\n"
                            "Jeżeli PDF został już zapisany, można go "
                            "otworzyć z katalogu zlecenia/karty/zbiorcze.",
                            parent=self,
                        )
                    return
                else:
                    outcome["status"] = kind
                    outcome["ids"] = ids
                    outcome["path"] = pdf_path
                    outcome["error"] = details
            if self.winfo_exists():
                self.after(350, poll)

        self.after(150, poll)

    def _open_print_history_on_double_click(self, event) -> bool:
        last_column = f"#{len(self.tree['columns'])}"
        if self.tree.identify_column(event.x) != last_column:
            return False
        oid = self.tree.identify_row(event.y)
        if oid and self.tree.exists(oid):
            self.tree.selection_set(oid)
            self.show_print_history()
        return True

    def show_print_history(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(
                "Historia wydruków", "Wybierz zlecenie na liście.", parent=self,
            )
            return
        oid = str(selected[0])
        order = self._orders.get(oid)
        if order is None:
            return
        try:
            registry = load_print_history()
            events = print_events(oid, registry)
            status = print_status(order, registry)
        except Exception as exc:
            messagebox.showerror("Historia wydruków", str(exc), parent=self)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Historia wydruków — zlecenie {oid}")
        dlg.geometry("860x420")
        dlg.transient(self.root)
        body = ttk.Frame(dlg, padding=12)
        body.pack(fill="both", expand=True)
        sent = sum(1 for event in events if event.get("stan") == PRINT_SENT)
        versions = list(dict.fromkeys(
            str(event.get("wersja") or "")
            for event in events
            if event.get("stan") == PRINT_SENT and event.get("wersja")
        ))
        ttk.Label(
            body,
            text=(
                f"Zlecenie {oid}  |  Status: {status}  |  "
                f"Wysłano: {sent} razy  |  Wersji karty: {len(versions)}"
            ),
        ).pack(anchor="w", pady=(0, 10))
        columns = ("czas", "stan", "uzytkownik", "zrodlo", "szczegoly")
        table = ttk.Treeview(body, columns=columns, show="headings")
        names = {
            "czas": "Data i godzina", "stan": "Status",
            "uzytkownik": "Użytkownik", "zrodlo": "Źródło",
            "szczegoly": "Metoda / komunikat",
        }
        widths = {"czas": 185, "stan": 110, "uzytkownik": 110, "zrodlo": 160, "szczegoly": 290}
        for col in columns:
            table.heading(col, text=names[col])
            table.column(col, width=widths[col])
        for index, event in enumerate(reversed(events)):
            table.insert(
                "", "end", iid=str(index),
                values=tuple(event.get(col, "") for col in columns),
            )
        table.pack(fill="both", expand=True)
        if not events:
            ttk.Label(
                body,
                text="Nie zarejestrowano zdarzeń. Starsze wydruki mogły odbywać "
                "się przed wprowadzeniem historii.",
            ).pack(anchor="w", pady=10)
        ttk.Button(body, text="Zamknij", command=dlg.destroy).pack(
            side="right", pady=(9, 0),
        )


def panel_planista(root, frame, login=None, rola=None):
    panel = PlanistaPanel(frame, root=root, login=login, rola=rola)
    panel.pack(fill="both", expand=True)
    return panel
