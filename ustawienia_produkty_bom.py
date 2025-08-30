# Plik: ustawienia_produkty_bom.py
# Wersja pliku: 1.1.0
# Zmiany 1.1.0:
# - Edycja wiersza BOM z polami "Czynności" oraz "Surowiec" (typ i długość)
# - Zapis/odczyt operacji i surowców w danych produktu
#
# Zmiany 1.0.0:
# - Zakładka "Produkty (BOM)" do Ustawień: lista produktów, edycja BOM, zapis do data/produkty/<KOD>.json
# - Obsługa materiałów zarówno z plików per-materiał (data/magazyn/*.json) jak i zbiorczego stanu (data/magazyn/magazyn.json)
# - Ciemny motyw przez ui_theme.apply_theme
# ⏹ KONIEC KODU

import os
import json
import glob
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui_theme import apply_theme_safe as apply_theme
from utils import error_dialogs
from utils.dirty_guard import DirtyGuard

DATA_DIR = os.path.join("data", "produkty")
POL_DIR = os.path.join("data", "polprodukty")

__all__ = ["make_tab"]

# ---------- I/O ----------
def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(POL_DIR, exist_ok=True)

def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except Exception:
        return default if default is not None else {}

def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _list_produkty():
    _ensure_dirs()
    out=[]
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        j = _read_json(p, {})
        kod = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
        naz = j.get("nazwa") or kod
        out.append({"kod": kod, "nazwa": naz, "_path": p})
    return out

def _list_polprodukty():
    items = []
    pattern = os.path.join(POL_DIR, "PP*.json")
    for p in glob.glob(pattern):
        j = _read_json(p, {})
        kod = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
        naz = j.get("nazwa", kod)
        items.append({"kod": kod, "nazwa": naz})
    return sorted(items, key=lambda x: x["kod"])

