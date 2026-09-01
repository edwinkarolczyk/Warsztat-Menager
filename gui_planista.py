# WM-VERSION: 0.1
# Plik: gui_planista.py
# version: 1.1
# Zmiany 1.1:
# - dodano małe zlecenie warsztatowe A5 z podglądem w przeglądarce;
# - wydruk zawiera półprodukty: potrzeba / z magazynu / do wykonania i operacje.

from __future__ import annotations

import html
import os
import tempfile
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

import zlecenia_logika as ZL


def _fmt_qty(value):
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _work_order_html(order):
    rows = []
    for code, rec in (order.get("plan_polprodukty") or {}).items():
        if not isinstance(rec, dict):
            continue
        operations = " → ".join(str(x) for x in (rec.get("czynnosci") or []) if str(x).strip()) or "—"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(rec.get('nazwa') or code))}</td>"
            f"<td>{html.escape(_fmt_qty(rec.get('potrzeba', rec.get('ilosc', 0))))}</td>"
            f"<td>{html.escape(_fmt_qty(rec.get('z_magazynu', 0)))}</td>"
            f"<td><b>{html.escape(_fmt_qty(rec.get('do_wykonania', rec.get('ilosc', 0))))}</b></td>"
            f"<td>{html.escape(operations)}</td>"
            "</tr>"
        )
    shortage_rows = []
    for rec in order.get("braki") or []:
        shortage_rows.append(
            f"<li>{html.escape(str(rec.get('nazwa') or rec.get('kod') or ''))}: "
            f"brakuje <b>{html.escape(_fmt_qty(rec.get('brakuje', 0)))} {html.escape(str(rec.get('jednostka') or ''))}</b></li>"
        )
    shortage_block = ""
    if shortage_rows:
        shortage_block = "<div class='warn'><b>Braki surowca / do zamówienia</b><ul>" + "".join(shortage_rows) + "</ul></div>"
    return f"""<!doctype html>
<html lang='pl'><head><meta charset='utf-8'><title>Zlecenie {html.escape(str(order.get('id') or ''))}</title>
<style>
@page {{ size: A5 portrait; margin: 8mm; }}
body {{ font-family: Arial, sans-serif; font-size: 10pt; color:#111; margin:0; }}
h1 {{ font-size:16pt; margin:0 0 5mm; }}
.meta {{ display:grid; grid-template-columns:1fr 1fr; gap:2mm 8mm; margin-bottom:5mm; }}
table {{ width:100%; border-collapse:collapse; font-size:9pt; }}
th,td {{ border:1px solid #555; padding:2.2mm; vertical-align:top; }}
th {{ background:#eee; }}
.warn {{ margin-top:4mm; border:2px solid #b33; padding:2mm; }}
.notes {{ margin-top:5mm; min-height:18mm; border:1px solid #777; padding:2mm; }}
.small {{ font-size:8pt; color:#555; }}
</style></head><body>
<h1>ZLECENIE DO WYKONANIA</h1>
<div class='meta'>
<div><b>Zlecenie:</b> {html.escape(str(order.get('id') or ''))}</div>
<div><b>Termin:</b> {html.escape(str(order.get('termin') or '—'))}</div>
<div><b>Produkt:</b> {html.escape(str(order.get('produkt') or ''))}</div>
<div><b>Ilość:</b> {html.escape(_fmt_qty(order.get('ilosc', 0)))}</div>
<div><b>Wykonano:</b> {html.escape(_fmt_qty(order.get('wykonano', 0)))}</div>
<div><b>Rzaz:</b> {html.escape(_fmt_qty(order.get('rzaz_mm', 2)))} mm / cięcie</div>
</div>
<table><thead><tr><th>Półprodukt</th><th>Potrzeba</th><th>Z magazynu</th><th>Do wykonania</th><th>Operacje</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="5">Brak półproduktów</td></tr>'}</tbody></table>
{shortage_block}
<div class='notes'><b>Uwagi:</b><br>{html.escape(str(order.get('uwagi') or ''))}</div>
<p class='small'>Warsztat Menager — karta robocza. Wydrukuj z przeglądarki w formacie A5.</p>
<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),250));</script>
</body></html>"""


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
        ttk.Button(bottom, text="Drukuj małe zlecenie", command=self.print_work_order).pack(side="left", padx=6)
        ttk.Button(bottom, text="Zamknij", command=self.win.destroy).pack(side="right")

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
            qty, done = float(order.get("ilosc", 0) or 0), float(order.get("wykonano", 0) or 0)
            left = max(0.0, qty - min(qty, done))
            self._orders[oid] = order
            self.tree.insert("", "end", iid=oid, values=(oid, order.get("produkt", ""), _fmt_qty(qty), _fmt_qty(done), _fmt_qty(left), order.get("termin", ""), order.get("status", "")))

    def edit_term(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win); return
        dlg = tk.Toplevel(self.win); dlg.title("Termin zlecenia"); dlg.transient(self.win); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Zlecenie: {order.get('id')} | Produkt: {order.get('produkt')}").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(frm, text="Termin (YYYY-MM-DD):").grid(row=1, column=0, sticky="w")
        var = tk.StringVar(value=str(order.get("termin") or date.today().isoformat()))
        ent = ttk.Entry(frm, textvariable=var, width=20); ent.grid(row=1, column=1, sticky="ew", padx=(8, 0)); ent.focus_set()
        def save():
            try: ZL.update_zlecenie(order["id"], termin=var.get().strip(), kto=self.login or "system")
            except Exception as exc: messagebox.showerror("Planista", str(exc), parent=dlg); return
            dlg.destroy(); self.refresh()
        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=1, sticky="e", pady=(10, 0))

    def report_done(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win); return
        dlg = tk.Toplevel(self.win); dlg.title("Rozlicz wykonanie"); dlg.transient(self.win); dlg.grab_set()
        frm = ttk.Frame(dlg, padding=12); frm.pack(fill="both", expand=True)
        current = float(order.get("wykonano", 0) or 0)
        ttk.Label(frm, text=f"Dotychczas wykonano: {_fmt_qty(current)}").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, text="Nowa łączna ilość wykonana:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        var = tk.StringVar(value=_fmt_qty(current)); ttk.Entry(frm, textvariable=var, width=16).grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        def save():
            try: ZL.report_wykonano(order["id"], float(var.get().replace(",", ".")), kto=self.login or "system")
            except Exception as exc: messagebox.showerror("Rozliczenie", str(exc), parent=dlg); return
            dlg.destroy(); self.refresh()
        ttk.Button(frm, text="Zapisz", command=save).grid(row=2, column=1, sticky="e", pady=(10, 0))

    def show_requirements(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win); return
        lines = []
        for code, rec in (order.get("plan_polprodukty") or {}).items():
            if isinstance(rec, dict):
                lines.append(f"{rec.get('nazwa') or code}: potrzeba {_fmt_qty(rec.get('potrzeba', rec.get('ilosc', 0)))} | z magazynu {_fmt_qty(rec.get('z_magazynu', 0))} | do wykonania {_fmt_qty(rec.get('do_wykonania', rec.get('ilosc', 0)))}")
        if order.get("braki"):
            lines += ["", "BRAKI SUROWCA:"]
            for rec in order["braki"]:
                lines.append(f"{rec.get('nazwa') or rec.get('kod')}: brakuje {_fmt_qty(rec.get('brakuje', 0))} {rec.get('jednostka', '')}")
        messagebox.showinfo("Zapotrzebowanie", "\n".join(lines) if lines else "Brak danych.", parent=self.win)

    def print_work_order(self):
        order = self._selected()
        if not order:
            messagebox.showinfo("Planista", "Wybierz zlecenie.", parent=self.win); return
        try:
            out_dir = Path(tempfile.gettempdir()) / "WarsztatMenager" / "wydruki"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"zlecenie_{order.get('id','')}.html"
            path.write_text(_work_order_html(order), encoding="utf-8")
            if os.name == "nt":
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror("Wydruk", f"Nie udało się przygotować wydruku:\n{exc}", parent=self.win)


def open_planista(root, login=None, rola=None):
    return PlanistaWindow(root, login=login, rola=rola)
