# Plik: gui_produkty.py
# Wersja pliku: 1.0.0
# Zmiany 1.0.0:
# - Nowy edytor produktów i półproduktów w osobnym oknie (Toplevel)
# - Zapis/odczyt plików w data/produkty/<kod>.json zgodnie ze strukturą:
#   {
#     "kod": "RAMAX",
#     "nazwa": "Rama X",
#     "polprodukty": [
#       {
#         "kod": "PP1",
#         "ilosc_na_szt": 2,
#         "czynnosci": ["ciecie"],
#         "surowiec": {"typ": "SR1", "dlugosc": 100}
#       }
#     ]
#   }
# ⏹ KONIEC KODU

import glob
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from utils.dirty_guard import DirtyGuard

from ui_theme import apply_theme_safe as apply_theme
from utils import error_dialogs
import logika_magazyn as LM
from utils.json_io import _ensure_dirs as _ensure_dirs_impl, _read_json, _write_json

DATA_DIR = os.path.join("data", "produkty")
MAG_DIR  = os.path.dirname(LM.MAGAZYN_PATH)

def _ensure_dirs():
    _ensure_dirs_impl(DATA_DIR, MAG_DIR)

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
    # akceptujemy dwa formaty: pliki per-materiał (RURA_FI30.json) lub zbiorczy magazyn.json
    items: list[dict] = []

    # 1) pliki per-materiał
    magazyn_file = os.path.basename(LM.MAGAZYN_PATH).lower()
    for p in glob.glob(os.path.join(MAG_DIR, "*.json")):
        base = os.path.basename(p)
        if base.lower() == magazyn_file or base.startswith("_"):
            continue
        j = _read_json(p, {})
        iid = j.get("kod") or os.path.splitext(base)[0]
        nm = j.get("nazwa", iid)
        items.append({"id": iid, "nazwa": nm})

    # 2) zbiorczy magazyn
    try:
        for it in LM.lista_items():
            items.append({"id": it.get("id"), "nazwa": it.get("nazwa", it.get("id"))})
    except Exception:
        pass

    # deduplikacja
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        if not it or it.get("id") in seen:
            continue
        seen.add(it["id"])
        out.append(it)
    return sorted(out, key=lambda x: x["id"])

