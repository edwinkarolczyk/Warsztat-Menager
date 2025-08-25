# Plik: ustawienia_produkty_bom.py
# Wersja pliku: 1.0.0
# Zmiany 1.0.0:
# - Zakładka "Produkty (BOM)" do Ustawień: lista produktów, edycja BOM, zapis do data/produkty/<KOD>.json
# - Obsługa materiałów zarówno z plików per-materiał (data/magazyn/*.json) jak i zbiorczego stanu (data/magazyn/stany.json)
# - Ciemny motyw przez ui_theme.apply_theme
# ⏹ KONIEC KODU

import os, json, glob, tkinter as tk
from tkinter import ttk, messagebox, simpledialog

try:
    from ui_theme import apply_theme
except Exception:
    def apply_theme(_): pass

DATA_DIR = os.path.join("data", "produkty")
MAG_DIR  = os.path.join("data", "magazyn")

__all__ = ["make_tab"]

# ---------- I/O ----------
def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MAG_DIR,  exist_ok=True)

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

def _list_materialy():
    # wspiera pliki per-materiał oraz zbiorczy stany.json
    items=[]
    for p in glob.glob(os.path.join(MAG_DIR, "*.json")):
        b=os.path.basename(p).lower()
        if b=="stany.json" or b.startswith("_"):
            continue
        j=_read_json(p,{})
        iid = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
        nm  = j.get("nazwa", iid)
        items.append({"id":iid,"nazwa":nm})
    stany=_read_json(os.path.join(MAG_DIR,"stany.json"),{})
    for k,v in stany.items():
        items.append({"id":k,"nazwa":v.get("nazwa",k)})
    # deduplikacja
    seen=set(); out=[]
    for it in items:
        if it["id"] in seen: continue
        seen.add(it["id"]); out.append(it)
    return sorted(out, key=lambda x: x["id"])

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
    btns = ttk.Frame(left); btns.pack(fill="x")
    ttk.Button(btns, text="Nowy",  command=lambda:_new(),  style="WM.Side.TButton").pack(side="left", padx=2)
    ttk.Button(btns, text="Usuń",  command=lambda:_delete(),style="WM.Side.TButton").pack(side="left", padx=2)
    ttk.Button(btns, text="Zapisz",command=lambda:_save(),  style="WM.Side.TButton").pack(side="left", padx=2)

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
    ttk.Button(bar, text="Usuń wiersz", command=lambda:_del_row(), style="WM.Side.TButton").pack(side="right")
    tv = ttk.Treeview(center, columns=("mat","nazwa","ilosc","dl"), show="headings", style="WM.Treeview", height=14)
    tv.grid(row=1, column=0, sticky="nsew", pady=(6,0))
    for c,t,w in [("mat","Kod materiału",200),("nazwa","Nazwa z magazynu",260),("ilosc","Ilość [szt]",120),("dl","Długość [mm]",140)]:
        tv.heading(c, text=t); tv.column(c, width=w, anchor="w")

    frm._materials = _list_materialy()

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
        idx=_select_idx()
        for iid in tv.get_children(): tv.delete(iid)
        if idx is None:
            var_kod.set(""); var_nazwa.set(""); return
        p = frm._products[idx]
        j = _read_json(p["_path"], {})
        var_kod.set(j.get("kod", p["kod"])); var_nazwa.set(j.get("nazwa", p["nazwa"]))
        for poz in j.get("BOM", []):
            mid = poz.get("kod_materialu",""); nm = next((m["nazwa"] for m in frm._materials if m["id"]==mid), "")
            tv.insert("", "end", values=(mid, nm, poz.get("ilosc",1), poz.get("dlugosc_mm","")))

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

    def _add_row():
        win = tk.Toplevel(frm); win.title("Dodaj pozycję BOM"); apply_theme(win)
        f = ttk.Frame(win); f.pack(padx=10, pady=10, fill="x")
        ttk.Label(f, text="Materiał:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        mat_ids  = [m["id"] for m in frm._materials]
        mat_desc = [f"{m['id']} – {m['nazwa']}" for m in frm._materials]
        cb = ttk.Combobox(f, values=mat_desc, state="readonly"); cb.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        if mat_desc: cb.current(0)
        ttk.Label(f, text="Ilość [szt]:", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_il = tk.StringVar(value="1"); ttk.Entry(f, textvariable=var_il, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(f, text="Długość [mm] (opc.):", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        var_dl = tk.StringVar(value=""); ttk.Entry(f, textvariable=var_dl, width=12).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        def _ok():
            try:
                i = cb.current()
                if i < 0: messagebox.showwarning("BOM","Wybierz materiał."); return
                mid = mat_ids[i]; nm = frm._materials[i]["nazwa"]
                il = int(var_il.get())
                if il<=0: raise ValueError
                dl = var_dl.get().strip(); dl = int(dl) if dl else ""
            except Exception:
                messagebox.showerror("BOM","Podaj poprawną ilość/długość."); return
            tv.insert("", "end", values=(mid, nm, il, dl)); win.destroy()
        ttk.Button(f, text="Dodaj", command=_ok, style="WM.Side.TButton").grid(row=3, column=0, columnspan=2, pady=(8,2))

    def _del_row():
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("BOM","Zaznacz wiersz do usunięcia."); return
        for iid in sel: tv.delete(iid)

    def _save():
        kod = (var_kod.get() or "").strip()
        naz = (var_nazwa.get() or "").strip()
        if not kod or not naz:
            messagebox.showwarning("Produkty","Uzupełnij kod i nazwę."); return
        bom=[]
        for iid in tv.get_children():
            mat, _nm, il, dl = tv.item(iid, "values")
            try:
                il = int(il)
                if il<=0: raise ValueError
            except Exception:
                messagebox.showerror("BOM","Ilość musi być dodatnią liczbą całkowitą."); return
            rec = {"kod_materialu": mat, "ilosc": il}
            if str(dl).strip() not in ("","0"):
                try: rec["dlugosc_mm"] = int(dl)
                except Exception:
                    messagebox.showerror("BOM","Długość musi być liczbą (mm)."); return
            bom.append(rec)
        payload = {"kod": kod, "nazwa": naz, "BOM": bom}
        _write_json(os.path.join(DATA_DIR, f"{kod}.json"), payload)
        messagebox.showinfo("Produkty", f"Zapisano {kod}.")
        _refresh()
        # selekcja na zapisany
        for i,p in enumerate(frm._products):
            if p["kod"] == kod:
                lb.selection_clear(0,"end"); lb.selection_set(i); lb.activate(i); break

    lb.bind("<<ListboxSelect>>", lambda e:_load())
    _refresh()
    return frm
