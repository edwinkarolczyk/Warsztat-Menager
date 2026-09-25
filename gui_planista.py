# WM-VERSION: 0.1
# Plik: gui_planista.py
# version: 1.6
# Zmiany 1.6:
# - doprecyzowano, że kolumna rezerwacji surowca pochodzi z Magazynu i dotyczy bieżącego zlecenia.
# Zmiany 1.5:
# - operacje na karcie do druku mają osobne pola do ręcznego odhaczania;
# - karta używa określenia „Grubość piły/taśmy” zamiast technicznego „rzaz”.
# Zmiany 1.4:
# - karta pokazuje standardową długość sztangi i liczbę sztang potrzebnych do cięcia;
# - wartości liniowe w mm pokazują też metry, a opis rzazu wyjaśnia jego znaczenie.
# Zmiany 1.3:
# - karta zlecenia pokazuje surowiec i normę zużycia na sztukę oraz łączne zapotrzebowanie;
# - wydruk jest archiwizowany w aktywnym WM_ROOT/data/zlecenia/karty zamiast w TEMP.
# Zmiany 1.2:
# - termin zlecenia wybierany z kalendarza zamiast ręcznego wpisywania;
# - pole terminu jest tylko do odczytu i ma zielone oznaczenie;
# - użytkownik widzi DD-MM-RR, a do danych nadal trafia YYYY-MM-DD.
# Zmiany 1.1:
# - dodano małe zlecenie warsztatowe A5 z podglądem w przeglądarce;
# - wydruk zawiera półprodukty: potrzeba / z magazynu / do wykonania i operacje.

from __future__ import annotations

import calendar
import html
import os
import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

import zlecenia_logika as ZL
from core.root_paths import get_data_root


def _fmt_qty(value):
    try:
        number = float(value or 0)
    except Exception:
        return str(value or "")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _fmt_linear(value, unit=""):
    txt = _fmt_qty(value)
    u = str(unit or "").strip()
    if u.lower() in {"mm", "milimetr", "milimetry", "milimetrów"}:
        try:
            meters = float(value or 0) / 1000.0
            return f"{txt} mm ({_fmt_qty(meters)} m)"
        except Exception:
            pass
    return f"{txt} {u}".strip()


