# Plik: ustawienia_produkty_bom.py
# Wersja pliku: 1.0.0
# Zmiany 1.0.0:
# - Zakładka "Produkty (BOM)" do Ustawień: lista produktów, edycja BOM, zapis do data/produkty/<KOD>.json
# - Obsługa materiałów zarówno z plików per-materiał (data/magazyn/*.json) jak i zbiorczego stanu (data/magazyn/magazyn.json)
# - Ciemny motyw przez ui_theme.apply_theme
# ⏹ KONIEC KODU

import os
import glob
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui_theme import apply_theme_safe as apply_theme
from utils.dirty_guard import DirtyGuard
from utils.json_io import _ensure_dirs as _ensure_dirs_impl, _read_json, _write_json

DATA_DIR = os.path.join("data", "produkty")
POL_DIR = os.path.join("data", "polprodukty")
SURO_PATH = os.path.join("data", "magazyn", "surowce.json")

__all__ = ["make_tab"]

def _ensure_dirs():
    _ensure_dirs_impl(DATA_DIR, POL_DIR)

# ---------- I/O ----------

def _list_produkty():
    _ensure_dirs()
    out = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        j = _read_json(p, {})
        kod = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
        naz = j.get("nazwa") or kod
        ver = j.get("version")
        is_def = j.get("is_default", False)
        out.append({
            "kod": kod,
            "nazwa": naz,
            "version": ver,
            "is_default": is_def,
            "_path": p,
        })
    return out

def _list_polprodukty():
    items = []
    pattern = os.path.join(POL_DIR, "PP*.json")
    for p in glob.glob(pattern):
        j = _read_json(p, {})
        kod = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
        naz = j.get("nazwa", kod)
        cz = j.get("czynnosci", [])
        items.append({"kod": kod, "nazwa": naz, "czynnosci": cz})
    return sorted(items, key=lambda x: x["kod"])


