"""Simple GUI for managing warehouse and BOM data.

This module provides three sections (raw materials, semi-finished,
and products) each displayed in a Treeview with forms for editing.
Data is persisted in data/magazyn, data/polprodukty, data/produkty.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from ui_theme import ensure_theme_applied

from config.paths import get_path
from config_manager import ConfigManager
from ui_utils import _msg_error
from wm_log import dbg as wm_dbg, err as wm_err

# Paths
DATA_DIR = Path("data")


def load_bom():
    path = get_path("bom.file")
    try:
        with open(path, "r", encoding="utf-8") as f:
            bom = json.load(f)
        wm_dbg(
            "gui.bom",
            "bom loaded",
            path=path,
            items=len(bom) if isinstance(bom, list) else 1,
        )
        return bom
    except Exception as e:  # pragma: no cover - logowanie błędów
        wm_err("gui.bom", "bom load failed", e, path=path)
        return []


def _load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _save_ops(lb: tk.Listbox) -> None:
    """Save operations from listbox to ``DATA_DIR/czynnosci.json``."""
    ops = list(lb.get(0, tk.END))
    path = DATA_DIR / "czynnosci.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ops, fh, ensure_ascii=False, indent=2)
    messagebox.showinfo("Czynności", "Zapisano czynności technologiczne.")


class WarehouseModel:
    """In-memory representation of warehouse, semi-finished and products."""

    def __init__(self):
        self.data_dir = DATA_DIR
        self.src_file = self.data_dir / "magazyn" / "surowce.json"
        self.pol_dir = self.data_dir / "polprodukty"
        self.prd_dir = self.data_dir / "produkty"
        for p in (self.src_file.parent, self.pol_dir, self.prd_dir):
            p.mkdir(parents=True, exist_ok=True)
        data = _load_json(self.src_file, [])
        if isinstance(data, list):
            self.surowce = {
                rec.get("kod"): rec
                for rec in data
                if isinstance(rec, dict) and rec.get("kod")
            }
        elif isinstance(data, dict):
            self.surowce = {
                k: v for k, v in data.items() if isinstance(v, dict)
            }
        else:
            self.surowce = {}
        self.polprodukty = self._load_dir(self.pol_dir)
        self.produkty = self._load_dir(self.prd_dir)
        self._load_bom_file()

    @staticmethod
    def _load_dir(folder: Path) -> dict:
        out: dict[str, dict] = {}
        for pth in folder.glob("*.json"):
            data = _load_json(pth, None)
            if isinstance(data, dict):
                key = data.get("kod") or data.get("symbol") or pth.stem
                out[key] = data
        return out

    # ------------------------------------------------------------------
    def _load_bom_file(self) -> None:
        """Augment product definitions with entries from the configured BOM file."""

        path_str = get_path("bom.file")
        if not path_str:
            return
        bom_path = Path(path_str)
        payload = load_bom()
        if not payload:
            return

        for record in self._normalise_bom_payload(payload, bom_path):
            symbol = record.get("symbol")
            if not symbol:
                continue
            current = self.produkty.get(symbol, {})
            merged = {**current, **record}
            merged.setdefault("_path", str(bom_path))
            self.produkty[symbol] = merged

    # ------------------------------------------------------------------
    def _normalise_bom_payload(self, payload, source: Path) -> list[dict]:
        """Return list of product dicts parsed from ``payload``."""

        def _iter_records(data):
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield item
                return
            if isinstance(data, dict):
                for key in ("produkty", "products", "items", "data"):
                    value = data.get(key)
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                yield item
                        return
                yield data

        records: list[dict] = []
        for raw in _iter_records(payload):
            symbol = raw.get("symbol") or raw.get("kod")
            if not symbol:
                continue
            record = {
                "symbol": symbol,
                "nazwa": raw.get("nazwa") or raw.get("name") or symbol,
                "polprodukty": self._normalise_polprodukty(raw.get("polprodukty")),
                "czynnosci": list(raw.get("czynnosci") or raw.get("operations") or []),
                "_path": str(source),
            }
            records.append(record)
        return records

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_polprodukty(data) -> list[dict]:
        """Normalise various BOM formats to list of dict entries."""

        def _coerce_qty(raw):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return raw

        if isinstance(data, dict):
            items = []
            for kod, value in data.items():
                entry = {"kod": kod, "ilosc_na_szt": _coerce_qty(value)}
                items.append(entry)
            return items
        if not isinstance(data, list):
            return []

        normalised: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            kod = item.get("kod") or item.get("id") or item.get("symbol")
            if not kod:
                continue
            qty = (
                item.get("ilosc_na_szt")
                or item.get("ilosc")
                or item.get("ilosc_na_sztuke")
                or item.get("qty")
                or item.get("quantity")
                or 0
            )
            entry: dict = {
                "kod": kod,
                "ilosc_na_szt": _coerce_qty(qty),
                "czynnosci": list(item.get("czynnosci") or item.get("operations") or []),
            }
            surowiec = item.get("surowiec") or item.get("material") or {}
            if isinstance(surowiec, dict):
                entry["surowiec"] = {
                    "typ": surowiec.get("typ") or surowiec.get("material"),
                    "dlugosc": surowiec.get("dlugosc") or surowiec.get("length"),
                    "jednostka": surowiec.get("jednostka") or surowiec.get("unit"),
                    "kod": surowiec.get("kod"),
                }
            normalised.append(entry)
        return normalised

    # Surowce
    def add_or_update_surowiec(self, record: dict) -> None:
        kod = record.get("kod")
        if not kod:
            raise ValueError("Pole 'kod' surowca jest wymagane.")
        self.surowce[kod] = record
        _save_json(self.src_file, list(self.surowce.values()))

    def delete_surowiec(self, kod: str) -> None:
        if kod in self.surowce:
            del self.surowce[kod]
            _save_json(self.src_file, list(self.surowce.values()))

    # Półprodukty
    def add_or_update_polprodukt(self, record: dict) -> None:
        kod = record.get("kod")
        if not kod:
            raise ValueError("Pole 'kod' półproduktu jest wymagane.")
        self.polprodukty[kod] = record
        _save_json(self.pol_dir / f"{kod}.json", record)

    def delete_polprodukt(self, kod: str) -> None:
        if kod in self.polprodukty:
            del self.polprodukty[kod]
        p = self.pol_dir / f"{kod}.json"
        if p.exists():
            p.unlink()

    # Produkty
    def add_or_update_produkt(self, record: dict) -> None:
        symbol = record.get("symbol")
        if not symbol:
            raise ValueError("Pole 'symbol' produktu jest wymagane.")
        self.produkty[symbol] = record
        _save_json(self.prd_dir / f"{symbol}.json", record)

    def delete_produkt(self, symbol: str) -> None:
        if symbol in self.produkty:
            del self.produkty[symbol]
        p = self.prd_dir / f"{symbol}.json"
        if p.exists():
            p.unlink()


class MagazynBOM(ttk.Frame):
    """Main frame with three sections: raw materials, semi-finished, products."""

    def __init__(self, master: tk.Misc | None = None, model: WarehouseModel | None = None):
        super().__init__(master)
        self.model = model or WarehouseModel()
        self._build_ui()
        self._load_all()

    def _build_ui(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        frm_sr = ttk.Frame(nb)
        frm_pp = ttk.Frame(nb)
        frm_pr = ttk.Frame(nb)
        nb.add(frm_sr, text="Surowce")
        nb.add(frm_pp, text="Półprodukty")
        nb.add(frm_pr, text="Produkty")

        self._build_surowce(frm_sr)
        self._build_polprodukty(frm_pp)
        self._build_produkty(frm_pr)

    # --- Surowce ---
    def _build_surowce(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_surowiec).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_surowiec).pack(side="right", padx=4)

        cols = ("kod","nazwa","rodzaj","rozmiar","dlugosc","jednostka","stan","prog_alertu")
        self.tree_sr = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_sr.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("kod","Kod"),
            ("nazwa","Nazwa"),
            ("rodzaj","Rodzaj"),
            ("rozmiar","Rozmiar"),
            ("dlugosc","Długość"),
            ("jednostka","Jednostka miary"),
            ("stan","Stan"),
            ("prog_alertu","Próg alertu [%]")
        ]
        for key, lbl in headers:
            self.tree_sr.heading(key, text=lbl)
            self.tree_sr.column(key, width=100, anchor="w")
        self.tree_sr.bind("<<TreeviewSelect>>", self._on_sr_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.s_vars = {k: tk.StringVar() for k,_ in headers}
        for i,(key,label) in enumerate(headers):
            ttk.Label(form, text=label).grid(row=i//2, column=(i%2)*2, sticky="w", padx=4, pady=2)
            ttk.Entry(form, textvariable=self.s_vars[key]).grid(row=i//2, column=(i%2)*2+1, sticky="ew", padx=4, pady=2)
        for c in range(4):
            form.columnconfigure(c, weight=1)

    def _on_sr_select(self, _event) -> None:
        sel = self.tree_sr.selection()
        if sel:
            values = self.tree_sr.item(sel[0], "values")
            keys = ("kod","nazwa","rodzaj","rozmiar","dlugosc","jednostka","stan","prog_alertu")
            for k,v in zip(keys, values):
                self.s_vars[k].set(v)

    def _save_surowiec(self) -> None:
        rec = {k: (v.get() or "").strip() for k, v in self.s_vars.items()}
        for field in ("kod","nazwa","rodzaj","jednostka"):
            if not rec.get(field):
                _msg_error(self, "Surowce", f"Pole '{field}' jest wymagane.")
                return
        try:
            rec["dlugosc"] = float(rec.get("dlugosc") or 0)
            rec["stan"] = int(rec.get("stan") or 0)
            rec["prog_alertu"] = int(rec.get("prog_alertu") or 0)
        except ValueError:
            _msg_error(
                self,
                "Surowce",
                "Pola liczby muszą zawierać wartości numeryczne.",
            )
            return
        self.model.add_or_update_surowiec(rec)
        self._load_surowce()

    def _delete_surowiec(self) -> None:
        kod = self.s_vars["kod"].get()
        if kod and messagebox.askyesno(
            "Potwierdź", f"Usunąć surowiec '{kod}'?", parent=self
        ):
            self.model.delete_surowiec(kod)
            self._load_surowce()

    # --- Półprodukty ---
    def _build_polprodukty(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_polprodukt).pack(
            side="right", padx=4
        )
        ttk.Button(bar, text="Usuń", command=self._delete_polprodukt).pack(
            side="right", padx=4
        )

        cols = (
            "kod",
            "nazwa",
            "sr_kod",
            "sr_ilosc",
            "sr_jednostka",
            "czynnosci",
            "norma_strat",
        )
        self.tree_pp = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_pp.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("kod", "Kod"),
            ("nazwa", "Nazwa"),
            ("sr_kod", "Kod surowca"),
            ("sr_ilosc", "Ilość surowca na szt."),
            ("sr_jednostka", "Jednostka"),
            ("czynnosci", "Lista czynności"),
            ("norma_strat", "Norma strat [%]"),
        ]
        for key, lbl in headers:
            self.tree_pp.heading(key, text=lbl)
            self.tree_pp.column(key, width=120, anchor="w")
        self.tree_pp.bind("<<TreeviewSelect>>", self._on_pp_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.pp_vars = {k: tk.StringVar() for k, _ in headers if k != "czynnosci"}
        self.pp_ops = ConfigManager().get("czynnosci_technologiczne", [])
        for i, (key, label) in enumerate(headers):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", padx=4, pady=2)
            if key == "czynnosci":
                self.pp_lb = tk.Listbox(form, selectmode="multiple", exportselection=False)
                for op in self.pp_ops:
                    self.pp_lb.insert(tk.END, op)
                self.pp_lb.grid(row=i, column=1, sticky="ew", padx=4, pady=2)
            else:
                tk.Entry(form, textvariable=self.pp_vars[key]).grid(
                    row=i, column=1, sticky="ew", padx=4, pady=2
                )
        tk.Button(form, text="Zapisz", command=self._save_polprodukt).grid(
            row=len(headers), column=1, sticky="e", padx=4, pady=4
        )
        form.columnconfigure(1, weight=1)

    def _on_pp_select(self, _event) -> None:
        sel = self.tree_pp.selection()
        if sel:
            values = self.tree_pp.item(sel[0], "values")
            keys = (
                "kod",
                "nazwa",
                "sr_kod",
                "sr_ilosc",
                "sr_jednostka",
                "czynnosci",
                "norma_strat",
            )
            for k, v in zip(keys, values):
                if k == "czynnosci":
                    selected = [s.strip() for s in v.split(",") if s.strip()]
                    self.pp_lb.selection_clear(0, tk.END)
                    for idx, op in enumerate(self.pp_ops):
                        if op in selected:
                            self.pp_lb.selection_set(idx)
                else:
                    self.pp_vars[k].set(v)

    def _save_polprodukt(self) -> None:
        kod = self.pp_vars["kod"].get().strip()
        nazwa = self.pp_vars["nazwa"].get().strip()
        sr_kod = self.pp_vars["sr_kod"].get().strip()
        sr_ilosc = self.pp_vars["sr_ilosc"].get().strip()
        sr_jedn = self.pp_vars["sr_jednostka"].get().strip()
        if not (kod and nazwa and sr_kod and sr_ilosc and sr_jedn):
            _msg_error(
                self,
                "Półprodukty",
                "Wymagane pola: kod, nazwa, kod surowca, ilość i jednostka.",
            )
            return
        try:
            sr_ilosc_val = float(sr_ilosc)
        except ValueError:
            _msg_error(self, "Półprodukty", "Ilość surowca musi być liczbą.")
            return
        try:
            norma = int(self.pp_vars["norma_strat"].get() or 0)
        except ValueError:
            _msg_error(self, "Półprodukty", "Norma strat musi być liczbą.")
            return
        rec = {
            "kod": kod,
            "nazwa": nazwa,
            "surowiec": {
                "kod": sr_kod,
                "ilosc_na_szt": sr_ilosc_val,
                "jednostka": sr_jedn,
            },
            "czynnosci": [self.pp_lb.get(i) for i in self.pp_lb.curselection()],
            "norma_strat_procent": norma,
        }
        self.model.add_or_update_polprodukt(rec)
        self._load_polprodukty()

    def _delete_polprodukt(self) -> None:
        kod = self.pp_vars["kod"].get()
        if kod and messagebox.askyesno(
            "Potwierdź", f"Usunąć półprodukt '{kod}'?", parent=self
        ):
            self.model.delete_polprodukt(kod)
            self._load_polprodukty()

    # --- Produkty ---
    def _build_produkty(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_produkt).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_produkt).pack(side="right", padx=4)

        cols = ("symbol","nazwa","bom")
        self.tree_pr = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_pr.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("symbol","Symbol"),
            ("nazwa","Nazwa"),
            ("bom","BOM")
        ]
        for key,lbl in headers:
            self.tree_pr.heading(key, text=lbl)
            self.tree_pr.column(key, width=140, anchor="w")
        self.tree_pr.bind("<<TreeviewSelect>>", self._on_pr_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.pr_vars = {k: tk.StringVar() for k,_ in headers}
        ttk.Label(form, text="Symbol").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["symbol"]).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(form, text="Nazwa").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["nazwa"]).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(
            form,
            text="BOM (pozycje rozdzielone pionową kreską '|',\nnp.: typ=polprodukt;kod=DRUT;ilosc=2)"
        ).grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["bom"]).grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        form.columnconfigure(1, weight=1)

    def _on_pr_select(self, _event) -> None:
        sel = self.tree_pr.selection()
        if sel:
            values = self.tree_pr.item(sel[0], "values")
            keys = ("symbol","nazwa","bom")
            for k,v in zip(keys, values):
                self.pr_vars[k].set(v)

    def _save_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        nazwa = self.pr_vars["nazwa"].get().strip()
        if not symbol or not nazwa:
            _msg_error(self, "Produkty", "Wymagane pola: symbol i nazwa.")
            return
        bom_list = self._parse_bom(self.pr_vars["bom"].get())
        if not bom_list:
            _msg_error(self, "Produkty", "BOM musi mieć co najmniej jedną pozycję.")
            return
        rec = {"symbol": symbol, "nazwa": nazwa, "BOM": bom_list}
        self.model.add_or_update_produkt(rec)
        self._load_produkty()

    def _delete_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get()
        if symbol and messagebox.askyesno(
            "Potwierdź", f"Usunąć produkt '{symbol}'?", parent=self
        ):
            self.model.delete_produkt(symbol)
            self._load_produkty()

    def _parse_bom(self, text: str) -> list:
        out: list[dict] = []
        for chunk in [c.strip() for c in text.split("|") if c.strip()]:
            item: dict[str, str] = {}
            for part in [p.strip() for p in chunk.split(";") if p.strip()]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    item[k.strip()] = v.strip()
            if item:
                if "kod" not in item:
                    raise ValueError("Każda pozycja BOM musi mieć klucz 'kod'.")
                qty = item.get("ilosc") or item.get("ilosc_na_sztuke") or "1"
                try:
                    item["ilosc_na_sztuke"] = int(qty)
                except ValueError:
                    item["ilosc_na_sztuke"] = 1
                item["typ"] = item.get("typ", "polprodukt")
                out.append({k: item[k] for k in ("typ","kod","ilosc_na_sztuke")})
        return out

    def _load_all(self) -> None:
        self._load_surowce()
        self._load_polprodukty()
        self._load_produkty()

    def _load_surowce(self) -> None:
        for i in self.tree_sr.get_children():
            self.tree_sr.delete(i)
        for kod, rec in sorted(self.model.surowce.items()):
            row = (
                kod,
                rec.get("nazwa", ""),
                rec.get("rodzaj", ""),
                rec.get("rozmiar", ""),
                rec.get("dlugosc", ""),
                rec.get("jednostka", ""),
                rec.get("stan", 0),
                rec.get("prog_alertu", 0),
            )
            self.tree_sr.insert("", "end", values=row)

    def _load_polprodukty(self) -> None:
        for i in self.tree_pp.get_children():
            self.tree_pp.delete(i)
        for kod, rec in sorted(self.model.polprodukty.items()):
            surowiec = rec.get("surowiec", {})
            row = (
                kod,
                rec.get("nazwa", ""),
                surowiec.get("kod", ""),
                surowiec.get("ilosc_na_szt", ""),
                surowiec.get("jednostka", ""),
                ", ".join(rec.get("czynnosci", [])),
                rec.get("norma_strat_procent", 0),
            )
            self.tree_pp.insert("", "end", values=row)

    def _load_produkty(self) -> None:
        for i in self.tree_pr.get_children():
            self.tree_pr.delete(i)
        for symbol, rec in sorted(self.model.produkty.items()):
            bom_txt = " | ".join(
                f"{i.get('typ','?')}:{i.get('kod','?')} x{i.get('ilosc_na_sztuke',1)}"
                for i in rec.get("BOM", [])
            )
            self.tree_pr.insert("", "end", values=(symbol, rec.get("nazwa",""), bom_txt))


def make_window(root: tk.Misc) -> ttk.Frame:
    """Return frame with Magazyn/BOM management."""
    win = MagazynBOM(root)
    win.lb = tk.Listbox(win)
    for op in ConfigManager().get("czynnosci_technologiczne", []):
        win.lb.insert(tk.END, op)
    win.lb.pack(fill="both", expand=True)
    ttk.Button(win, text="Zapisz", command=lambda: _save_ops(win.lb)).pack()
    return win


if __name__ == "__main__":  # pragma: no cover - manual launch
    root = tk.Tk()
    ensure_theme_applied(root)
    root.title("Magazyn i BOM")
    MagazynBOM(root).pack(fill="both", expand=True)
    root.mainloop()
