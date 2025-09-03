"""Simple GUI for managing warehouse and BOM data.

This module provides three sections (raw materials, semi-finished,
and products) each displayed in a Treeview with forms for editing.
Data is persisted in data/magazyn, data/polprodukty, data/produkty.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config_manager import ConfigManager

# Paths
DATA_DIR = Path("data")
LOG_FILE = Path("logi_magazyn.txt")


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

    @staticmethod
    def _load_dir(folder: Path) -> dict:
        out: dict[str, dict] = {}
        for pth in folder.glob("*.json"):
            data = _load_json(pth, None)
            if isinstance(data, dict):
                key = data.get("kod") or data.get("symbol") or pth.stem
                out[key] = data
        return out

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

    def register_delivery(
        self, kod: str, ilosc: float, rodzaj: str | None = None, dlugosc: float | None = None
    ) -> None:
        rec = self.surowce.get(kod)
        if not rec:
            raise ValueError(f"Surowiec '{kod}' nie istnieje.")
        rec["stan"] = int(rec.get("stan", 0)) + int(ilosc)
        if rodzaj:
            rec["rodzaj"] = rodzaj
        if dlugosc is not None:
            try:
                rec["dlugosc"] = float(dlugosc)
            except ValueError:
                pass
        self.add_or_update_surowiec(rec)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(
                f"{datetime.now().isoformat()}|{kod}|{ilosc}|{rodzaj or ''}|{dlugosc or ''}\n"
            )

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
        cols = (
            "kod",
            "nazwa",
            "rodzaj",
            "rozmiar",
            "dlugosc",
            "jednostka",
            "stan",
        )
        self.tree_sr = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_sr.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("kod", "Kod"),
            ("nazwa", "Nazwa"),
            ("rodzaj", "Rodzaj"),
            ("rozmiar", "Rozmiar"),
            ("dlugosc", "Długość"),
            ("jednostka", "Jednostka"),
            ("stan", "Stan"),
        ]
        for key, lbl in headers:
            self.tree_sr.heading(key, text=lbl)
            self.tree_sr.column(key, width=100, anchor="w")
        self.tree_sr.bind("<<TreeviewSelect>>", self._on_sr_select)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj", command=self._start_add_surowiec).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Edytuj", command=self._start_edit_surowiec).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Usuń", command=self._delete_surowiec).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Przyjmij dostawę", command=self._przyjmij_dostawe).pack(
            side="left", padx=4
        )

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.s_vars = {k: tk.StringVar() for k, _ in headers}
        for i, (key, label) in enumerate(headers[:-1]):
            ttk.Label(form, text=label).grid(
                row=i // 2, column=(i % 2) * 2, sticky="w", padx=4, pady=2
            )
            ttk.Entry(form, textvariable=self.s_vars[key]).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky="ew", padx=4, pady=2
            )
        ttk.Button(form, text="Zapisz", command=self._save_surowiec).grid(
            row=3, column=3, sticky="e", padx=4, pady=4
        )
        for c in range(4):
            form.columnconfigure(c, weight=1)

    def _on_sr_select(self, _event) -> None:
        sel = self.tree_sr.selection()
        if sel:
            values = self.tree_sr.item(sel[0], "values")
            keys = (
                "kod",
                "nazwa",
                "rodzaj",
                "rozmiar",
                "dlugosc",
                "jednostka",
                "stan",
            )
            for k, v in zip(keys, values):
                self.s_vars[k].set(v)

    def _start_add_surowiec(self) -> None:
        for var in self.s_vars.values():
            var.set("")
        self.s_vars["stan"].set("0")

    def _start_edit_surowiec(self) -> None:
        sel = self.tree_sr.selection()
        if not sel:
            messagebox.showerror("Surowce", "Wybierz pozycję do edycji.")
            return
        values = self.tree_sr.item(sel[0], "values")
        keys = (
            "kod",
            "nazwa",
            "rodzaj",
            "rozmiar",
            "dlugosc",
            "jednostka",
            "stan",
        )
        for k, v in zip(keys, values):
            self.s_vars[k].set(v)

    def _przyjmij_dostawe(self) -> None:
        sel = self.tree_sr.selection()
        if not sel:
            messagebox.showerror("Surowce", "Wybierz surowiec.")
            return
        kod = self.tree_sr.item(sel[0], "values")[0]
        try:
            ilosc = simpledialog.askstring("Dostawa", "Ilość", parent=self)
            if ilosc is None:
                return
            ilosc_val = float(ilosc)
            rodzaj = simpledialog.askstring("Dostawa", "Typ/Rodzaj", parent=self)
            dl = simpledialog.askstring("Dostawa", "Długość", parent=self)
            dl_val = float(dl) if dl else None
        except ValueError:
            messagebox.showerror("Surowce", "Nieprawidłowe dane dostawy.")
            return
        self.model.register_delivery(kod, ilosc_val, rodzaj, dl_val)
        self._load_surowce()

    def _save_surowiec(self) -> None:
        rec = {k: (v.get() or "").strip() for k, v in self.s_vars.items()}
        for field in ("kod", "nazwa", "rodzaj", "jednostka"):
            if not rec.get(field):
                messagebox.showerror("Surowce", f"Pole '{field}' jest wymagane.")
                return
        try:
            rec["dlugosc"] = float(rec.get("dlugosc") or 0)
            rec["stan"] = int(rec.get("stan") or 0)
        except ValueError:
            messagebox.showerror(
                "Surowce", "Pola liczby muszą zawierać wartości numeryczne."
            )
            return
        self.model.add_or_update_surowiec(rec)
        self._load_surowce()

    def _delete_surowiec(self) -> None:
        sel = self.tree_sr.selection()
        if sel:
            kod = self.tree_sr.item(sel[0], "values")[0]
        else:
            kod = self.s_vars["kod"].get()
        if kod and messagebox.askyesno("Potwierdź", f"Usunąć surowiec '{kod}'?"):
            self.model.delete_surowiec(kod)
            self._load_surowce()

    # --- Półprodukty ---
    def _build_polprodukty(self, parent: ttk.Frame) -> None:
        cols = ("kod", "nazwa", "sr_kod", "czynnosci", "norma_strat")
        self.tree_pp = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_pp.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("kod", "Kod"),
            ("nazwa", "Nazwa"),
            ("sr_kod", "Kod surowca"),
            ("czynnosci", "Czynności"),
            ("norma_strat", "Norma strat [%]"),
        ]
        for key, lbl in headers:
            self.tree_pp.heading(key, text=lbl)
            self.tree_pp.column(key, width=120, anchor="w")
        self.tree_pp.bind("<<TreeviewSelect>>", self._on_pp_select)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj", command=self._start_add_polprodukt).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Edytuj", command=self._start_edit_polprodukt).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Usuń", command=self._delete_polprodukt).pack(
            side="left", padx=4
        )

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        form_fields = [
            ("kod", "Kod"),
            ("nazwa", "Nazwa"),
            ("sr_kod", "Kod surowca"),
            ("sr_ilosc", "Ilość surowca na szt."),
            ("sr_jednostka", "Jednostka"),
            ("norma_strat", "Norma strat [%]"),
        ]
        self.pp_vars = {k: tk.StringVar() for k, _ in form_fields}
        self.pp_ops = ConfigManager().get("czynnosci_technologiczne", [])
        for i, (key, label) in enumerate(form_fields):
            ttk.Label(form, text=label).grid(
                row=i, column=0, sticky="w", padx=4, pady=2
            )
            tk.Entry(form, textvariable=self.pp_vars[key]).grid(
                row=i, column=1, sticky="ew", padx=4, pady=2
            )
        ttk.Label(form, text="Czynności").grid(
            row=len(form_fields), column=0, sticky="w", padx=4, pady=2
        )
        self.pp_lb = tk.Listbox(form, selectmode="multiple", exportselection=False)
        for op in self.pp_ops:
            self.pp_lb.insert(tk.END, op)
        self.pp_lb.grid(row=len(form_fields), column=1, sticky="ew", padx=4, pady=2)
        tk.Button(form, text="Zapisz", command=self._save_polprodukt).grid(
            row=len(form_fields) + 1, column=1, sticky="e", padx=4, pady=4
        )
        form.columnconfigure(1, weight=1)

    def _on_pp_select(self, _event) -> None:
        sel = self.tree_pp.selection()
        if not sel:
            return
        kod = self.tree_pp.item(sel[0], "values")[0]
        rec = self.model.polprodukty.get(kod, {})
        self.pp_vars["kod"].set(rec.get("kod", ""))
        self.pp_vars["nazwa"].set(rec.get("nazwa", ""))
        surowiec = rec.get("surowiec", {})
        self.pp_vars["sr_kod"].set(surowiec.get("kod", ""))
        self.pp_vars["sr_ilosc"].set(str(surowiec.get("ilosc_na_szt", "")))
        self.pp_vars["sr_jednostka"].set(surowiec.get("jednostka", ""))
        self.pp_vars["norma_strat"].set(str(rec.get("norma_strat_procent", 0)))
        self.pp_lb.selection_clear(0, tk.END)
        for idx, op in enumerate(self.pp_ops):
            if op in rec.get("czynnosci", []):
                self.pp_lb.selection_set(idx)

    def _start_add_polprodukt(self) -> None:
        for var in self.pp_vars.values():
            var.set("")
        self.pp_lb.selection_clear(0, tk.END)

    def _start_edit_polprodukt(self) -> None:
        sel = self.tree_pp.selection()
        if not sel:
            messagebox.showerror("Półprodukty", "Wybierz pozycję do edycji.")
            return
        self._on_pp_select(None)

    def _save_polprodukt(self) -> None:
        kod = self.pp_vars["kod"].get().strip()
        nazwa = self.pp_vars["nazwa"].get().strip()
        sr_kod = self.pp_vars["sr_kod"].get().strip()
        sr_ilosc = self.pp_vars["sr_ilosc"].get().strip()
        sr_jedn = self.pp_vars["sr_jednostka"].get().strip()
        if not (kod and nazwa and sr_kod and sr_ilosc and sr_jedn):
            messagebox.showerror(
                "Półprodukty",
                "Wymagane pola: kod, nazwa, kod surowca, ilość i jednostka.",
            )
            return
        try:
            sr_ilosc_val = float(sr_ilosc)
        except ValueError:
            messagebox.showerror(
                "Półprodukty", "Ilość surowca musi być liczbą.")
            return
        try:
            norma = int(self.pp_vars["norma_strat"].get() or 0)
        except ValueError:
            messagebox.showerror("Półprodukty", "Norma strat musi być liczbą.")
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
        sel = self.tree_pp.selection()
        kod = self.tree_pp.item(sel[0], "values")[0] if sel else ""
        if kod and messagebox.askyesno("Potwierdź", f"Usunąć półprodukt '{kod}'?"):
            self.model.delete_polprodukt(kod)
            self._load_polprodukty()

    # --- Produkty ---
    def _build_produkty(self, parent: ttk.Frame) -> None:
        cols = ("symbol", "nazwa", "bom")
        self.tree_pr = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree_pr.pack(fill="both", expand=True, padx=6, pady=4)
        headers = [
            ("symbol", "Symbol"),
            ("nazwa", "Nazwa"),
            ("bom", "BOM"),
        ]
        for key, lbl in headers:
            self.tree_pr.heading(key, text=lbl)
            self.tree_pr.column(key, width=140, anchor="w")
        self.tree_pr.bind("<<TreeviewSelect>>", self._on_pr_select)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj", command=self._start_add_produkt).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Edytuj", command=self._start_edit_produkt).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Usuń", command=self._delete_produkt).pack(
            side="left", padx=4
        )

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.pr_vars = {k: tk.StringVar() for k, _ in headers}
        ttk.Label(form, text="Symbol").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(form, textvariable=self.pr_vars["symbol"]).grid(
            row=0, column=1, sticky="ew", padx=4, pady=2
        )
        ttk.Label(form, text="Nazwa").grid(
            row=1, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(form, textvariable=self.pr_vars["nazwa"]).grid(
            row=1, column=1, sticky="ew", padx=4, pady=2
        )
        ttk.Label(
            form,
            text="BOM (pozycje rozdzielone pionową kreską '|',\nnp.: typ=polprodukt;kod=DRUT;ilosc=2)"
        ).grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["bom"]).grid(
            row=2, column=1, sticky="ew", padx=4, pady=2
        )
        ttk.Button(form, text="Zapisz", command=self._save_produkt).grid(
            row=3, column=1, sticky="e", padx=4, pady=4
        )
        form.columnconfigure(1, weight=1)

    def _on_pr_select(self, _event) -> None:
        sel = self.tree_pr.selection()
        if not sel:
            return
        symbol = self.tree_pr.item(sel[0], "values")[0]
        rec = self.model.produkty.get(symbol, {})
        self.pr_vars["symbol"].set(rec.get("symbol", ""))
        self.pr_vars["nazwa"].set(rec.get("nazwa", ""))
        bom_txt = " | ".join(
            ";".join(
                f"{k}={i.get(k)}" for k in ("typ", "kod", "ilosc_na_sztuke")
            )
            for i in rec.get("BOM", [])
        )
        self.pr_vars["bom"].set(bom_txt)

    def _start_add_produkt(self) -> None:
        for var in self.pr_vars.values():
            var.set("")

    def _start_edit_produkt(self) -> None:
        sel = self.tree_pr.selection()
        if not sel:
            messagebox.showerror("Produkty", "Wybierz pozycję do edycji.")
            return
        self._on_pr_select(None)

    def _save_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        nazwa = self.pr_vars["nazwa"].get().strip()
        if not symbol or not nazwa:
            messagebox.showerror("Produkty", "Wymagane pola: symbol i nazwa.")
            return
        bom_list = self._parse_bom(self.pr_vars["bom"].get())
        if not bom_list:
            messagebox.showerror("Produkty", "BOM musi mieć co najmniej jedną pozycję.")
            return
        rec = {"symbol": symbol, "nazwa": nazwa, "BOM": bom_list}
        self.model.add_or_update_produkt(rec)
        self._load_produkty()

    def _delete_produkt(self) -> None:
        sel = self.tree_pr.selection()
        symbol = self.tree_pr.item(sel[0], "values")[0] if sel else ""
        if symbol and messagebox.askyesno("Potwierdź", f"Usunąć produkt '{symbol}'?"):
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
                ", ".join(rec.get("czynnosci", [])),
                rec.get("norma_strat_procent", 0),
            )
            self.tree_pp.insert("", "end", values=row)

    def _load_produkty(self) -> None:
        for i in self.tree_pr.get_children():
            self.tree_pr.delete(i)
        for symbol, rec in sorted(self.model.produkty.items()):
            bom_count = len(rec.get("BOM", []))
            self.tree_pr.insert(
                "", "end", values=(symbol, rec.get("nazwa", ""), bom_count)
            )


def make_window(root: tk.Misc) -> ttk.Frame:
    """Return frame with Magazyn/BOM management."""
    return MagazynBOM(root)


if __name__ == "__main__":  # pragma: no cover - manual launch
    root = tk.Tk()
    root.title("Magazyn i BOM")
    MagazynBOM(root).pack(fill="both", expand=True)
    root.mainloop()