def _display_date(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y"):
        try:
            return __import__("datetime").datetime.strptime(raw, fmt).strftime("%d-%m-%y")
        except ValueError:
            continue
    return raw


def _iso_date(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return __import__("datetime").datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Termin musi być wybrany z kalendarza.")


def _open_date_calendar(parent, variable):
    try:
        initial_iso = _iso_date(variable.get())
        initial = date.fromisoformat(initial_iso) if initial_iso else date.today()
    except Exception:
        initial = date.today()

    picker = tk.Toplevel(parent)
    picker.title("Wybierz termin")
    picker.resizable(False, False)
    picker.transient(parent)
    picker.grab_set()

    state = {"year": initial.year, "month": initial.month}
    month_names = [
        "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
        "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
    ]

    top = ttk.Frame(picker, padding=(10, 10, 10, 4))
    top.pack(fill="x")
    title_var = tk.StringVar()
    body = ttk.Frame(picker, padding=(10, 4, 10, 10))
    body.pack(fill="both", expand=True)

    def close_picker():
        try:
            picker.grab_release()
        except Exception:
            pass
        picker.destroy()
        try:
            parent.grab_set()
        except Exception:
            pass

    def pick_day(day):
        chosen = date(state["year"], state["month"], int(day))
        variable.set(chosen.strftime("%d-%m-%y"))
        close_picker()

    def render_month():
        for child in body.winfo_children():
            child.destroy()
        title_var.set(f"{month_names[state['month'] - 1]} {state['year']}")
        for col, label in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):
            ttk.Label(body, text=label, width=4, anchor="center").grid(
                row=0, column=col, padx=1, pady=(0, 4)
            )
        for row_idx, week in enumerate(
            calendar.monthcalendar(state["year"], state["month"]), start=1
        ):
            for col_idx, day in enumerate(week):
                if day == 0:
                    ttk.Label(body, text="", width=4).grid(row=row_idx, column=col_idx)
                    continue
                ttk.Button(
                    body,
                    text=str(day),
                    width=4,
                    command=lambda d=day: pick_day(d),
                ).grid(row=row_idx, column=col_idx, padx=1, pady=1)

    def move_month(delta):
        month = state["month"] + int(delta)
        year = state["year"]
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        state["year"], state["month"] = year, month
        render_month()

    ttk.Button(top, text="◀", width=3, command=lambda: move_month(-1)).pack(side="left")
    ttk.Label(top, textvariable=title_var, width=20, anchor="center").pack(side="left", padx=8)
    ttk.Button(top, text="▶", width=3, command=lambda: move_month(1)).pack(side="left")
    picker.protocol("WM_DELETE_WINDOW", close_picker)
    render_month()


def _work_order_output_path(order):
    """Zwraca trwałą ścieżkę karty w aktywnym ROOT danych WM."""
    raw_id = str(order.get("id") or "bez_id")
    safe_id = "".join(ch for ch in raw_id if ch.isalnum() or ch in ("-", "_")) or "bez_id"
    folder = get_data_root() / "zlecenia" / "karty"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"zlecenie_{safe_id}.html"


def _work_order_html(order):
    try:
        raw_summary = ZL.material_bar_summary(order)
    except Exception:
        raw_summary = {
            str(code): dict(rec)
            for code, rec in (order.get("zapotrzebowanie_surowce") or {}).items()
            if isinstance(rec, dict)
        }

    rows = []
    for code, rec in (order.get("plan_polprodukty") or {}).items():
        if not isinstance(rec, dict):
            continue
        operation_names = [
            str(x).strip()
            for x in (rec.get("czynnosci") or [])
            if str(x).strip()
        ]
        operations = (
            "".join(
                f"<div class='operation'><span class='check-box'></span>{html.escape(name)}</div>"
                for name in operation_names
            )
            or "—"
        )
        raw = rec.get("surowiec") or {}
        raw_code = str(raw.get("kod") or raw.get("id") or "—")
        raw_info = raw_summary.get(raw_code, {}) if isinstance(raw_summary, dict) else {}
        raw_name = str(raw.get("nazwa") or raw_info.get("nazwa") or raw_code)
        raw_unit = str(raw.get("jednostka") or raw_info.get("jednostka") or "")
        per_piece_value = raw.get("ilosc_na_szt")
        if per_piece_value in (None, ""):
            per_piece_text = "—"
        else:
            per_piece_text = f"Długość detalu: {_fmt_linear(per_piece_value, raw_unit)}"
            if raw_unit.strip().lower() in {"mm", "milimetr", "milimetry", "milimetrów"}:
                try:
                    with_cut = float(per_piece_value or 0) + max(0.0, float(order.get("rzaz_mm", 2) or 0))
                    per_piece_text += (
                        f"<br>Do odcięcia: <b>{_fmt_linear(per_piece_value, raw_unit)} + "
                        f"grubość piły/taśmy {_fmt_qty(order.get('rzaz_mm', 2))} mm = "
                        f"{_fmt_linear(with_cut, raw_unit)} / szt.</b>"
                    )
                except Exception:
                    pass
        qty_text = (
            f"Potrzeba: {_fmt_qty(rec.get('potrzeba', rec.get('ilosc', 0)))}<br>"
            f"Z magazynu: {_fmt_qty(rec.get('z_magazynu', 0))}<br>"
            f"<b>Do wykonania: {_fmt_qty(rec.get('do_wykonania', rec.get('ilosc', 0)))}</b>"
        )
        rows.append(
            "<tr>"
            f"<td><b>{html.escape(str(rec.get('nazwa') or code))}</b><br><span class='small'>{html.escape(str(code))}</span></td>"
            f"<td>{qty_text}</td>"
            f"<td><b>{html.escape(raw_name)}</b><br><span class='small'>{html.escape(raw_code)}</span><br>"
            f"{per_piece_text}</td>"
            f"<td>{operations}</td>"
            "</tr>"
        )

    raw_total_rows = []
    reservations = order.get("rezerwacje_surowce") or {}
    for code, rec in (raw_summary or {}).items():
        if not isinstance(rec, dict):
            continue
        unit = str(rec.get("jednostka") or "")
        reserved = reservations.get(code, 0) if isinstance(reservations, dict) else 0
        bar_length = float(rec.get("dlugosc_sztangi_mm", 0) or 0)
        bars = rec.get("sztangi_potrzebne")
        bars_text = "—" if bars is None else _fmt_qty(bars)
        error = str(rec.get("blad_ciecia") or "").strip()
        if error:
            bars_text = f"{bars_text}<br><span class='warn-inline'>{html.escape(error)}</span>"
        raw_total_rows.append(
            "<tr>"
            f"<td><b>{html.escape(str(rec.get('nazwa') or code))}</b><br><span class='small'>{html.escape(str(code))}</span></td>"
            f"<td><b>{html.escape(_fmt_linear(rec.get('ilosc', 0), unit))}</b></td>"
            f"<td>{html.escape(_fmt_linear(bar_length, 'mm')) if bar_length > 0 else '—'}</td>"
            f"<td><b>{bars_text}</b></td>"
            f"<td>{html.escape(_fmt_linear(reserved, unit))}</td>"
            "</tr>"
        )
    raw_total_block = ""
    if raw_total_rows:
        raw_total_block = (
            "<h2>Surowiec do pobrania i cięcia</h2>"
            "<table><thead><tr><th>Surowiec</th><th>Razem</th><th>Standardowa sztanga</th><th>Potrzeba sztang</th><th>Zarezerwowano z magazynu</th></tr></thead>"
            f"<tbody>{''.join(raw_total_rows)}</tbody></table>"
            "<p class='small stock-note'><b>Zarezerwowano z magazynu</b> = ilość surowca już zablokowana w Magazynie dla tego zlecenia.</p>"
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

    try:
        ordered = float(order.get("ilosc", 0) or 0)
        done = float(order.get("wykonano", 0) or 0)
        remaining = max(0.0, ordered - done)
    except Exception:
        remaining = 0.0

    return f"""<!doctype html>
<html lang='pl'><head><meta charset='utf-8'><title>Zlecenie {html.escape(str(order.get('id') or ''))}</title>
<style>
@page {{ size: A5 portrait; margin: 7mm; }}
body {{ font-family: Arial, sans-serif; font-size: 9.5pt; color:#111; margin:0; }}
h1 {{ font-size:15pt; margin:0 0 4mm; }}
h2 {{ font-size:11pt; margin:4mm 0 2mm; }}
.meta {{ display:grid; grid-template-columns:1fr 1fr; gap:1.5mm 7mm; margin-bottom:4mm; }}
.wide {{ grid-column:1 / -1; }}
.warn-inline {{ color:#922; font-size:7.5pt; }}
table {{ width:100%; border-collapse:collapse; font-size:8.5pt; page-break-inside:auto; }}
tr {{ page-break-inside:avoid; }}
th,td {{ border:1px solid #555; padding:1.6mm; vertical-align:top; }}
th {{ background:#eee; }}
.warn {{ margin-top:4mm; border:2px solid #b33; padding:2mm; }}
.notes {{ margin-top:4mm; min-height:14mm; border:1px solid #777; padding:2mm; }}
.small {{ font-size:7.5pt; color:#555; }}
.operation {{ display:flex; align-items:center; gap:1.5mm; margin:0.7mm 0; }}
.check-box {{ display:inline-block; width:3.2mm; height:3.2mm; border:1.2px solid #111; flex:0 0 3.2mm; }}
.operations-note {{ margin-top:2mm; padding:1.8mm 2mm; border:1px solid #777; font-weight:bold; }}
.stock-note {{ margin:1.5mm 0 0; }}
</style></head><body>
<h1>ZLECENIE DO WYKONANIA</h1>
<div class='meta'>
<div><b>Zlecenie warsztatowe:</b> {html.escape(str(order.get('id') or ''))}</div>
<div><b>Zlecenie wew:</b> {html.escape(str(order.get('zlec_wew') or '—'))}</div>
<div><b>Termin:</b> {html.escape(_display_date(order.get('termin')) or '—')}</div>
<div><b>Produkt:</b> {html.escape(str(order.get('produkt') or ''))}</div>
<div><b>Zamówienie:</b> {html.escape(_fmt_qty(order.get('ilosc', 0)))}</div>
<div><b>Wykonano:</b> {html.escape(_fmt_qty(order.get('wykonano', 0)))}</div>
<div><b>Pozostało:</b> {html.escape(_fmt_qty(remaining))}</div>
<div><b>Wersja BOM:</b> {html.escape(str(order.get('version') or '—'))}</div>
<div class='wide'><b>Grubość piły/taśmy:</b> {html.escape(_fmt_qty(order.get('rzaz_mm', 2)))} mm</div>
<div><b>Nadprodukcja:</b> {'TAK' if order.get('zezwol_nadprodukcja') else 'NIE'}</div>
</div>
<table><thead><tr><th>Półprodukt</th><th>Ilości</th><th>Surowiec / długość cięcia</th><th>Operacje</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="4">Brak półproduktów</td></tr>'}</tbody></table>
<div class='operations-note'>Po wykonaniu wszystkich operacji oznacz zlecenie jako wykonane w WM.</div>
{raw_total_block}
{shortage_block}
<div class='notes'><b>Uwagi:</b><br>{html.escape(str(order.get('uwagi') or ''))}</div>
<p class='small'>Warsztat Menager — karta robocza A5. Kopia została zapisana w aktywnym ROOT WM.</p>
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
            self.tree.insert("", "end", iid=oid, values=(oid, order.get("produkt", ""), _fmt_qty(qty), _fmt_qty(done), _fmt_qty(left), _display_date(order.get("termin", "")), order.get("status", "")))

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
        ttk.Label(frm, text=f"Zlecenie: {order.get('id')} | Produkt: {order.get('produkt')}").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frm, text="Termin:").grid(row=1, column=0, sticky="w")
        var = tk.StringVar(value=_display_date(order.get("termin")) or date.today().strftime("%d-%m-%y"))
        ent = tk.Entry(
            frm,
            textvariable=var,
            width=16,
            state="readonly",
            readonlybackground="#2e7d32",
            fg="white",
            relief="solid",
            bd=1,
            justify="center",
        )
        ent.grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Button(
            frm,
            text="📅 Kalendarz",
            command=lambda: _open_date_calendar(dlg, var),
        ).grid(row=1, column=2, sticky="w", padx=(8, 0))

        def save():
            try:
                ZL.update_zlecenie(
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
            path = _work_order_output_path(order)
            path.write_text(_work_order_html(order), encoding="utf-8")
            if os.name == "nt":
                os.startfile(str(path))
            else:
                webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror("Wydruk", f"Nie udało się przygotować wydruku:\n{exc}", parent=self.win)


def open_planista(root, login=None, rola=None):
    return PlanistaWindow(root, login=login, rola=rola)