# ---------- UI ----------
def make_tab(parent, rola=None):
    """Zwraca Frame do wpięcia jako zakładka w Ustawieniach."""
    frm = ttk.Frame(parent)
    apply_theme(frm)
    _ensure_dirs()

    # layout
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(1, weight=1)

    # lewy panel (lista produktów)
    left = ttk.Frame(frm, style="WM.Card.TFrame"); left.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(10,6), pady=10)
    ttk.Label(left, text="Produkty", style="WM.Card.TLabel").pack(anchor="w")
    lb = tk.Listbox(left, height=22); lb.pack(fill="y", expand=False, pady=(6,6))
    btns = ttk.Frame(left)
    btns.pack(fill="x")
    btn_new = ttk.Button(btns, text="Nowy", style="WM.Side.TButton")
    btn_new.pack(side="left", padx=2)
    btn_del = ttk.Button(btns, text="Usuń", style="WM.Side.TButton")
    btn_del.pack(side="left", padx=2)
    btn_save = ttk.Button(btns, text="Zapisz", style="WM.Side.TButton")
    btn_save.pack(side="left", padx=2)

    # prawy panel (nagłówek + BOM)
    right = ttk.Frame(frm, style="WM.Card.TFrame"); right.grid(row=0, column=1, sticky="new", padx=(6,10), pady=(10,0))
    right.columnconfigure(3, weight=1)
    ttk.Label(right, text="Kod produktu:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    var_kod = tk.StringVar();  ttk.Entry(right, textvariable=var_kod, width=24).grid(row=0, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(right, text="Nazwa:", style="WM.Card.TLabel").grid(row=0, column=2, sticky="w", padx=6, pady=4)
    var_nazwa = tk.StringVar(); ttk.Entry(right, textvariable=var_nazwa).grid(row=0, column=3, sticky="ew", padx=6, pady=4)

    # BOM tabela
    center = ttk.Frame(frm, style="WM.TFrame"); center.grid(row=1, column=1, sticky="nsew", padx=(6,10), pady=(6,10))
    center.rowconfigure(1, weight=1); center.columnconfigure(0, weight=1)
    bar = ttk.Frame(center, style="WM.TFrame"); bar.grid(row=0, column=0, sticky="ew")
    ttk.Label(bar, text="BOM (półprodukty)", style="WM.Card.TLabel").pack(side="left")
    ttk.Button(bar, text="Dodaj wiersz", command=lambda:_add_row(), style="WM.Side.TButton").pack(side="right", padx=(6,2))
    ttk.Button(bar, text="Edytuj wiersz", command=lambda:_edit_row(), style="WM.Side.TButton").pack(side="right", padx=(6,2))
    ttk.Button(bar, text="Usuń wiersz", command=lambda:_del_row(), style="WM.Side.TButton").pack(side="right")
    tv = ttk.Treeview(
        center,
        columns=("pp", "nazwa", "ilosc_na_szt", "operacje", "surowiec"),
        show="headings",
        style="WM.Treeview",
        height=14,
    )
    tv.grid(row=1, column=0, sticky="nsew", pady=(6,0))
    for c, t, w in [
        ("pp", "Kod PP", 160),
        ("nazwa", "Nazwa", 220),
        ("ilosc_na_szt", "Ilość na szt.", 100),
        ("operacje", "Czynności", 160),
        ("surowiec", "Surowiec", 160),
    ]:
        tv.heading(c, text=t)
        tv.column(c, width=w, anchor="w")
    tv.bind("<Double-1>", lambda e: _edit_row())

    frm._polprodukty = _list_polprodukty()

    # funkcje wewnętrzne
    def _refresh():
        lb.delete(0,"end")
        frm._products = _list_produkty()
        for p in frm._products:
            lb.insert("end", f"{p['kod']} – {p['nazwa']}")

    def _select_idx():
        sel = lb.curselection()
        return sel[0] if sel else None

    def _load():
        idx = _select_idx()
        for iid in tv.get_children():
            tv.delete(iid)
        if idx is None:
            var_kod.set("")
            var_nazwa.set("")
            return
        p = frm._products[idx]
        j = _read_json(p["_path"], {})
        var_kod.set(j.get("kod", p["kod"]))
        var_nazwa.set(j.get("nazwa", p["nazwa"]))
        for poz in j.get("polprodukty", []):
            mid = poz.get("kod", "")
            nm = next((m["nazwa"] for m in frm._polprodukty if m["kod"] == mid), "")
            ops_txt = ", ".join(poz.get("operacje", []))
            sr = poz.get("surowiec") or {}
            sr_txt = ""
            if sr:
                t = sr.get("typ", "")
                d = sr.get("dlugosc")
                sr_txt = f"{t}:{d}" if d is not None else t
            tv.insert(
                "",
                "end",
                values=(mid, nm, poz.get("ilosc_na_szt", 1), ops_txt, sr_txt),
            )

    def _new():
        k = simpledialog.askstring("Nowy produkt", "Podaj kod:", parent=frm)
        if not k: return
        var_kod.set(k.strip()); var_nazwa.set("")
        for iid in tv.get_children(): tv.delete(iid)

    def _delete():
        idx=_select_idx()
        if idx is None:
            messagebox.showwarning("Produkty","Zaznacz produkt do usunięcia."); return
        p = frm._products[idx]
        if not messagebox.askyesno("Produkty", f"Usunąć {p['kod']}?"): return
        try: os.remove(p["_path"])
        except Exception: pass
        _refresh(); var_kod.set(""); var_nazwa.set("")
        for iid in tv.get_children(): tv.delete(iid)

    def _add_row(edit_iid=None):
        win = tk.Toplevel(frm)
        win.title("Pozycja BOM")
        apply_theme(win)
        f = ttk.Frame(win)
        f.pack(padx=10, pady=10, fill="x")
        ttk.Label(f, text="Półprodukt:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        pp_ids = [m["kod"] for m in frm._polprodukty]
        pp_desc = [f"{m['kod']} – {m['nazwa']}" for m in frm._polprodukty]
        cb = ttk.Combobox(f, values=pp_desc, state="readonly")
        cb.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(f, text="Ilość na szt.", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_il = tk.StringVar(value="1")
        ttk.Entry(f, textvariable=var_il, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(f, text="Czynności:", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        var_ops = tk.StringVar()
        ttk.Entry(f, textvariable=var_ops).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(f, text="Surowiec typ:", style="WM.Card.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        var_sr_typ = tk.StringVar()
        ttk.Entry(f, textvariable=var_sr_typ).grid(row=3, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(f, text="Surowiec dł.", style="WM.Card.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        var_sr_dl = tk.StringVar()
        ttk.Entry(f, textvariable=var_sr_dl, width=10).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        if pp_desc:
            cb.current(0)
        if edit_iid:
            vals = tv.item(edit_iid, "values")
            try:
                idx = pp_ids.index(vals[0])
                cb.current(idx)
            except ValueError:
                cb.set(vals[0])
            var_il.set(vals[2])
            var_ops.set(vals[3])
            sr_typ = sr_dl = ""
            if vals[4]:
                parts = str(vals[4]).split(":", 1)
                sr_typ = parts[0]
                if len(parts) > 1:
                    sr_dl = parts[1]
            var_sr_typ.set(sr_typ)
            var_sr_dl.set(sr_dl)

        def _ok():
            try:
                i = cb.current()
                if i < 0:
                    messagebox.showwarning("BOM", "Wybierz półprodukt.")
                    return
                pp_id = pp_ids[i]
                nm = frm._polprodukty[i]["nazwa"]
                il = float(var_il.get())
                if il <= 0:
                    raise ValueError
            except Exception:
                error_dialogs.show_error_dialog("BOM", "Ilość musi być dodatnią liczbą")
                return
            if il.is_integer():
                il = int(il)
            ops_txt = ", ".join([o.strip() for o in var_ops.get().split(",") if o.strip()])
            sr_typ = var_sr_typ.get().strip()
            sr_dl = var_sr_dl.get().strip()
            sr_txt = f"{sr_typ}:{sr_dl}" if sr_typ and sr_dl else sr_typ
            values = (pp_id, nm, il, ops_txt, sr_txt)
            if edit_iid:
                tv.item(edit_iid, values=values)
            else:
                tv.insert("", "end", values=values)
            win.destroy()

        ttk.Button(f, text="OK", command=_ok, style="WM.Side.TButton").grid(row=5, column=0, columnspan=2, pady=(8, 2))

    def _edit_row():
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("BOM","Zaznacz wiersz do edycji.")
            return
        _add_row(sel[0])

    def _del_row():
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("BOM","Zaznacz wiersz do usunięcia."); return
        for iid in sel:
            tv.delete(iid)

    def _save():
        kod = (var_kod.get() or "").strip()
        naz = (var_nazwa.get() or "").strip()
        if not kod or not naz:
            messagebox.showwarning("Produkty", "Uzupełnij kod i nazwę.")
            return
        bom = []
        for iid in tv.get_children():
            pp, _nm, il, ops_txt, sr_txt = tv.item(iid, "values")
            try:
                il = float(il)
                if il <= 0:
                    raise ValueError
            except Exception:
                error_dialogs.show_error_dialog("BOM", "Ilość musi być dodatnią liczbą")
                return
            if il.is_integer():
                il = int(il)
            poz = {"kod": pp, "ilosc_na_szt": il}
            ops = [o.strip() for o in str(ops_txt).split(",") if o.strip()]
            if ops:
                poz["operacje"] = ops
            if sr_txt:
                parts = str(sr_txt).split(":", 1)
                sr_typ = parts[0].strip()
                sr_dl = None
                if len(parts) > 1:
                    try:
                        sr_dl = float(parts[1])
                    except ValueError:
                        sr_dl = None
                if sr_typ and sr_dl is not None:
                    poz["surowiec"] = {"typ": sr_typ, "dlugosc": sr_dl}
            bom.append(poz)
        payload = {"kod": kod, "nazwa": naz, "polprodukty": bom}
        _write_json(os.path.join(DATA_DIR, f"{kod}.json"), payload)
        messagebox.showinfo("Produkty", f"Zapisano {kod}.")
        _refresh()
        # selekcja na zapisany
        for i, p in enumerate(frm._products):
            if p["kod"] == kod:
                lb.selection_clear(0, "end")
                lb.selection_set(i)
                lb.activate(i)
                break

    notebook = parent.nametowidget(parent.winfo_parent())
    base_title = notebook.tab(parent, "text")
    guard = DirtyGuard(
        "Produkty (BOM)",
        on_save=lambda: (_save(), guard.reset()),
        on_reset=lambda: (_load(), guard.reset()),
        on_dirty_change=lambda d: notebook.tab(
            parent, text=base_title + (" •" if d else "")
        ),
    )
    guard.watch(frm)

    lb.bind(
        "<<ListboxSelect>>",
        lambda e: guard.check_before(lambda: (_load(), guard.reset())),
    )
    btn_new.configure(
        command=lambda: guard.check_before(lambda: (_new(), guard.reset()))
    )
    btn_del.configure(
        command=lambda: guard.check_before(lambda: (_delete(), guard.reset()))
    )
    btn_save.configure(command=guard.on_save)

    _refresh()
    return frm

# ⏹ KONIEC KODU
