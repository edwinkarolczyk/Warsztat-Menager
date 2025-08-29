# Plik: gui_produkty.py
# Wersja pliku: 1.0.0
# Zmiany 1.0.0:
# - Nowy edytor produktów i BOM (półprodukty) w osobnym oknie (Toplevel)
# - Zapis/odczyt plików w data/produkty/<kod>.json zgodnie ze strukturą:
#   {
#     "kod": "RAMAX",
#     "nazwa": "Rama X",
#     "BOM": [
#       {"kod_materialu": "RURA_FI30", "ilosc": 3, "dlugosc_mm": 1200},
#       {"kod_materialu": "PROFIL_40x40", "ilosc": 2, "dlugosc_mm": 6000}
#     ]
#   }
# ⏹ KONIEC KODU

import os, json, glob
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui_theme import apply_theme_safe as apply_theme
from utils import error_dialogs

DATA_DIR = os.path.join("data", "produkty")
MAG_DIR  = os.path.join("data", "magazyn")

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MAG_DIR, exist_ok=True)

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
    out = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        try:
            j = _read_json(p, {})
            kod = j.get("kod") or os.path.splitext(os.path.basename(p))[0]
            naz = j.get("nazwa") or kod
            out.append({"kod": kod, "nazwa": naz, "_path": p})
        except Exception:
            pass
    return out

def _list_materialy_z_magazynu():
    # akceptujemy dwa formaty: pliki per-materiał (RURA_FI30.json) lub zbiorczy stany.json
    items = []
    # 1) pliki per-materiał
    for p in glob.glob(os.path.join(MAG_DIR, "*.json")):
        base = os.path.basename(p)
        if base.lower() == "stany.json" or base.startswith("_"): 
            continue
        j = _read_json(p, {})
        iid = j.get("kod") or os.path.splitext(base)[0]
        nm  = j.get("nazwa", iid)
        items.append({"id": iid, "nazwa": nm})
    # 2) zbiorczy
    stany = _read_json(os.path.join(MAG_DIR, "stany.json"), {})
    for k, v in stany.items():
        items.append({"id": k, "nazwa": v.get("nazwa", k)})
    # deduplikacja
    seen = set(); out=[]
    for it in items:
        if it["id"] in seen: continue
        seen.add(it["id"]); out.append(it)
    return sorted(out, key=lambda x: x["id"])

