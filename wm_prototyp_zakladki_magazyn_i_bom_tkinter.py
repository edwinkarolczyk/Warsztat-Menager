# Wersja pliku: 2025-09-03.1
# Nazwa: gui_magazyn_bom.py
# Opis: Prototyp zakładki „Magazyn i BOM” (Surowce → Półprodukty → Produkty) dla Warsztat Menager
# Zgodnie z ustaleniami: pełne nazwy pól, brak skrótów; edytowalne w Ustawieniach.
# Ścieżki danych: 
#   - data/magazyn/surowce.json
#   - data/polprodukty/*.json
#   - data/produkty/*.json
# Motyw: ciemny (dark) + czerwone akcenty.
# ⏹ KONIEC KODU (nagłówek) – patrz stopka na końcu

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ===== Motyw (dark) =====
DARK_THEME = {
    "bg": "#111318",
    "bg2": "#171923",
    "fg": "#E5E7EB",
    "muted": "#9CA3AF",
    "accent": "#EF4444",
    "accent2": "#F87171",
    "frame": "#0B0D12",
    "border": "#23262F",
}

DATA_DIR = Path("data")
S_SOURCES = DATA_DIR / "magazyn" / "surowce.json"
S_HALFS = DATA_DIR / "polprodukty"
S_PRODUCTS = DATA_DIR / "produkty"

S_HALFS.mkdir(parents=True, exist_ok=True)
S_PRODUCTS.mkdir(parents=True, exist_ok=True)
S_SOURCES.parent.mkdir(parents=True, exist_ok=True)

# ====== Helpers JSON ======

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ====== Domenowe modele w pamięci ======
class WarehouseModel:
    """Model pamięci dla Surowców, Półproduktów i Produktów."""

    def __init__(self):
        # Surowce – pojedynczy plik JSON jako słownik {kod: {...}}
        self.surowce = load_json(S_SOURCES, {})
        # Półprodukty – każdy w osobnym pliku data/polprodukty/<kod>.json
        self.polprodukty = self._load_dir(S_HALFS)
        # Produkty – każdy w osobnym pliku data/produkty/<symbol>.json
        self.produkty = self._load_dir(S_PRODUCTS)

    def _load_dir(self, folder: Path):
        out = {}
        for p in folder.glob("*.json"):
            try:
                j = load_json(p, None)
                if isinstance(j, dict):
                    key = j.get("kod") or j.get("symbol") or p.stem
                    out[key] = j
            except Exception:
                pass
        return out

    # --- Surowce ---
    def add_or_update_surowiec(self, record):
        kod = record.get("kod")
        if not kod:
            raise ValueError("Pole 'kod' surowca jest wymagane.")
        self.surowce[kod] = record
        save_json(S_SOURCES, self.surowce)

    def delete_surowiec(self, kod):
        if kod in self.surowce:
            del self.surowce[kod]
            save_json(S_SOURCES, self.surowce)

    # --- Półprodukty ---
    def add_or_update_polprodukt(self, record):
        kod = record.get("kod")
        if not kod:
            raise ValueError("Pole 'kod' półproduktu jest wymagane.")
        self.polprodukty[kod] = record
        save_json(S_HALFS / f"{kod}.json", record)

    def delete_polprodukt(self, kod):
        if kod in self.polprodukty:
            del self.polprodukty[kod]
        p = S_HALFS / f"{kod}.json"
        if p.exists():
            p.unlink()

    # --- Produkty ---
    def add_or_update_produkt(self, record):
        symbol = record.get("symbol")
        if not symbol:
            raise ValueError("Pole 'symbol' produktu jest wymagane.")
        self.produkty[symbol] = record
        save_json(S_PRODUCTS / f"{symbol}.json", record)

    def delete_produkt(self, symbol):
        if symbol in self.produkty:
            del self.produkty[symbol]
        p = S_PRODUCTS / f"{symbol}.json"
        if p.exists():
            p.unlink()


