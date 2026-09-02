# WM-VERSION: 0.1
# Plik: gui_planista_panel.py
# version: 1.4
# Planista osadzony w glownym obszarze WM.
# 1.3: przywrócono dostęp do Produktów, Półproduktów i Surowców bez osobnego dużego okna.

from __future__ import annotations

import os
import tempfile
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

import zlecenia_logika as ZL
import zlecenia_progress as ZP
from config_manager import ConfigManager
from gui_planista import _display_date, _iso_date, _open_date_calendar, _work_order_html


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
        cols = ("id", "produkt", "ilosc", "wykonano", "pozostalo", "termin", "status")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        labels = {
            "id": "Zlecenie",
            "produkt": "Produkt",
            "ilosc": "Ilość",
            "wykonano": "Wykonano",
            "pozostalo": "Pozostało",
            "termin": "Termin",
            "status": "Status",
        }
        widths = {
            "id": 110,
            "produkt": 250,
            "ilosc": 80,
            "wykonano": 90,
            "pozostalo": 90,
            "termin": 120,
            "status": 120,
        }
        for col in cols:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit_term())

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Ustaw / zmień termin", command=self.edit_term).pack(side="left")
        ttk.Button(buttons, text="Ilość / rzaz / półprodukty…", command=self.edit_production).pack(side="left", padx=6)
        ttk.Button(buttons, text="Wykonano…", command=self.report_done).pack(side="left")
        ttk.Button(buttons, text="Pokaż zapotrzebowanie", command=self.show_requirements).pack(side="left", padx=6)
        ttk.Button(buttons, text="Drukuj małe zlecenie", command=self.print_work_order).pack(side="left")

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

    def refresh(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        self._orders = {}
        for order in ZL.list_zlecenia():
            oid = str(order.get("id") or "")
            if not oid:
                continue
            qty = float(order.get("ilosc", 0) or 0)
            done = float(order.get("wykonano", 0) or 0)
            self._orders[oid] = order
            self.tree.insert(
                "",
                "end",
                iid=oid,
                values=(
                    oid,
                    order.get("produkt", ""),
                    _fmt_qty(qty),
                    _fmt_qty(done),
                    _fmt_qty(max(0, qty - done)),
                    _display_date(order.get("termin", "")),
                    order.get("status", ""),
                ),
            )

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
        try:
            folder = Path(tempfile.gettempdir()) / "WarsztatMenager" / "wydruki"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"zlecenie_{order.get('id', '')}.html"
            path.write_text(_work_order_html(order), encoding="utf-8")
            if os.name == "nt":
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror("Wydruk", f"Nie udało się przygotować wydruku:\n{exc}", parent=self)


def panel_planista(root, frame, login=None, rola=None):
    panel = PlanistaPanel(frame, root=root, login=login, rola=rola)
    panel.pack(fill="both", expand=True)
    return panel
