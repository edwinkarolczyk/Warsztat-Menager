# WM-VERSION: 0.1
# Plik: gui_planista.py
# version: 1.0
# Planista: prosty termin realizacji zleceń produkcyjnych.

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date

import zlecenia_logika as ZL


def _fmt_qty(value):
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


class PlanistaWindow:
    def __init__(self, root, login=None, rola=None):
        self.root = root
        self.login = str(login or "")
        self.rola = str(rola or "")
        self.win = tk.Toplevel(root)
        self.win.title("Planista")
        self.win.geometry("1050x640")
        self.win.minsize(850, 480)
        self._orders = {}
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self.win, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="PLANISTA", font=("Arial", 15, "bold")).pack(side="left")
        ttk.Label(top, text="Ustawia tylko termin realizacji. Zlecenie określa co i ile wykonać.").pack(side="left", padx=18)
        ttk.Button(top, text="Odśwież", command=self.refresh).pack(side="right")

        cols = ("id", "produkt", "ilosc", "wykonano", "pozostalo", "termin", "status")
        self.tree = ttk.Treeview(self.win, columns=cols, show="headings", height=18)
        labels = {"id": "Zlecenie", "produkt": "Produkt", "ilosc": "Ilość", "wykonano": "Wykonano", "pozostalo": "Pozostało", "termin": "Termin", "status": "Status"}
        widths = {"id": 110, "produkt": 240, "ilosc": 80, "wykonano": 90, "pozostalo": 90, "termin": 120, "status": 120}
        for col in cols:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda _e: self.edit_term())

        bottom = ttk.Frame(self.win, padding=(10, 4, 10, 10))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Ustaw / zmień termin", command=self.edit_term).pack(side="left")
        ttk.Button(bottom, text="Wykonano…", command=self.report_done).pack(side="left", padx=6)
        ttk.Button(bottom, text="Pokaż zapotrzebowanie", command=self.show_requirements).pack(side="left")
        ttk.Button(bottom, text="Zamknij", command=self.win.destroy).pack(side="right")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._orders.get(sel[0])

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
            self.tree.insert("", "end", iid=oid, values=(oid, order.get("produkt", ""), _fmt_qty(qty), _fmt_qty(done), _fmt_qty(left), order.get("termin", ""), order.get("status", "")))

    def edit_term(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win)
            return
        dlg = tk.Toplevel(self.win)
        dlg.title("Termin zlecenia")
        dlg.transient(self.win)
        dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Zlecenie: {order.get('id')} | Produkt: {order.get('produkt')}").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(frm, text="Termin (YYYY-MM-DD):").grid(row=1, column=0, sticky="w")
        var = tk.StringVar(value=str(order.get("termin") or date.today().isoformat()))
        ent = ttk.Entry(frm, textvariable=var, width=20)
        ent.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        ent.focus_set()

        def save():
            try:
                ZL.update_zlecenie(order["id"], termin=var.get().strip(), kto=self.login or "system")
            except Exception as exc:
                messagebox.showerror("Planista", str(exc), parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=1, sticky="e", pady=(10, 0))

    def report_done(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win)
            return
        dlg = tk.Toplevel(self.win)
        dlg.title("Rozlicz wykonanie")
        dlg.transient(self.win)
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
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win)
            return
        plan = order.get("plan_polprodukty") or {}
        lines = []
        for code, rec in plan.items():
            if not isinstance(rec, dict):
                continue
            lines.append(f"{rec.get('nazwa') or code}: potrzeba {_fmt_qty(rec.get('potrzeba', rec.get('ilosc', 0)))} | z magazynu {_fmt_qty(rec.get('z_magazynu', 0))} | do wykonania {_fmt_qty(rec.get('do_wykonania', rec.get('ilosc', 0)))}")
        braki = order.get("braki") or []
        if braki:
            lines.append("")
            lines.append("BRAKI SUROWCA:")
            for rec in braki:
                lines.append(f"{rec.get('nazwa') or rec.get('kod')}: brakuje {_fmt_qty(rec.get('brakuje', 0))} {rec.get('jednostka', '')}")
        messagebox.showinfo("Zapotrzebowanie", "\n".join(lines) if lines else "Brak danych.", parent=self.win)


def open_planista(root, login=None, rola=None):
    return PlanistaWindow(root, login=login, rola=rola)