# ====== GUI: Proste TreeView + formularze ======
class MagazynBOMWindow(tk.Toplevel):
    def __init__(self, master=None, model: WarehouseModel | None = None):
        super().__init__(master)
        self.title("Ustawienia – Magazyn i BOM")
        self.geometry("1280x720")
        self.configure(bg=DARK_THEME["bg"]) 
        self.model = model or WarehouseModel()

        self._build_style()
        self._build_layout()
        self._load_all()

    # --- Styl ---
    def _build_style(self):
        style = ttk.Style(self)
        # Użyj motywu 'clam' jako bazy
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=DARK_THEME["bg"]) 
        style.configure("Card.TFrame", background=DARK_THEME["bg2"], relief="solid", borderwidth=1)
        style.configure("Header.TLabel", background=DARK_THEME["bg2"], foreground=DARK_THEME["fg"], font=("Segoe UI", 12, "bold"))
        style.configure("TLabel", background=DARK_THEME["bg2"], foreground=DARK_THEME["fg"], font=("Segoe UI", 10))
        style.configure("TButton", background=DARK_THEME["accent"], foreground="#ffffff")
        style.map("TButton", background=[("active", DARK_THEME["accent2"])])
        style.configure("Treeview", background=DARK_THEME["frame"], fieldbackground=DARK_THEME["frame"], foreground=DARK_THEME["fg"], bordercolor=DARK_THEME["border"], borderwidth=1)
        style.configure("Treeview.Heading", background=DARK_THEME["bg2"], foreground=DARK_THEME["fg"], relief="flat")

    # --- Układ ---
    def _build_layout(self):
        # Top: nagłówek
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(header, text="Magazyn i BOM – Surowce, Półprodukty, Produkty", style="Header.TLabel").pack(side="left", padx=12, pady=8)

        # Main – trzy kolumny
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=(6,12))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)

        # Kolumna 1: Surowce
        self.frame_surowce = self._make_card(main)
        self.frame_surowce.grid(row=0, column=0, sticky="nsew", padx=(0,6))
        self._build_surowce(self.frame_surowce)

        # Kolumna 2: Półprodukty
        self.frame_polprodukty = self._make_card(main)
        self.frame_polprodukty.grid(row=0, column=1, sticky="nsew", padx=6)
        self._build_polprodukty(self.frame_polprodukty)

        # Kolumna 3: Produkty
        self.frame_produkty = self._make_card(main)
        self.frame_produkty.grid(row=0, column=2, sticky="nsew", padx=(6,0))
        self._build_produkty(self.frame_produkty)

    def _make_card(self, parent):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)
        return f

    # --- Sekcja: Surowce ---
    def _build_surowce(self, parent):
        # Header
        bar = ttk.Frame(parent, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(bar, text="Surowce (rodzaj, rozmiar, długość, jednostka, ilość, próg alertu)", style="Header.TLabel").pack(side="left")
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_surowiec).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_surowiec).pack(side="right", padx=4)

        # Lista
        cols = ("kod","nazwa","rodzaj","rozmiar","dlugosc","jednostka","ilosc","prog_alertu_procent")
        self.tree_surowce = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_surowce.grid(row=1, column=0, sticky="nsew", padx=8)
        for c in cols:
            self.tree_surowce.heading(c, text=c)
            self.tree_surowce.column(c, width=110, anchor="w")
        self.tree_surowce.bind("<<TreeviewSelect>>", self._on_surowiec_select)

        # Formularz
        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self.s_vars = {k: tk.StringVar() for k in cols}
        grid = [
            ("kod","Kod"), ("nazwa","Nazwa"), ("rodzaj","Rodzaj"), ("rozmiar","Rozmiar"),
            ("dlugosc","Długość"), ("jednostka","Jednostka miary"), ("ilosc","Ilość"), ("prog_alertu_procent","Próg alertu [%]")
        ]
        for i,(key,label) in enumerate(grid):
            ttk.Label(form, text=label).grid(row=i//2*2, column=(i%2)*2, sticky="w", padx=6, pady=2)
            ttk.Entry(form, textvariable=self.s_vars[key]).grid(row=i//2*2, column=(i%2)*2+1, sticky="ew", padx=6, pady=2)
        for c in range(4):
            form.columnconfigure(c, weight=1)

    def _on_surowiec_select(self, _):
        sel = self.tree_surowce.selection()
        if not sel:
            return
        vals = self.tree_surowce.item(sel[0], "values")
        keys = ("kod","nazwa","rodzaj","rozmiar","dlugosc","jednostka","ilosc","prog_alertu_procent")
        for k,v in zip(keys, vals):
            self.s_vars[k].set(v)

    def _save_surowiec(self):
        try:
            rec = {k: (v.get() or "").strip() for k, v in self.s_vars.items()}
            for field in ("kod", "nazwa", "rodzaj", "jednostka"):
                if not rec.get(field):
                    messagebox.showerror("Surowce", f"Pole '{field}' jest wymagane.")
                    return
            for field in ("dlugosc", "ilosc", "prog_alertu_procent"):
                val = rec.get(field, "")
                if val == "":
                    num = 0
                else:
                    try:
                        num = float(val) if field == "dlugosc" else int(val)
                    except Exception:
                        messagebox.showerror(
                            "Surowce", f"Pole '{field}' musi być liczbą."
                        )
                        return
                    if num < 0:
                        messagebox.showerror(
                            "Surowce", f"Pole '{field}' musi być ≥ 0."
                        )
                        return
                rec[field] = num if field == "dlugosc" else int(num)
            self.model.add_or_update_surowiec(rec)
            self._load_surowce()
        except Exception as e:
            messagebox.showerror("Błąd zapisu surowca", str(e))

    def _delete_surowiec(self):
        kod = self.s_vars["kod"].get()
        if not kod:
            return
        if messagebox.askyesno("Potwierdź", f"Usunąć surowiec '{kod}'?"):
            self.model.delete_surowiec(kod)
            self._load_surowce()

    # --- Sekcja: Półprodukty ---
    def _build_polprodukty(self, parent):
        bar = ttk.Frame(parent, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(bar, text="Półprodukty (kod, nazwa, surowiec, czynności, norma strat)", style="Header.TLabel").pack(side="left")
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_polprodukt).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_polprodukt).pack(side="right", padx=4)

        cols = ("kod","nazwa","surowiec_kod","surowiec_typ","surowiec_rozmiar","surowiec_dlugosc","czynnosci","norma_strat_procent")
        self.tree_pp = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_pp.grid(row=1, column=0, sticky="nsew", padx=8)
        for c in cols:
            self.tree_pp.heading(c, text=c)
            self.tree_pp.column(c, width=120, anchor="w")
        self.tree_pp.bind("<<TreeviewSelect>>", self._on_pp_select)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self.pp_vars = {
            "kod": tk.StringVar(),
            "nazwa": tk.StringVar(),
            "surowiec_kod": tk.StringVar(),
            "surowiec_typ": tk.StringVar(),
            "surowiec_rozmiar": tk.StringVar(),
            "surowiec_dlugosc": tk.StringVar(),
            "czynnosci": tk.StringVar(),  # wpisywane po przecinku
            "norma_strat_procent": tk.StringVar(),
        }
        labels = [
            ("kod","Kod"), ("nazwa","Nazwa"), ("surowiec_kod","Kod surowca źródłowego"),
            ("surowiec_typ","Rodzaj surowca (profil, rura, pręt, blacha)"),
            ("surowiec_rozmiar","Wymiary/rozmiar surowca"), ("surowiec_dlugosc","Długość surowca"),
            ("czynnosci","Lista czynności technologicznych (po przecinku)"),
            ("norma_strat_procent","Norma strat [%]")
        ]
        for i,(key,label) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            ttk.Entry(form, textvariable=self.pp_vars[key]).grid(row=i, column=1, sticky="ew", padx=6, pady=2)
        form.columnconfigure(1, weight=1)

    def _on_pp_select(self, _):
        sel = self.tree_pp.selection()
        if not sel:
            return
        vals = self.tree_pp.item(sel[0], "values")
        keys = ("kod","nazwa","surowiec_kod","surowiec_typ","surowiec_rozmiar","surowiec_dlugosc","czynnosci","norma_strat_procent")
        for k,v in zip(keys, vals):
            self.pp_vars[k].set(v)

    def _save_polprodukt(self):
        try:
            kod = self.pp_vars["kod"].get().strip()
            nazwa = self.pp_vars["nazwa"].get().strip()
            sr_kod = self.pp_vars["surowiec_kod"].get().strip()
            if not kod or not nazwa or not sr_kod:
                messagebox.showerror(
                    "Półprodukty", "Wymagane pola: kod, nazwa i kod surowca."
                )
                return
            dl_txt = self.pp_vars["surowiec_dlugosc"].get().strip()
            if dl_txt:
                try:
                    dl = float(dl_txt)
                except Exception:
                    messagebox.showerror(
                        "Półprodukty", "Długość surowca musi być liczbą."
                    )
                    return
                if dl < 0:
                    messagebox.showerror(
                        "Półprodukty", "Długość surowca musi być ≥ 0."
                    )
                    return
            else:
                dl = 0
            try:
                norma = int(self.pp_vars["norma_strat_procent"].get() or 0)
            except Exception:
                messagebox.showerror(
                    "Półprodukty", "Norma strat musi być liczbą."
                )
                return
            if not 0 <= norma <= 100:
                messagebox.showerror(
                    "Półprodukty", "Norma strat musi być w zakresie 0–100."
                )
                return
            rec = {
                "kod": kod,
                "nazwa": nazwa,
                "surowiec": {
                    "kod": sr_kod,
                    "typ": self.pp_vars["surowiec_typ"].get().strip(),
                    "rozmiar": self.pp_vars["surowiec_rozmiar"].get().strip(),
                    "dlugosc": dl,
                    "jednostka": "szt",
                },
                "czynnosci": [
                    s.strip() for s in self.pp_vars["czynnosci"].get().split(",") if s.strip()
                ],
                "norma_strat_procent": norma,
            }
            self.model.add_or_update_polprodukt(rec)
            self._load_polprodukty()
        except Exception as e:
            messagebox.showerror("Błąd zapisu półproduktu", str(e))

    def _delete_polprodukt(self):
        kod = self.pp_vars["kod"].get()
        if not kod:
            return
        if messagebox.askyesno("Potwierdź", f"Usunąć półprodukt '{kod}'?"):
            self.model.delete_polprodukt(kod)
            self._load_polprodukty()

    # --- Sekcja: Produkty ---
    def _build_produkty(self, parent):
        bar = ttk.Frame(parent, style="Card.TFrame")
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(bar, text="Produkty (symbol, nazwa, BOM)", style="Header.TLabel").pack(side="left")
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_produkt).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_produkt).pack(side="right", padx=4)

        cols = ("symbol","nazwa","BOM")
        self.tree_prod = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_prod.grid(row=1, column=0, sticky="nsew", padx=8)
        for c in cols:
            self.tree_prod.heading(c, text=c)
            self.tree_prod.column(c, width=140, anchor="w")
        self.tree_prod.bind("<<TreeviewSelect>>", self._on_prod_select)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self.p_vars = {
            "symbol": tk.StringVar(),
            "nazwa": tk.StringVar(),
            "bom_text": tk.StringVar(),  # format: typ=polprodukt;kod=DRUT_30_GWINT;ilosc=2 | typ=surowiec;kod=SRUBA_M12;ilosc=4
        }
        ttk.Label(form, text="Symbol").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(form, textvariable=self.p_vars["symbol"]).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(form, text="Nazwa").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(form, textvariable=self.p_vars["nazwa"]).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(form, text="BOM (pozycje rozdzielone pionową kreską '|')\nnp.: typ=polprodukt;kod=DRUT_30_GWINT;ilosc=2 | typ=surowiec;kod=SRUBA_M12;ilosc=4").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(form, textvariable=self.p_vars["bom_text"]).grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        form.columnconfigure(1, weight=1)

    def _on_prod_select(self, _):
        sel = self.tree_prod.selection()
        if not sel:
            return
        symbol, nazwa, bom = self.tree_prod.item(sel[0], "values")
        self.p_vars["symbol"].set(symbol)
        self.p_vars["nazwa"].set(nazwa)
        self.p_vars["bom_text"].set(bom)

    def _save_produkt(self):
        try:
            symbol = self.p_vars["symbol"].get().strip()
            nazwa = self.p_vars["nazwa"].get().strip()
            if not symbol or not nazwa:
                messagebox.showerror(
                    "Produkty", "Wymagane pola: symbol i nazwa."
                )
                return
            bom_text = self.p_vars["bom_text"].get()
            bom_list = self._parse_bom_text(bom_text)
            if not bom_list:
                messagebox.showerror(
                    "Produkty", "BOM musi mieć co najmniej jedną pozycję."
                )
                return
            record = {"symbol": symbol, "nazwa": nazwa, "BOM": bom_list}
            self.model.add_or_update_produkt(record)
            self._load_produkty()
        except Exception as e:
            messagebox.showerror("Błąd zapisu produktu", str(e))

    def _delete_produkt(self):
        symbol = self.p_vars["symbol"].get()
        if not symbol:
            return
        if messagebox.askyesno("Potwierdź", f"Usunąć produkt '{symbol}'?"):
            self.model.delete_produkt(symbol)
            self._load_produkty()

    # --- Parsowanie BOM z prostego pola tekstowego ---
    def _parse_bom_text(self, text: str):
        # Format: "typ=polprodukt;kod=DRUT_30_GWINT;ilosc=2 | typ=surowiec;kod=SRUBA_M12;ilosc=4"
        out = []
        for chunk in [c.strip() for c in text.split("|") if c.strip()]:
            item = {}
            for part in [p.strip() for p in chunk.split(";") if p.strip()]:
                if "=" in part:
                    k,v = part.split("=", 1)
                    item[k.strip()] = v.strip()
            if item:
                # konwersja liczby
                if "ilosc" in item:
                    try:
                        item["ilosc_na_sztuke"] = int(item.pop("ilosc"))
                    except Exception:
                        item["ilosc_na_sztuke"] = 1
                # aliasy kluczy
                if "typ" not in item:
                    item["typ"] = "polprodukt"
                if "kod" not in item:
                    raise ValueError("Każda pozycja BOM musi mieć klucz 'kod'.")
                out.append({k: item[k] for k in ("typ","kod","ilosc_na_sztuke") if k in item})
        return out

    # --- Ładowanie tabel ---
    def _load_all(self):
        self._load_surowce()
        self._load_polprodukty()
        self._load_produkty()

    def _load_surowce(self):
        for i in self.tree_surowce.get_children():
            self.tree_surowce.delete(i)
        for kod, rec in sorted(self.model.surowce.items()):
            ilosc = int(rec.get("ilosc", 0) or 0)
            prog = int(rec.get("prog_alertu_procent", 0) or 0)
            row = (
                kod,
                rec.get("nazwa", ""),
                rec.get("rodzaj", ""),
                rec.get("rozmiar", ""),
                rec.get("dlugosc", ""),
                rec.get("jednostka", ""),
                ilosc,
                prog,
            )
            tags = ("alert",) if ilosc <= prog else ()
            self.tree_surowce.insert("", "end", values=row, tags=tags)
        self.tree_surowce.tag_configure(
            "alert", background=DARK_THEME.get("accent2", "#F87171")
        )

    def _load_polprodukty(self):
        for i in self.tree_pp.get_children():
            self.tree_pp.delete(i)
        for kod, rec in sorted(self.model.polprodukty.items()):
            su = rec.get("surowiec", {})
            row = (
                kod,
                rec.get("nazwa",""),
                su.get("kod",""),
                su.get("typ",""),
                su.get("rozmiar",""),
                su.get("dlugosc",""),
                ", ".join(rec.get("czynnosci", [])),
                rec.get("norma_strat_procent",0),
            )
            self.tree_pp.insert("", "end", values=row)

    def _load_produkty(self):
        for i in self.tree_prod.get_children():
            self.tree_prod.delete(i)
        for symbol, rec in sorted(self.model.produkty.items()):
            # Skrótowe pokazanie BOM w jednej kolumnie
            bom_text = " | ".join([f"{i.get('typ','?')}:{i.get('kod','?')} x{i.get('ilosc_na_sztuke',1)}" for i in rec.get("BOM",[])])
            self.tree_prod.insert("", "end", values=(symbol, rec.get("nazwa",""), bom_text))


# ====== Uruchomienie testowe okna ======
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # chowamy główne okno
    w = MagazynBOMWindow(root)
    w.mainloop()

# ⏹ KONIEC KODU