class ProduktyBOM(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root)
        self.title("Produkty (BOM)")
        self.geometry("1000x600+140+140")
        apply_theme(self)
        _ensure_dirs()
        self._build_ui()
        self._reload_lists()

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Lewy panel: lista produktów
        left = ttk.Frame(self); left.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(10,6), pady=10)
        ttk.Label(left, text="Produkty", style="WM.Card.TLabel").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=24)
        self.listbox.pack(fill="y", expand=False, pady=(6,6))
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._load_selected())

        btns = ttk.Frame(left); btns.pack(fill="x")
        ttk.Button(btns, text="Nowy", command=self._new_product, style="WM.Side.TButton").pack(side="left", padx=2)
        ttk.Button(btns, text="Usuń", command=self._delete_product, style="WM.Side.TButton").pack(side="left", padx=2)
        ttk.Button(btns, text="Zapisz", command=self._save_current, style="WM.Side.TButton").pack(side="left", padx=2)

        # Prawy panel: nagłówek + BOM
        right = ttk.Frame(self); right.grid(row=0, column=1, sticky="new", padx=(6,10), pady=(10,0))
        right.columnconfigure(3, weight=1)

        ttk.Label(right, text="Kod produktu:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_kod = tk.StringVar()
        ttk.Entry(right, textvariable=self.var_kod, width=24).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(right, text="Nazwa:", style="WM.Card.TLabel").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        self.var_nazwa = tk.StringVar()
        ttk.Entry(right, textvariable=self.var_nazwa).grid(row=0, column=3, sticky="ew", padx=6, pady=4)

        # Tabela BOM
        center = ttk.Frame(self); center.grid(row=1, column=1, sticky="nsew", padx=(6,10), pady=(6,10))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        bar = ttk.Frame(center); bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="BOM (półprodukty)", style="WM.Card.TLabel").pack(side="left")
        ttk.Button(bar, text="Dodaj wiersz", command=self._add_row, style="WM.Side.TButton").pack(side="right", padx=(6,2))
        ttk.Button(bar, text="Usuń wiersz", command=self._del_row, style="WM.Side.TButton").pack(side="right")

        self.tree = ttk.Treeview(center, columns=("mat","nazwa","ilosc","dl"), show="headings", style="WM.Treeview", height=16)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(6,0))
        for c, t, w in [("mat","Kod materiału",200), ("nazwa","Nazwa z magazynu",260), ("ilosc","Ilość [szt]",120), ("dl","Długość [mm]",140)]:
            self.tree.heading(c, text=t); self.tree.column(c, width=w, anchor="w")

        # Lista materiałów do wyboru
        self._materials = _list_materialy_z_magazynu()

        # Stopka zapisu
        foot = ttk.Frame(self); foot.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))
        ttk.Button(foot, text="Zapisz produkt", command=self._save_current, style="WM.Side.TButton").pack(side="left")
        ttk.Button(foot, text="Zamknij", command=self.destroy, style="WM.Side.TButton").pack(side="right")

    # --- działania ---
    def _reload_lists(self):
        self._products = _list_produkty()
        self.listbox.delete(0, "end")
        for p in self._products:
            self.listbox.insert("end", f"{p['kod']} – {p['nazwa']}")

    def _get_sel_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def _load_selected(self):
        idx = self._get_sel_index()
        if idx is None: return
        p = self._products[idx]
        j = _read_json(p["_path"], {})
        self.var_kod.set(j.get("kod", p["kod"]))
        self.var_nazwa.set(j.get("nazwa", p["nazwa"]))
        # załaduj BOM
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for poz in j.get("BOM", []):
            mid = poz.get("kod_materialu","")
            nm  = self._name_for(mid)
            il  = poz.get("ilosc", 1)
            dl  = poz.get("dlugosc_mm", "")
            self.tree.insert("", "end", values=(mid, nm, il, dl))

    def _name_for(self, mat_id):
        for it in self._materials:
            if it["id"] == mat_id: return it["nazwa"]
        return ""

    def _new_product(self):
        nowy_kod = simpledialog.askstring("Nowy produkt", "Podaj kod (ID) produktu:", parent=self)
        if not nowy_kod: return
        self.var_kod.set(nowy_kod.strip())
        self.var_nazwa.set("")
        for iid in self.tree.get_children(): self.tree.delete(iid)

    def _delete_product(self):
        idx = self._get_sel_index()
        if idx is None:
            messagebox.showwarning("Produkty", "Zaznacz produkt do usunięcia."); return
        p = self._products[idx]
        if not messagebox.askyesno("Produkty", f"Usunąć produkt {p['kod']}?"):
            return
        try:
            os.remove(p["_path"])
        except Exception:
            pass
        self._reload_lists()
        self.var_kod.set(""); self.var_nazwa.set("")
        for iid in self.tree.get_children(): self.tree.delete(iid)

    def _add_row(self):
        # okienko wyboru materiału z listy magazynu + ilość + długość
        win = tk.Toplevel(self); win.title("Dodaj pozycję BOM"); apply_theme(win)
        frm = ttk.Frame(win); frm.pack(padx=10, pady=10, fill="x")
        ttk.Label(frm, text="Materiał:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        mat_ids  = [it["id"] for it in self._materials]
        mat_desc = [f"{it['id']} – {it['nazwa']}" for it in self._materials]
        var_mat  = tk.StringVar(value=mat_ids[0] if mat_ids else "")
        cb = ttk.Combobox(frm, values=mat_desc, state="readonly")
        cb.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        if mat_desc: cb.current(0)

        ttk.Label(frm, text="Ilość [szt]:", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_il = tk.StringVar(value="1")
        ttk.Entry(frm, textvariable=var_il, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Długość [mm] (opcjonalnie):", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        var_dl = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=var_dl, width=12).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        def _ok():
            try:
                idx = cb.current()
                if idx < 0:
                    messagebox.showwarning("BOM", "Wybierz materiał."); return
                mat_id = mat_ids[idx]
                mat_nm = self._materials[idx]["nazwa"]
                il = int(var_il.get())
                dl = var_dl.get().strip()
                dl = int(dl) if dl else ""
            except Exception:
                error_dialogs.show_error_dialog("BOM", "Podaj poprawną ilość/długość.")
                return
            self.tree.insert("", "end", values=(mat_id, mat_nm, il, dl))
            win.destroy()

        ttk.Button(frm, text="Dodaj", command=_ok, style="WM.Side.TButton").grid(row=3, column=0, columnspan=2, pady=(8,2))

    def _del_row(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("BOM", "Zaznacz wiersz BOM do usunięcia."); return
        for iid in sel:
            self.tree.delete(iid)

    def _save_current(self):
        kod = (self.var_kod.get() or "").strip()
        if not kod:
            messagebox.showwarning("Produkty", "Uzupełnij kod produktu."); return
        naz = (self.var_nazwa.get() or "").strip()
        if not naz:
            messagebox.showwarning("Produkty", "Uzupełnij nazwę."); return

        bom = []
        for iid in self.tree.get_children():
            mat, _nm, il, dl = self.tree.item(iid, "values")
            try:
                il = int(il)
                if il <= 0: raise ValueError
            except Exception:
                error_dialogs.show_error_dialog("BOM", "Ilość w BOM musi być dodatnią liczbą całkowitą.")
                return
            rec = {"kod_materialu": mat, "ilosc": il}
            if str(dl).strip() not in ("", "0"):
                try:
                    rec["dlugosc_mm"] = int(dl)
                except Exception:
                    error_dialogs.show_error_dialog("BOM", "Długość musi być liczbą (mm).")
                    return
            bom.append(rec)

        payload = {"kod": kod, "nazwa": naz, "BOM": bom}
        _write_json(os.path.join(DATA_DIR, f"{kod}.json"), payload)
        messagebox.showinfo("Produkty", f"Zapisano produkt {kod}.")
        self._reload_lists()

def open_panel_produkty(root):
    return ProduktyBOM(root)
