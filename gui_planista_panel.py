# WM-VERSION: 0.1
# Plik: gui_planista_panel.py
# version: 1.0
# Osadzony widok Planisty dla glownego obszaru Warsztat Menager.

from __future__ import annotations

import os
import tempfile
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

import zlecenia_logika as ZL
from gui_planista import _display_date, _iso_date, _open_date_calendar, _work_order_html


def _fmt_qty(value):
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


class PlanistaPanel(ttk.Frame):
    """Planista osadzony w prawym panelu glownego okna WM."""

    def __init__(self, parent, *, root=None, login=None, rola=None):
        super().__init__(parent, padding=10)
        self.root = root or parent.winfo_toplevel()
        self.login = str(login or "")
        self.rola = str(rola or "")
        self._orders = {}
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="PLANISTA", style="WM.H1.TLabel").pack(side="left")
        ttk.Label(
            top,
            text="Termin realizacji zlecenia. Zlecenie określa co i ile wykonać.",
        ).pack(side="left", padx=18)
        ttk.Button(top, text="Odśwież", command=self.refresh).pack(side="right")

        cols = ("id", "produkt", "ilosc", "wykonano", "pozostalo", "termin", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        labels = {
            "id": "Zlecenie", "produkt": "Produkt", "ilosc": "Ilość",
            "wykonano": "Wykonano", "pozostalo": "Pozostało",
            "termin": "Termin", "status": "Status",
        }
        widths = {"id": 110, "produkt": 250, "ilosc": 80, "wykonano": 90,
                  "pozostalo": 90, "termin": 120, "status": 120}
        for col in cols:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit_term())

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Ustaw / zmień termin", command=self.edit_term).pack(side="left")
        ttk.Button(bottom, text="Wykonano…", command=self.report_done).pack(side="left", padx=6)
        ttk.Button(bottom, text="Pokaż zapotrzebowanie", command=self.show_requirements).pack(side="left")
        ttk.Button(bottom, text="Drukuj małe zlecenie", command=self.print_work_order).pack(side="left", padx=6)

    def _selected(self):
        sel = self.tree.selection()
        return self._orders.get(sel[0]) if sel else None

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._orders = {}
        for order in ZL.list_zlecenia():
            oid = str(order.get("id") or "")
            if not oid:
                continue
            qty = float(order.get("ilosc", 0) or 0)
            done = float(order.get("wykonano", 0) or 0)
            left = max(0.0, qty - min(qty, done))
            self._orders[oid] = order
            self.tree.insert("", "end", iid=oid, values=(
                oid, order.get("produkt", ""), _fmt_qty(qty), _fmt_qty(done),
                _fmt_qty(left), _display_date(order.get("termin", "")), order.get("status", ""),
            ))

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
        ent = tk.Entry(frm, textvariable=var, width=16, state="readonly",
                       readonlybackground="#2e7d32", fg="white", relief="solid", bd=1,
                       justify="center")
        ent.grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Button(frm, text="📅 Kalendarz", command=lambda: _open_date_calendar(dlg, var)).grid(
            row=1, column=2, sticky="w", padx=(8, 0)
        )

        def save():
            try:
                ZL.update_zlecenie(order["id"], termin=_iso_date(var.get()), kto=self.login or "system")
            except Exception as exc:
                messagebox.showerror("Planista", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=2, sticky="e", pady=(10, 0))

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
                ZL.report_wykonano(order["id"], float(var.get().replace(",", ".")), kto=self.login or "system")
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
                    f"{rec.get('nazwa') or code}: potrzeba {_fmt_qty(rec.get('potrzeba', rec.get('ilosc', 0)))} | "
                    f"z magazynu {_fmt_qty(rec.get('z_magazynu', 0))} | "
                    f"do wykonania {_fmt_qty(rec.get('do_wykonania', rec.get('ilosc', 0)))}"
                )
        if order.get("braki"):
            lines += ["", "BRAKI SUROWCA:"]
            for rec in order["braki"]:
                lines.append(f"{rec.get('nazwa') or rec.get('kod')}: brakuje {_fmt_qty(rec.get('brakuje', 0))} {rec.get('jednostka', '')}")
        messagebox.showinfo("Zapotrzebowanie", "\n".join(lines) if lines else "Brak danych.", parent=self)

    def print_work_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self)
            return
        try:
            out_dir = Path(tempfile.gettempdir()) / "WarsztatMenager" / "wydruki"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"zlecenie_{order.get('id', '')}.html"
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
