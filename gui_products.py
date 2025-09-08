# Wersja pliku: 1.0.0
# Moduł: gui_products
# ⏹ KONIEC WSTĘPU

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import logika_magazyn as LM

from ui_theme import apply_theme_safe as apply_theme

_VALID_ID_RE = re.compile(r"^[A-Z0-9_-]+$")


class ProductsMaterialsTab(ttk.Frame):
    """Zakładka zarządzania produktami, półproduktami i surowcami."""

    def __init__(self, parent: tk.Misc, base_dir: str | os.PathLike[str]) -> None:
        super().__init__(parent)
        self.base_dir = os.fspath(base_dir)
        self.paths = {
            "produkty_dir": os.path.join(self.base_dir, "data", "produkty"),
            "polprodukty": os.path.join(self.base_dir, "data", "polprodukty.json"),
            "magazyn": os.path.join(
                self.base_dir, "data", "magazyn", "magazyn.json"
            ),
            "backup": os.path.join(self.base_dir, "backup"),
        }
        print("[WM-DBG] [SETTINGS] init ProductsMaterialsTab")
        print(f"[WM-DBG] paths: {self.paths}")
        self._ensure_dirs()
        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------
    def _ensure_dirs(self) -> None:
        os.makedirs(self.paths["produkty_dir"], exist_ok=True)
        os.makedirs(self.paths["backup"], exist_ok=True)
        os.makedirs(os.path.join(self.paths["backup"], "produkty"), exist_ok=True)
        os.makedirs(os.path.join(self.paths["backup"], "polprodukty"), exist_ok=True)
        os.makedirs(os.path.join(self.paths["backup"], "magazyn"), exist_ok=True)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # Produkty ------------------------------------------------------
        prod_frame = ttk.Frame(nb)
        nb.add(prod_frame, text="Produkty")
        cols = ("symbol", "nazwa", "polprodukty", "czynnosci")
        self.products_tree = ttk.Treeview(prod_frame, columns=cols, show="headings")
        for col in cols:
            self.products_tree.heading(col, text=col.capitalize())
        self.products_tree.pack(fill="both", expand=True, padx=5, pady=5)
        prod_btns = ttk.Frame(prod_frame)
        prod_btns.pack(fill="x", padx=5, pady=5)
        ttk.Button(prod_btns, text="Dodaj", command=self.add_product).pack(
            side="left", padx=2
        )
        ttk.Button(prod_btns, text="Edytuj", command=self.edit_product).pack(
            side="left", padx=2
        )
        ttk.Button(prod_btns, text="Usuń", command=self.delete_product).pack(
            side="left", padx=2
        )
        ttk.Button(prod_btns, text="Odśwież", command=self.refresh_all).pack(
            side="left", padx=2
        )

        # Półprodukty ---------------------------------------------------
        pol_frame = ttk.Frame(nb)
        nb.add(pol_frame, text="Półprodukty")
        pcols = ("id", "nazwa", "rodzaj", "surowce", "czynnosci")
        self.pol_tree = ttk.Treeview(pol_frame, columns=pcols, show="headings")
        headers = ["ID", "Nazwa", "Rodzaj", "Surowce (#)", "Czynności (#)"]
        for col, head in zip(pcols, headers):
            self.pol_tree.heading(col, text=head)
        self.pol_tree.pack(fill="both", expand=True, padx=5, pady=5)
        pol_btns = ttk.Frame(pol_frame)
        pol_btns.pack(fill="x", padx=5, pady=5)
        ttk.Button(pol_btns, text="Dodaj", command=self.add_polprodukt).pack(
            side="left", padx=2
        )
        ttk.Button(pol_btns, text="Edytuj", command=self.edit_polprodukt).pack(
            side="left", padx=2
        )
        ttk.Button(pol_btns, text="Usuń", command=self.delete_polprodukt).pack(
            side="left", padx=2
        )
        ttk.Button(pol_btns, text="Odśwież", command=self.refresh_all).pack(
            side="left", padx=2
        )

        # Surowce -------------------------------------------------------
        mat_frame = ttk.Frame(nb)
        nb.add(mat_frame, text="Surowce")
        headers = {
            "id": "ID",
            "typ": "Typ",
            "rozmiar": "Rozmiar",
            "dlugosc": "Długość",
            "jednostka": "Jednostka",
            "stan": "Stan",
        }
        self.mat_tree = ttk.Treeview(
            mat_frame, columns=tuple(headers.keys()), show="headings"
        )
        for col, hdr in headers.items():
            self.mat_tree.heading(col, text=hdr)
        self.mat_tree.pack(fill="both", expand=True, padx=5, pady=5)
        mat_btns = ttk.Frame(mat_frame)
        mat_btns.pack(fill="x", padx=5, pady=5)
        ttk.Button(mat_btns, text="Dodaj", command=self.add_surowiec).pack(
            side="left", padx=2
        )
        ttk.Button(mat_btns, text="Edytuj", command=self.edit_surowiec).pack(
            side="left", padx=2
        )
        ttk.Button(mat_btns, text="Usuń", command=self.delete_surowiec).pack(
            side="left", padx=2
        )
        ttk.Button(mat_btns, text="Odśwież", command=self.refresh_all).pack(
            side="left", padx=2
        )

    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        self._refresh_products()
        self._refresh_polprodukty()
        self._refresh_surowce()

    # ------------------------------------------------------------------
    def _load_products_from_dir(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for fname in sorted(os.listdir(self.paths["produkty_dir"])):
            if not fname.lower().endswith(".json"):
                continue
            path = os.path.join(self.paths["produkty_dir"], fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    data["_path"] = path
                    items.append(data)
            except Exception:
                print(f"[WM-DBG] [ERROR] failed to read {path}")
        return items

    def _refresh_products(self) -> None:
        for iid in self.products_tree.get_children():
            self.products_tree.delete(iid)
        self.products = self._load_products_from_dir()
        for prod in self.products:
            sym = prod.get("symbol")
            name = prod.get("nazwa", sym)
            pc = len(prod.get("polprodukty", []))
            cc = len(prod.get("czynnosci", []))
            self.products_tree.insert(
                "",
                "end",
                iid=sym,
                values=(sym, name, pc, cc),
            )

    def _read_json_list(self, path: str) -> list[dict[str, Any]]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f) or []
        except Exception:
            print(f"[WM-DBG] [ERROR] read list {path}")
            return []

    def _write_json_list(self, path: str, data: list[dict[str, Any]], category: str) -> None:
        self._backup(path, category)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[WM-DBG] [IO] saved {path}")

    def _refresh_polprodukty(self) -> None:
        for iid in self.pol_tree.get_children():
            self.pol_tree.delete(iid)
        self.polprodukty = self._read_json_list(self.paths["polprodukty"])
        for pp in self.polprodukty:
            pid = pp.get("id")
            name = pp.get("nazwa", pid)
            rodzaj = pp.get("rodzaj", "")
            sc = len(pp.get("surowce", []))
            cc = len(pp.get("czynnosci", []))
            self.pol_tree.insert(
                "",
                "end",
                iid=pid,
                values=(pid, name, rodzaj, sc, cc),
            )

    def _refresh_surowce(self) -> None:
        self.mat_tree.delete(*self.mat_tree.get_children())
        items: dict[str, dict[str, Any]] = {}
        try:
            data = LM.load_magazyn()
            items = data.get("items", {})
        except Exception:
            try:
                with open(self.paths["magazyn"], encoding="utf-8") as f:
                    data = json.load(f) or {}
                    items = data.get("items", {})
            except Exception:
                print("[WM-DBG] [ERROR] nie można wczytać magazynu")
                messagebox.showwarning(
                    "Magazyn", "Nie można wczytać danych magazynu", parent=self
                )
                return
        if not isinstance(items, dict) or not items:
            print("[WM-DBG] [WARN] magazyn brak danych lub nieprawidłowy")
            messagebox.showinfo(
                "Magazyn", "Plik magazynu nie zawiera danych", parent=self
            )
            return
        for it in items.values():
            iid = it.get("id")
            self.mat_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    iid,
                    it.get("typ"),
                    it.get("rozmiar"),
                    it.get("dlugosc"),
                    it.get("jednostka"),
                    it.get("stan"),
                ),
            )

    # ------------------------------------------------------------------
    def _backup(self, src: str, category: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bdir = os.path.join(self.paths["backup"], category, ts)
        os.makedirs(bdir, exist_ok=True)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(bdir, os.path.basename(src)))

    # ------------------------------------------------------------------
    def _is_symbol_unique(self, symbol: str) -> bool:
        return all(p.get("symbol") != symbol for p in self.products)

    def _is_id_unique(self, list_data: list[dict[str, Any]], id_: str) -> bool:
        return all(it.get("id") != id_ for it in list_data)

    def _is_surowiec_used(self, surowiec_id: str) -> bool:
        for pp in self.polprodukty:
            if surowiec_id in pp.get("surowce", []):
                return True
        return False

    def _is_polprodukt_used(self, pol_id: str) -> bool:
        for prod in self.products:
            if pol_id in prod.get("polprodukty", []):
                return True
        return False

    # ----------------------------- Produkty CRUD ----------------------
    def add_product(self) -> None:
        print("[WM-DBG] [PROD] Dodaj produkt")
        self._product_form()

    def edit_product(self) -> None:
        sel = self.products_tree.selection()
        if not sel:
            return
        symbol = sel[0]
        print(f"[WM-DBG] [PROD] Edytuj produkt: {symbol}")
        prod = next((p for p in self.products if p.get("symbol") == symbol), None)
        if prod:
            self._product_form(prod)

    def delete_product(self) -> None:
        sel = self.products_tree.selection()
        if not sel:
            return
        symbol = sel[0]
        path = os.path.join(self.paths["produkty_dir"], f"{symbol}.json")
        if not messagebox.askyesno("Potwierdź", f"Czy na pewno usunąć {symbol}?", parent=self):
            return
        if not messagebox.askyesno(
            "Potwierdź", "To druga prośba o potwierdzenie. Usunąć?", parent=self
        ):
            return
        try:
            self._backup(path, "produkty")
            os.remove(path)
            print(f"[WM-DBG] [PROD] Usunięto produkt: {symbol}")
        except OSError:
            print(f"[WM-DBG] [ERROR] nie można usunąć produktu: {symbol}")
        self.refresh_all()

    def _product_form(self, product: dict[str, Any] | None = None) -> None:
        win = tk.Toplevel(self)
        win.title("Produkt")
        apply_theme(win)
        win.grab_set()

        tk.Label(win, text="Symbol:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        sym_var = tk.StringVar(value=product.get("symbol", "") if product else "")
        sym_entry = ttk.Entry(win, textvariable=sym_var)
        sym_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        tk.Label(win, text="Nazwa:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        name_var = tk.StringVar(value=product.get("nazwa", "") if product else "")
        ttk.Entry(win, textvariable=name_var).grid(
            row=1, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Półprodukty:").grid(
            row=2, column=0, sticky="nw", padx=5, pady=2
        )
        list_pol = tk.Listbox(win, selectmode="multiple", exportselection=False, height=6)
        pol_ids = [p.get("id") for p in self.polprodukty]
        for pid in pol_ids:
            list_pol.insert("end", pid)
        if product:
            for pid in product.get("polprodukty", []):
                if pid in pol_ids:
                    idx = pol_ids.index(pid)
                    list_pol.selection_set(idx)
        list_pol.grid(row=2, column=1, padx=5, pady=2, sticky="nsew")

        tk.Label(win, text="Czynności:").grid(
            row=3, column=0, sticky="nw", padx=5, pady=2
        )
        czyn_list = tk.Listbox(win, height=6)
        if product:
            for c in product.get("czynnosci", []):
                czyn_list.insert("end", c)
        czyn_list.grid(row=3, column=1, padx=5, pady=2, sticky="nsew")

        add_entry = ttk.Entry(win)
        add_entry.grid(row=4, column=1, padx=5, pady=2, sticky="ew")

        def add_czyn() -> None:
            txt = add_entry.get().strip()
            if txt:
                czyn_list.insert("end", txt)
                add_entry.delete(0, "end")

        def del_czyn() -> None:
            for i in reversed(czyn_list.curselection()):
                czyn_list.delete(i)

        btns = ttk.Frame(win)
        btns.grid(row=5, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(btns, text="Dodaj pozycję", command=add_czyn).pack(side="left")
        ttk.Button(btns, text="Usuń pozycję", command=del_czyn).pack(
            side="left", padx=5
        )

        def save() -> None:
            symbol = sym_var.get().strip().upper()
            name = name_var.get().strip()
            if not symbol or not name:
                messagebox.showerror("Błąd", "Wymagany symbol i nazwa", parent=win)
                print("[WM-DBG] [ERROR] brak symbolu/nazwy")
                return
            if not _VALID_ID_RE.match(symbol):
                messagebox.showerror("Błąd", "Nieprawidłowy symbol", parent=win)
                print("[WM-DBG] [ERROR] invalid symbol")
                return
            if (not product or product.get("symbol") != symbol) and not self._is_symbol_unique(
                symbol
            ):
                messagebox.showerror("Błąd", "Duplikat symbolu", parent=win)
                print("[WM-DBG] [ERROR] duplicate symbol")
                return
            selected_pol = [pol_ids[i] for i in list_pol.curselection()]
            czyn = [czyn_list.get(i) for i in range(czyn_list.size())]
            data = {
                "symbol": symbol,
                "nazwa": name,
                "polprodukty": selected_pol,
                "czynnosci": czyn,
            }
            path = os.path.join(self.paths["produkty_dir"], f"{symbol}.json")
            self._backup(path, "produkty")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if product:
                print(f"[WM-DBG] [PROD] Aktualizacja produktu: {symbol}")
            else:
                print(f"[WM-DBG] [PROD] Dodano produkt: {symbol}")
            win.destroy()
            self.refresh_all()

        ttk.Button(win, text="Zapisz", command=save).grid(
            row=6, column=1, padx=5, pady=5, sticky="e"
        )

        win.columnconfigure(1, weight=1)

    # ------------------------- Półprodukty CRUD ----------------------
    def add_polprodukt(self) -> None:
        print("[WM-DBG] [POL] Dodaj półprodukt")
        self._polprodukt_form()

    def edit_polprodukt(self) -> None:
        sel = self.pol_tree.selection()
        if not sel:
            return
        pid = sel[0]
        print(f"[WM-DBG] [POL] Edytuj półprodukt: {pid}")
        item = next((p for p in self.polprodukty if p.get("id") == pid), None)
        if item:
            self._polprodukt_form(item)

    def delete_polprodukt(self) -> None:
        sel = self.pol_tree.selection()
        if not sel:
            return
        pid = sel[0]
        if self._is_polprodukt_used(pid):
            messagebox.showerror(
                "Błąd", "Półprodukt użyty w produkcie – usuń najpierw produkt", parent=self
            )
            print(f"[WM-DBG] [POL] blokada usunięcia: {pid}")
            return
        if not messagebox.askyesno("Potwierdź", f"Czy na pewno usunąć {pid}?", parent=self):
            return
        if not messagebox.askyesno(
            "Potwierdź", "To druga prośba o potwierdzenie. Usunąć?", parent=self
        ):
            return
        self.polprodukty = [p for p in self.polprodukty if p.get("id") != pid]
        self._write_json_list(self.paths["polprodukty"], self.polprodukty, "polprodukty")
        print(f"[WM-DBG] [POL] Usunięto półprodukt: {pid}")
        self.refresh_all()

    def _polprodukt_form(self, item: dict[str, Any] | None = None) -> None:
        win = tk.Toplevel(self)
        win.title("Półprodukt")
        apply_theme(win)
        win.grab_set()

        tk.Label(win, text="ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        id_var = tk.StringVar(value=item.get("id", "") if item else "")
        ttk.Entry(win, textvariable=id_var).grid(
            row=0, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Nazwa:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        name_var = tk.StringVar(value=item.get("nazwa", "") if item else "")
        ttk.Entry(win, textvariable=name_var).grid(
            row=1, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Rodzaj:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        rodz_var = tk.StringVar(value=item.get("rodzaj", "") if item else "")
        rodz_cb = ttk.Combobox(
            win,
            textvariable=rodz_var,
            values=["Rura", "Profil", "Pręt", "Inne"],
            state="readonly",
        )
        rodz_cb.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        tk.Label(win, text="Surowce:").grid(
            row=3, column=0, sticky="nw", padx=5, pady=2
        )
        list_mat = tk.Listbox(win, selectmode="multiple", exportselection=False, height=6)
        mat_ids = [m.get("id") for m in self.surowce]
        for mid in mat_ids:
            list_mat.insert("end", mid)
        if item:
            for mid in item.get("surowce", []):
                if mid in mat_ids:
                    list_mat.selection_set(mat_ids.index(mid))
        list_mat.grid(row=3, column=1, padx=5, pady=2, sticky="nsew")

        tk.Label(win, text="Czynności:").grid(
            row=4, column=0, sticky="nw", padx=5, pady=2
        )
        czyn_list = tk.Listbox(win, height=6)
        if item:
            for c in item.get("czynnosci", []):
                czyn_list.insert("end", c)
        czyn_list.grid(row=4, column=1, padx=5, pady=2, sticky="nsew")

        add_entry = ttk.Entry(win)
        add_entry.grid(row=5, column=1, padx=5, pady=2, sticky="ew")

        def add_czyn() -> None:
            txt = add_entry.get().strip()
            if txt:
                czyn_list.insert("end", txt)
                add_entry.delete(0, "end")

        def del_czyn() -> None:
            for i in reversed(czyn_list.curselection()):
                czyn_list.delete(i)

        btns = ttk.Frame(win)
        btns.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(btns, text="Dodaj pozycję", command=add_czyn).pack(side="left")
        ttk.Button(btns, text="Usuń pozycję", command=del_czyn).pack(
            side="left", padx=5
        )

        def save() -> None:
            pid = id_var.get().strip().upper()
            name = name_var.get().strip()
            rodz = rodz_var.get().strip()
            if not pid or not name or not rodz:
                messagebox.showerror("Błąd", "Wszystkie pola wymagane", parent=win)
                print("[WM-DBG] [ERROR] brak danych półproduktu")
                return
            if not _VALID_ID_RE.match(pid):
                messagebox.showerror("Błąd", "Nieprawidłowy ID", parent=win)
                print("[WM-DBG] [ERROR] invalid id")
                return
            if (not item or item.get("id") != pid) and not self._is_id_unique(
                self.polprodukty, pid
            ):
                messagebox.showerror("Błąd", "Duplikat ID", parent=win)
                print("[WM-DBG] [ERROR] duplicate id")
                return
            selected_mat = [mat_ids[i] for i in list_mat.curselection()]
            czyn = [czyn_list.get(i) for i in range(czyn_list.size())]
            data = {
                "id": pid,
                "nazwa": name,
                "rodzaj": rodz,
                "surowce": selected_mat,
                "czynnosci": czyn,
            }
            if item:
                idx = next((i for i, d in enumerate(self.polprodukty) if d.get("id") == pid), None)
                if idx is not None:
                    self.polprodukty[idx] = data
            else:
                self.polprodukty.append(data)
            self._write_json_list(
                self.paths["polprodukty"], self.polprodukty, "polprodukty"
            )
            if item:
                print(f"[WM-DBG] [POL] Aktualizacja półproduktu: {pid}")
            else:
                print(f"[WM-DBG] [POL] Dodano półprodukt: {pid}")
            win.destroy()
            self.refresh_all()

        ttk.Button(win, text="Zapisz", command=save).grid(
            row=7, column=1, padx=5, pady=5, sticky="e"
        )

        win.columnconfigure(1, weight=1)

    # ----------------------------- Surowce CRUD ----------------------
    def add_surowiec(self) -> None:
        print("[WM-DBG] [MAT] Dodaj surowiec")
        self._surowiec_form()

    def edit_surowiec(self) -> None:
        sel = self.mat_tree.selection()
        if not sel:
            return
        sid = sel[0]
        print(f"[WM-DBG] [MAT] Edytuj surowiec: {sid}")
        item = next((m for m in self.surowce if m.get("id") == sid), None)
        if item:
            self._surowiec_form(item)

    def delete_surowiec(self) -> None:
        sel = self.mat_tree.selection()
        if not sel:
            return
        sid = sel[0]
        if self._is_surowiec_used(sid):
            messagebox.showerror(
                "Błąd", "Surowiec użyty w półprodukcie", parent=self
            )
            print(f"[WM-DBG] [MAT] blokada usunięcia: {sid}")
            return
        if not messagebox.askyesno("Potwierdź", f"Czy na pewno usunąć {sid}?", parent=self):
            return
        if not messagebox.askyesno(
            "Potwierdź", "To druga prośba o potwierdzenie. Usunąć?", parent=self
        ):
            return
        self.surowce = [m for m in self.surowce if m.get("id") != sid]
        self._write_json_list(self.paths["magazyn"], self.surowce, "magazyn")
        print(f"[WM-DBG] [MAT] Usunięto surowiec: {sid}")
        self.refresh_all()

    def _surowiec_form(self, item: dict[str, Any] | None = None) -> None:
        win = tk.Toplevel(self)
        win.title("Surowiec")
        apply_theme(win)
        win.grab_set()

        tk.Label(win, text="ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        id_var = tk.StringVar(value=item.get("id", "") if item else "")
        ttk.Entry(win, textvariable=id_var).grid(
            row=0, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Typ:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        typ_var = tk.StringVar(value=item.get("typ", "") if item else "")
        ttk.Combobox(
            win,
            textvariable=typ_var,
            values=["Rura", "Profil", "Pręt", "Inne"],
            state="readonly",
        ).grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        tk.Label(win, text="Rozmiar:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        roz_var = tk.StringVar(value=item.get("rozmiar", "") if item else "")
        ttk.Entry(win, textvariable=roz_var).grid(
            row=2, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Długość:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        dl_var = tk.StringVar(value=str(item.get("dlugosc", "")) if item else "")
        ttk.Entry(win, textvariable=dl_var).grid(
            row=3, column=1, padx=5, pady=2, sticky="ew"
        )

        tk.Label(win, text="Jednostka:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        jed_var = tk.StringVar(value=item.get("jednostka", "") if item else "")
        ttk.Combobox(
            win,
            textvariable=jed_var,
            values=["mm", "m", "szt."],
            state="readonly",
        ).grid(row=4, column=1, padx=5, pady=2, sticky="ew")

        tk.Label(win, text="Stan:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        stan_var = tk.StringVar(value=str(item.get("stan", "")) if item else "")
        ttk.Entry(win, textvariable=stan_var).grid(
            row=5, column=1, padx=5, pady=2, sticky="ew"
        )

        def save() -> None:
            sid = id_var.get().strip().upper()
            if not sid:
                messagebox.showerror("Błąd", "ID wymagane", parent=win)
                print("[WM-DBG] [ERROR] brak ID surowca")
                return
            if not _VALID_ID_RE.match(sid):
                messagebox.showerror("Błąd", "Nieprawidłowy ID", parent=win)
                print("[WM-DBG] [ERROR] invalid ID surowca")
                return
            if (not item or item.get("id") != sid) and not self._is_id_unique(
                self.surowce, sid
            ):
                messagebox.showerror("Błąd", "Duplikat ID", parent=win)
                print("[WM-DBG] [ERROR] duplicate ID surowca")
                return
            try:
                dl_val = float(dl_var.get())
                stan_val = float(stan_var.get())
            except ValueError:
                messagebox.showerror("Błąd", "Długość i stan muszą być liczbą", parent=win)
                print("[WM-DBG] [ERROR] liczby surowca")
                return
            data = {
                "id": sid,
                "typ": typ_var.get().strip(),
                "rozmiar": roz_var.get().strip(),
                "dlugosc": dl_val,
                "jednostka": jed_var.get().strip(),
                "stan": stan_val,
            }
            if item:
                idx = next((i for i, d in enumerate(self.surowce) if d.get("id") == sid), None)
                if idx is not None:
                    self.surowce[idx] = data
            else:
                self.surowce.append(data)
            self._write_json_list(self.paths["magazyn"], self.surowce, "magazyn")
            if item:
                print(f"[WM-DBG] [MAT] Aktualizacja surowca: {sid}")
            else:
                print(f"[WM-DBG] [MAT] Dodano surowiec: {sid}")
            win.destroy()
            self.refresh_all()

        ttk.Button(win, text="Zapisz", command=save).grid(
            row=6, column=1, padx=5, pady=5, sticky="e"
        )

        win.columnconfigure(1, weight=1)


# ⏹ KONIEC KODU