def _list_surowce():
    j = _read_json(SURO_PATH, [])
    out = []
    if isinstance(j, dict):
        for k, v in sorted(j.items()):
            if isinstance(v, dict):
                out.append({"kod": k, "nazwa": v.get("nazwa", k)})
    elif isinstance(j, list):
        for rec in sorted(j, key=lambda r: r.get("kod", "")):
            if isinstance(rec, dict) and rec.get("kod"):
                kod = rec["kod"]
                out.append({"kod": kod, "nazwa": rec.get("nazwa", kod)})
    return out

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
    left = ttk.Frame(frm, style="WM.Card.TFrame")
    left.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(10, 6), pady=10)
    left.grid_columnconfigure(0, weight=1)
    left.grid_rowconfigure(1, weight=1)

    ttk.Label(left, text="Produkty", style="WM.Card.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    lb = tk.Listbox(left, height=22)
    lb.grid(row=1, column=0, sticky="ns", pady=(6, 6))
    btns = ttk.Frame(left)
    btns.grid(row=2, column=0, sticky="ew")
    btn_new = ttk.Button(btns, text="Nowy", style="WM.Side.TButton")
    btn_new.grid(row=0, column=0, padx=2)
    btn_del = ttk.Button(btns, text="Usuń", style="WM.Side.TButton")
    btn_del.grid(row=0, column=1, padx=2)
    btn_save = ttk.Button(btns, text="Zapisz", style="WM.Side.TButton")
    btn_save.grid(row=0, column=2, padx=2)

    # prawy panel (nagłówek + BOM)
    right = ttk.Frame(frm, style="WM.Card.TFrame"); right.grid(row=0, column=1, sticky="new", padx=(6,10), pady=(10,0))
    right.columnconfigure(3, weight=1)
    ttk.Label(right, text="Kod produktu:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    var_kod = tk.StringVar();  ttk.Entry(right, textvariable=var_kod, width=24).grid(row=0, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(right, text="Nazwa:", style="WM.Card.TLabel").grid(row=0, column=2, sticky="w", padx=6, pady=4)
    var_nazwa = tk.StringVar(); ttk.Entry(right, textvariable=var_nazwa).grid(row=0, column=3, sticky="ew", padx=6, pady=4)

    ttk.Label(right, text="Wersja:", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    var_ver = tk.StringVar(); ttk.Entry(right, textvariable=var_ver, width=12).grid(row=1, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(right, text="BOM rev:", style="WM.Card.TLabel").grid(row=1, column=2, sticky="w", padx=6, pady=4)
    var_bom_rev = tk.IntVar(value=1); ttk.Spinbox(right, from_=1, to=999, textvariable=var_bom_rev, width=8).grid(row=1, column=3, sticky="w", padx=6, pady=4)
    var_is_default = tk.BooleanVar(value=True); ttk.Checkbutton(right, text="Domyślna", variable=var_is_default).grid(row=1, column=4, sticky="w", padx=6, pady=4)

    ttk.Label(right, text="Obowiązuje od:", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=6, pady=4)
    var_eff_from = tk.StringVar(); ttk.Entry(right, textvariable=var_eff_from, width=12).grid(row=2, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(right, text="Obowiązuje do:", style="WM.Card.TLabel").grid(row=2, column=2, sticky="w", padx=6, pady=4)
    var_eff_to = tk.StringVar(); ttk.Entry(right, textvariable=var_eff_to, width=12).grid(row=2, column=3, sticky="w", padx=6, pady=4)

    # BOM tabela
    center = ttk.Frame(frm, style="WM.TFrame"); center.grid(row=1, column=1, sticky="nsew", padx=(6,10), pady=(6,10))
    center.rowconfigure(1, weight=1); center.columnconfigure(0, weight=1)
    bar = ttk.Frame(center, style="WM.TFrame")
    bar.grid(row=0, column=0, sticky="ew")
    bar.grid_columnconfigure(0, weight=1)
    ttk.Label(bar, text="BOM (półprodukty)", style="WM.Card.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Button(
        bar,
        text="Usuń wiersz",
        command=lambda: _del_row(),
        style="WM.Side.TButton",
    ).grid(row=0, column=1)
    ttk.Button(
        bar,
        text="Dodaj wiersz",
        command=lambda: _add_row(),
        style="WM.Side.TButton",
    ).grid(row=0, column=2, padx=(6, 2))
    tv = ttk.Treeview(
        center,
        columns=(
            "pp",
            "nazwa",
            "ilosc_na_szt",
            "czynnosci",
            "surowiec",
            "surowiec_dlugosc",
        ),
        show="headings",
        style="WM.Treeview",
        height=14,
    )
    tv.grid(row=1, column=0, sticky="nsew", pady=(6,0))
    for c, t, w in [
        ("pp", "Kod PP", 150),
        ("nazwa", "Nazwa", 220),
        ("ilosc_na_szt", "Ilość na szt.", 110),
        ("czynnosci", "Czynności", 180),
        ("surowiec", "Surowiec", 140),
        ("surowiec_dlugosc", "Długość", 80),
    ]:
        tv.heading(c, text=t)
        tv.column(c, width=w, anchor="w")

    frm._polprodukty = _list_polprodukty()
    frm._surowce = _list_surowce()

    # funkcje wewnętrzne
    def _refresh():
        lb.delete(0, "end")
        frm._products = _list_produkty()
        frm._polprodukty = _list_polprodukty()
        frm._surowce = _list_surowce()
        for p in frm._products:
            label = f"{p['kod']} – {p['nazwa']}"
            if p.get("version"):
                label += f" (v{p['version']})"
            if p.get("is_default"):
                label += " *"
            lb.insert("end", label)

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
            var_ver.set("")
            var_bom_rev.set(1)
            var_eff_from.set("")
            var_eff_to.set("")
            var_is_default.set(True)
            return
        p = frm._products[idx]
        j = _read_json(p["_path"], {})
        var_kod.set(j.get("kod", p["kod"]))
        var_nazwa.set(j.get("nazwa", p["nazwa"]))
        var_ver.set(str(j.get("version", "")))
        var_bom_rev.set(j.get("bom_revision", 1))
        var_eff_from.set(j.get("effective_from", ""))
        var_eff_to.set(j.get("effective_to", ""))
        var_is_default.set(j.get("is_default", False))
        for poz in j.get("polprodukty", []):
            mid = poz.get("kod", "")
            nm = next((m["nazwa"] for m in frm._polprodukty if m["kod"] == mid), "")
            cz = ", ".join(poz.get("czynnosci", []))
            sr = poz.get("surowiec", {})
            tv.insert(
                "",
                "end",
                values=(
                    mid,
                    nm,
                    poz.get("ilosc_na_szt", 1),
                    cz,
                    sr.get("typ", ""),
                    sr.get("dlugosc", ""),
                ),
            )

    def _new():
        k = simpledialog.askstring("Nowy produkt", "Podaj kod:", parent=frm)
        if not k: return
        var_kod.set(k.strip()); var_nazwa.set("")
        var_ver.set("1.0")
        var_bom_rev.set(1)
        var_eff_from.set("")
        var_eff_to.set("")
        var_is_default.set(True)
        for iid in tv.get_children(): tv.delete(iid)

    def _delete():
        idx=_select_idx()
        if idx is None:
            messagebox.showerror("Produkty","Zaznacz produkt do usunięcia."); return
        p = frm._products[idx]
        if not messagebox.askyesno("Produkty", f"Usunąć {p['kod']}?"): return
        try:
            os.remove(p["_path"])
        except Exception as e:
            messagebox.showerror("Produkty", f"Błąd usuwania pliku: {e}")
            raise
        _refresh(); var_kod.set(""); var_nazwa.set("")
        for iid in tv.get_children(): tv.delete(iid)

    def _add_row():
        if not frm._polprodukty:
            if messagebox.askyesno(
                "BOM",
                "Brak zdefiniowanych półproduktów. Czy przejść do ustawień, aby je dodać?",
            ):
                try:
                    import ustawienia_systemu as us

                    top = tk.Toplevel(frm)
                    top.title("Ustawienia")
                    top.grid_columnconfigure(0, weight=1)
                    top.grid_rowconfigure(0, weight=1)
                    cont = ttk.Frame(top)
                    cont.grid(row=0, column=0, sticky="nsew")
                    us.panel_ustawien(top, cont)
                except Exception:
                    messagebox.showerror(
                        "BOM", "Nie udało się otworzyć modułu ustawień"
                    )
            return
        if not frm._surowce:
            if messagebox.askyesno(
                "BOM",
                "Brak zdefiniowanych surowców. Czy przejść do ustawień, aby je dodać?",
            ):
                try:
                    import ustawienia_systemu as us

                    top = tk.Toplevel(frm)
                    top.title("Ustawienia")
                    top.grid_columnconfigure(0, weight=1)
                    top.grid_rowconfigure(0, weight=1)
                    cont = ttk.Frame(top)
                    cont.grid(row=0, column=0, sticky="nsew")
                    us.panel_ustawien(top, cont)
                except Exception:
                    messagebox.showerror(
                        "BOM", "Nie udało się otworzyć modułu ustawień"
                    )
            return
        win = tk.Toplevel(frm)
        win.title("Dodaj pozycję BOM")
        apply_theme(win)
        win.grid_columnconfigure(0, weight=1)
        f = ttk.Frame(win)
        f.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ttk.Label(f, text="Półprodukt:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        pp_ids = [m["kod"] for m in frm._polprodukty]
        pp_desc = ["Wybierz…"] + [f"{m['kod']} – {m['nazwa']}" for m in frm._polprodukty]
        pp_cz = [m.get("czynnosci", []) for m in frm._polprodukty]
        cb = ttk.Combobox(f, values=pp_desc, state="readonly")
        cb.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        cb.current(0)
        ttk.Label(f, text="Ilość na szt.", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_il = tk.StringVar(value="1")
        ttk.Entry(f, textvariable=var_il, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(f, text="Czynności:", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        var_cz = tk.StringVar()
        ent_cz = ttk.Entry(f, textvariable=var_cz)
        ent_cz.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(f, text="Surowiec:", style="WM.Card.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        sr_ids = [m["kod"] for m in frm._surowce]
        sr_desc = ["Wybierz…"] + [f"{m['kod']} – {m['nazwa']}" for m in frm._surowce]
        cb_sr = ttk.Combobox(f, values=sr_desc, state="readonly")
        cb_sr.grid(row=3, column=1, sticky="ew", padx=4, pady=4)
        cb_sr.current(0)
        ttk.Label(f, text="Długość:", style="WM.Card.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        var_sr_dl = tk.StringVar()
        ttk.Entry(f, textvariable=var_sr_dl).grid(row=4, column=1, sticky="ew", padx=4, pady=4)

        def _ok():
            try:
                i = cb.current()
                if i <= 0:
                    messagebox.showerror("BOM", "Wybierz półprodukt.")
                    return
                pp_id = pp_ids[i - 1]
                nm = frm._polprodukty[i - 1]["nazwa"]
                il = float(var_il.get())
                if il <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("BOM", "Ilość musi być dodatnią liczbą")
                return
            try:
                j = cb_sr.current()
                if j <= 0:
                    messagebox.showerror("BOM", "Wybierz surowiec.")
                    return
                sr_typ = sr_ids[j - 1]
                sr_dl = var_sr_dl.get().strip()
                dl = float(sr_dl)
                if dl <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror(
                    "BOM", "Długość musi być dodatnią liczbą"
                )
                return
            sr = {
                "typ": sr_typ,
                "dlugosc": dl if not dl.is_integer() else int(dl),
            }
            if il.is_integer():
                il = int(il)
            cz = [c.strip() for c in var_cz.get().split(",") if c.strip()]
            tv.insert(
                "",
                "end",
                values=(pp_id, nm, il, ", ".join(cz), sr["typ"], sr["dlugosc"]),
            )
            win.destroy()

        btn_ok = ttk.Button(f, text="Dodaj", command=_ok, style="WM.Side.TButton")
        btn_ok.grid(row=5, column=0, columnspan=2, pady=(8, 2))

        def _check_ok(event=None):
            if cb.current() > 0 and cb_sr.current() > 0:
                btn_ok.state(["!disabled"])
            else:
                btn_ok.state(["disabled"])

        def _on_pp_change(event=None):
            i = cb.current() - 1
            if i >= 0:
                var_cz.set(", ".join(pp_cz[i]))
            else:
                var_cz.set("")
            _check_ok()

        cb.bind("<<ComboboxSelected>>", _on_pp_change)
        cb_sr.bind("<<ComboboxSelected>>", _check_ok)
        _on_pp_change()
        _check_ok()

    def _del_row():
        sel = tv.selection()
        if not sel:
            messagebox.showerror("BOM", "Zaznacz wiersz do usunięcia.")
            return
        details = []
        for iid in sel:
            pp, _nazwa, _il, _cz, sr, _dl = tv.item(iid, "values")
            details.append(f"Półprodukt: {pp} / Surowiec: {sr}")
        if not messagebox.askyesno(
            "BOM", "Usuń zaznaczone wiersze?\n" + "\n".join(details)
        ):
            return
        for iid in sel:
            tv.delete(iid)

    def _save():
        kod = (var_kod.get() or "").strip()
        naz = (var_nazwa.get() or "").strip()
        if not kod or not naz:
            messagebox.showerror("Produkty", "Uzupełnij kod i nazwę.")
            return
        bom = []
        for iid in tv.get_children():
            pp, _nm, il, cz_str, sr_typ, sr_dl = tv.item(iid, "values")
            try:
                il = float(il)
                if il <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror(
                    "BOM", "Ilość musi być dodatnią liczbą"
                )
                return
            if il.is_integer():
                il = int(il)
            cz = [c.strip() for c in (cz_str or "").split(",") if c.strip()]
            if not sr_typ or not sr_dl:
                messagebox.showerror(
                    "BOM", "Wybierz surowiec i podaj długość"
                )
                return
            try:
                dl = float(sr_dl)
                if dl <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror(
                    "BOM", "Długość musi być dodatnią liczbą"
                )
                return
            sr = {"typ": sr_typ, "dlugosc": dl if not dl.is_integer() else int(dl)}
            bom.append(
                {
                    "kod": pp,
                    "ilosc_na_szt": il,
                    "czynnosci": cz,
                    "surowiec": sr,
                }
            )
        if not bom:
            messagebox.showerror("Produkty", "Dodaj przynajmniej jedną pozycję BOM.")
            return
        payload = {
            "kod": kod,
            "nazwa": naz,
            "version": var_ver.get() or "1.0",
            "bom_revision": int(var_bom_rev.get() or 1),
            "effective_from": var_eff_from.get() or None,
            "effective_to": var_eff_to.get() or None,
            "is_default": bool(var_is_default.get()),
            "polprodukty": bom,
        }
        path = os.path.join(DATA_DIR, f"{kod}.json")
        if payload["is_default"]:
            for p in glob.glob(os.path.join(DATA_DIR, "*.json")):
                if p == path:
                    continue
                other = _read_json(p, {})
                if other.get("kod") == kod and other.get("is_default"):
                    other["is_default"] = False
                    _write_json(p, other)
        _write_json(path, payload)
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