class ProduktyBOM(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root)
        self._base_title = "Produkty (BOM)"
        self.title(self._base_title)
        self.geometry("1000x600+140+140")
        apply_theme(self)
        _ensure_dirs()
        self._build_ui()
        self._reload_lists()

        self.guard = DirtyGuard(
            self._base_title,
            on_save=lambda: (self._save_current(), self.guard.reset()),
            on_reset=lambda: (self._load_selected(), self.guard.reset()),
            on_dirty_change=lambda d: self.title(
                self._base_title + (" *" if d else "")
            ),
        )
        self.guard.watch(self)

        def _check():
            if self.guard.dirty:
                return messagebox.askyesno(
                    "Niezapisane zmiany",
                    "Porzucić niezapisane zmiany?",
                    parent=self,
                )
            return True

        self.guard.check_dirty = _check
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        print(f"[WM-DBG] {self.__class__.__name__}._build_ui")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Lewy panel: lista produktów
        left = ttk.Frame(self); left.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(10,6), pady=10)
        ttk.Label(left, text="Produkty", style="WM.Card.TLabel").pack(anchor="w")
        self.listbox = tk.Listbox(left, height=24)
        self.listbox.pack(fill="y", expand=False, pady=(6,6))
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._load_selected())

        btns = ttk.Frame(left); btns.pack(fill="x")
        ttk.Button(
            btns,
            text="Nowy",
            command=lambda: self.guard.check_dirty() and self._new_product(),
            style="WM.Side.TButton",
        ).pack(side="left", padx=2)
        ttk.Button(
            btns,
            text="Usuń",
            command=lambda: self.guard.check_dirty() and self._delete_product(),
            style="WM.Side.TButton",
        ).pack(side="left", padx=2)
        ttk.Button(
            btns,
            text="Zapisz",
            command=self.guard.on_save,
            style="WM.Side.TButton",
        ).pack(side="left", padx=2)

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
        ttk.Label(bar, text="Polprodukty", style="WM.Card.TLabel").pack(side="left")
        ttk.Button(bar, text="Dodaj wiersz", command=self._add_row, style="WM.Side.TButton").pack(side="right", padx=(6,2))
        ttk.Button(bar, text="Usuń wiersz", command=self._del_row, style="WM.Side.TButton").pack(side="right")

        self.tree = ttk.Treeview(
            center,
            columns=("kod", "ilosc", "czynnosci", "sr_typ", "sr_dlugosc"),
            show="headings",
            style="WM.Treeview",
            height=16,
        )
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(6,0))
        for c, t, w in [
            ("kod", "Kod PP", 140),
            ("ilosc", "Ilość/szt", 100),
            ("czynnosci", "Czynności", 200),
            ("sr_typ", "Surowiec", 140),
            ("sr_dlugosc", "Długość", 100),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")

        # Stopka zapisu
        foot = ttk.Frame(self); foot.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))
        ttk.Button(
            foot,
            text="Zapisz produkt",
            command=self.guard.on_save,
            style="WM.Side.TButton",
        ).pack(side="left")
        ttk.Button(
            foot,
            text="Zamknij",
            command=self._on_close,
            style="WM.Side.TButton",
        ).pack(side="right")

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
        if idx is None:
            return
        p = self._products[idx]
        j = _read_json(p["_path"], {})
        self.var_kod.set(j.get("kod", p["kod"]))
        self.var_nazwa.set(j.get("nazwa", p["nazwa"]))
        # załaduj półprodukty
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for poz in j.get("polprodukty", []):
            kod = poz.get("kod", "")
            il = poz.get("ilosc_na_szt", 1)
            cz = ", ".join(poz.get("czynnosci", []))
            sr = poz.get("surowiec", {})
            self.tree.insert(
                "",
                "end",
                values=(kod, il, cz, sr.get("typ", ""), sr.get("dlugosc", "")),
            )
        self.guard.reset()

    def _new_product(self):
        nowy_kod = simpledialog.askstring("Nowy produkt", "Podaj kod (ID) produktu:", parent=self)
        if not nowy_kod: return
        self.var_kod.set(nowy_kod.strip())
        self.var_nazwa.set("")
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.guard.reset()

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
        self.var_kod.set("")
        self.var_nazwa.set("")
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.guard.reset()

    def _add_row(self):
        win = tk.Toplevel(self)
        win.title("Dodaj półprodukt")
        apply_theme(win)
        frm = ttk.Frame(win)
        frm.pack(padx=10, pady=10, fill="x")

        ttk.Label(frm, text="Kod PP:", style="WM.Card.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        var_kod = tk.StringVar()
        ttk.Entry(frm, textvariable=var_kod).grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        ttk.Label(frm, text="Ilość na szt:", style="WM.Card.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        var_il = tk.StringVar(value="1")
        ttk.Entry(frm, textvariable=var_il, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Czynności (po przecinku):", style="WM.Card.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        var_cz = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=var_cz).grid(row=2, column=1, sticky="ew", padx=4, pady=4)

        ttk.Label(frm, text="Surowiec typ:", style="WM.Card.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        var_sr = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=var_sr).grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        ttk.Label(frm, text="Długość surowca:", style="WM.Card.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        var_dl = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=var_dl, width=12).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        def _ok():
            try:
                il = float(var_il.get())
                if il <= 0:
                    raise ValueError
                dl = var_dl.get().strip()
                dl = float(dl) if dl else ""
            except Exception:
                error_dialogs.show_error_dialog("BOM", "Podaj poprawne wartości.")
                return
            kod = var_kod.get().strip()
            sr_typ = var_sr.get().strip()
            if not kod or not sr_typ:
                messagebox.showwarning("BOM", "Uzupełnij kod i surowiec.")
                return
            cz = [c.strip() for c in var_cz.get().split(",") if c.strip()]
            self.tree.insert("", "end", values=(kod, il, ", ".join(cz), sr_typ, dl))
            self.guard.set_dirty()
            win.destroy()

        ttk.Button(frm, text="Dodaj", command=_ok, style="WM.Side.TButton").grid(
            row=5, column=0, columnspan=2, pady=(8, 2)
        )

    def _del_row(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("BOM", "Zaznacz wiersz BOM do usunięcia."); return
        for iid in sel:
            self.tree.delete(iid)
        self.guard.set_dirty()

    def _save_current(self):
        kod = (self.var_kod.get() or "").strip()
        if not kod:
            messagebox.showwarning("Produkty", "Uzupełnij kod produktu."); return
        naz = (self.var_nazwa.get() or "").strip()
        if not naz:
            messagebox.showwarning("Produkty", "Uzupełnij nazwę."); return

        polprodukty = []
        for iid in self.tree.get_children():
            kod_pp, il, cz, sr_typ, sr_dl = self.tree.item(iid, "values")
            try:
                il = float(il)
                if il <= 0:
                    raise ValueError
                sr_dl_val = float(sr_dl) if str(sr_dl).strip() not in ("", "0") else None
            except Exception:
                error_dialogs.show_error_dialog(
                    "BOM", "Ilości i długości muszą być liczbami."
                )
                return
            czynnosci = [c.strip() for c in str(cz).split(",") if c.strip()]
            sr = {"typ": sr_typ}
            if sr_dl_val is not None:
                sr["dlugosc"] = sr_dl_val
            polprodukty.append(
                {
                    "kod": kod_pp,
                    "ilosc_na_szt": il,
                    "czynnosci": czynnosci,
                    "surowiec": sr,
                }
            )

        payload = {"kod": kod, "nazwa": naz, "polprodukty": polprodukty}
        _write_json(os.path.join(DATA_DIR, f"{kod}.json"), payload)
        messagebox.showinfo("Produkty", f"Zapisano produkt {kod}.")
        self._reload_lists()
        self.guard.reset()

    def _on_close(self):
        if self.guard.check_dirty():
            self.destroy()

def open_panel_produkty(root):
    return ProduktyBOM(root)
