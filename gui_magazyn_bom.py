# version: 1.1
"""GUI zarządzania surowcami, półproduktami i produktami/BOM.

Wersja 1.1 spina wybór surowca półproduktu z istniejącą kartoteką Magazynu,
przechowuje stabilne ID oraz korzysta ze wspólnego systemu pomocy „!”.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from ui_theme import ensure_theme_applied
from ui_context_help import SearchableCombobox, add_help_button
from config.paths import get_path
from config_manager import ConfigManager
from ui_utils import _msg_error
from wm_log import dbg as wm_dbg, err as wm_err

try:
    import logika_magazyn as LM
except Exception:  # pragma: no cover - tryb autonomiczny
    LM = None


DATA_DIR = Path("data")

HELP = {
    "raw_id": (
        "Unikalny numer surowca używany do powiązań w WM. "
        "Jeżeli pole jest puste przy tworzeniu, program nada następne ID automatycznie."
    ),
    "raw_name": "Wpisz czytelną nazwę surowca. Powiązania półproduktów opierają się na ID, więc nazwę można później poprawić.",
    "raw_type": "Określ rodzaj materiału, np. profil, pręt, rura albo blacha. Pole służy do porządkowania i filtrowania surowców.",
    "raw_size": "Podaj rozmiar lub przekrój, np. fi8 albo 30×30×2. Rozmiar jest także używany w podpowiedziach przy wyborze surowca.",
    "raw_length": "Podaj długość jednostkową materiału, jeżeli ma zastosowanie. Wartość jest zapisywana jako liczba.",
    "unit": "Wybierz jednostkę zgodną ze sposobem prowadzenia stanu magazynowego. Ta sama jednostka powinna być używana przy zużyciu półproduktu.",
    "stock": "Aktualny stan surowca w magazynie. Ruchy magazynowe w głównym Magazynie powinny być wykonywane przez PZ/RW, aby zachować historię.",
    "alert": "Próg określa poziom ostrzegawczy dla zapasu. Pomaga wykrywać materiały wymagające uzupełnienia.",
    "semi_code": "Kod identyfikuje półprodukt w BOM, np. OS-01. Powinien być unikalny dla danego półproduktu.",
    "semi_name": "Nazwa opisuje półprodukt w sposób czytelny dla użytkownika. Kod pozostaje jego identyfikatorem w składzie produktu.",
    "raw_select": (
        "Wybierz materiał, z którego wykonywany jest półprodukt. "
        "Lista pochodzi z Magazynu i można ją przeszukiwać po ID, nazwie oraz rozmiarze."
    ),
    "raw_qty": "Podaj ilość materiału potrzebną do wykonania jednej sztuki półproduktu. Wartość może być używana do obliczania zapotrzebowania.",
    "ops": "Wybierz operacje potrzebne do wykonania półproduktu, np. cięcie, wiercenie lub szlifowanie. Lista czynności pochodzi z konfiguracji WM.",
    "loss": "Określa procent materiału doliczany jako przewidywana strata produkcyjna. Np. 5% zwiększa zapotrzebowanie ze 100 do 105 jednostek.",
    "product_code": "To stały numer lub symbol produktu, np. ST-01. Nie jest tym samym co nazwa produktu.",
    "product_name": "Nazwa produktu jest opisem czytelnym dla użytkownika. Oznaczenie pozostaje stabilnym symbolem produktu.",
    "bom": "BOM określa, z jakich pozycji i w jakiej ilości składa się produkt. Każda pozycja powinna wskazywać istniejący kod półproduktu lub materiału.",
    "save": "Zapisuje wprowadzone dane i powiązania. Przed zapisem WM sprawdza wymagane pola i poprawność danych.",
    "delete": "Usuwa wybraną definicję po potwierdzeniu. Użyj tej opcji tylko wtedy, gdy pozycja nie jest już potrzebna w BOM.",
}


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
    except Exception as exc:  # pragma: no cover - logowanie błędów
        wm_err("gui.bom", "bom load failed", exc, path=path)
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
    ops = list(lb.get(0, tk.END))
    path = DATA_DIR / "czynnosci.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ops, fh, ensure_ascii=False, indent=2)
    messagebox.showinfo("Czynności", "Zapisano czynności technologiczne.")


def _next_code(existing, prefix: str) -> str:
    rx = re.compile(rf"^{re.escape(prefix)}[-_]?(\d+)$", re.IGNORECASE)
    maximum = 0
    used = {str(value).strip().casefold() for value in existing}
    for value in existing:
        match = rx.match(str(value).strip())
        if match:
            maximum = max(maximum, int(match.group(1)))
    number = maximum + 1
    while True:
        candidate = f"{prefix}-{number:03d}"
        if candidate.casefold() not in used:
            return candidate
        number += 1


class WarehouseModel:
    """Dane surowców, półproduktów i produktów używane przez edytor BOM."""

    def __init__(self):
        self.data_dir = DATA_DIR
        self.src_file = self.data_dir / "magazyn" / "surowce.json"
        self.pol_dir = self.data_dir / "polprodukty"
        self.prd_dir = self.data_dir / "produkty"
        for path in (self.src_file.parent, self.pol_dir, self.prd_dir):
            path.mkdir(parents=True, exist_ok=True)

        data = _load_json(self.src_file, [])
        if isinstance(data, list):
            self.surowce = {
                str(rec.get("kod") or rec.get("id")): rec
                for rec in data
                if isinstance(rec, dict) and (rec.get("kod") or rec.get("id"))
            }
        elif isinstance(data, dict):
            self.surowce = {str(k): v for k, v in data.items() if isinstance(v, dict)}
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
                out[str(key)] = data
        return out

    def _load_bom_file(self) -> None:
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

    def _normalise_bom_payload(self, payload, source: Path) -> list[dict]:
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
            records.append(
                {
                    "symbol": symbol,
                    "nazwa": raw.get("nazwa") or raw.get("name") or symbol,
                    "polprodukty": self._normalise_polprodukty(raw.get("polprodukty")),
                    "czynnosci": list(raw.get("czynnosci") or raw.get("operations") or []),
                    "_path": str(source),
                }
            )
        return records

    @staticmethod
    def _normalise_polprodukty(data) -> list[dict]:
        def _coerce_qty(raw):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return raw

        if isinstance(data, dict):
            return [
                {"kod": kod, "ilosc_na_szt": _coerce_qty(value)}
                for kod, value in data.items()
            ]
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

    def inventory_raw_materials(self) -> dict[str, dict]:
        """Zwraca surowce widoczne w Magazynie, z kluczem będącym stabilnym ID."""
        out: dict[str, dict] = {}
        for key, rec in self.surowce.items():
            if not isinstance(rec, dict):
                continue
            item_id = str(rec.get("id") or rec.get("kod") or key).strip()
            if not item_id:
                continue
            copy = dict(rec)
            copy.setdefault("id", item_id)
            copy.setdefault("kod", item_id)
            out[item_id] = copy

        if LM is not None and hasattr(LM, "load_magazyn"):
            try:
                payload = LM.load_magazyn(include_external=True)
                items = payload.get("items") or payload.get("pozycje") or {}
            except Exception:
                items = {}
            if isinstance(items, dict):
                for key, rec in items.items():
                    if not isinstance(rec, dict):
                        continue
                    raw_type = str(rec.get("typ") or rec.get("type") or "").strip().casefold()
                    section = str(rec.get("sekcja") or rec.get("section") or "").strip().casefold()
                    is_raw = raw_type in {"surowiec", "surowce", "materiał", "material", "materiał"} or section == "surowce"
                    if not is_raw:
                        continue
                    item_id = str(rec.get("id") or rec.get("kod") or key).strip()
                    if not item_id:
                        continue
                    copy = dict(rec)
                    copy.setdefault("id", item_id)
                    copy.setdefault("kod", item_id)
                    out[item_id] = {**out.get(item_id, {}), **copy}
        return out

    def add_or_update_surowiec(self, record: dict) -> None:
        kod = record.get("kod") or record.get("id")
        if not kod:
            raise ValueError("ID surowca jest wymagane.")
        record = dict(record)
        record["kod"] = str(kod)
        record.setdefault("id", str(kod))
        self.surowce[str(kod)] = record
        _save_json(self.src_file, list(self.surowce.values()))

    def delete_surowiec(self, kod: str) -> None:
        if kod in self.surowce:
            del self.surowce[kod]
            _save_json(self.src_file, list(self.surowce.values()))

    def add_or_update_polprodukt(self, record: dict) -> None:
        kod = record.get("kod")
        if not kod:
            raise ValueError("Pole 'kod' półproduktu jest wymagane.")
        self.polprodukty[kod] = record
        _save_json(self.pol_dir / f"{kod}.json", record)

    def delete_polprodukt(self, kod: str) -> None:
        self.polprodukty.pop(kod, None)
        path = self.pol_dir / f"{kod}.json"
        if path.exists():
            path.unlink()

    def add_or_update_produkt(self, record: dict) -> None:
        symbol = record.get("symbol")
        if not symbol:
            raise ValueError("Oznaczenie produktu jest wymagane.")
        self.produkty[symbol] = record
        _save_json(self.prd_dir / f"{symbol}.json", record)

    def delete_produkt(self, symbol: str) -> None:
        self.produkty.pop(symbol, None)
        path = self.prd_dir / f"{symbol}.json"
        if path.exists():
            path.unlink()


class MagazynBOM(ttk.Frame):
    def __init__(self, master: tk.Misc | None = None, model: WarehouseModel | None = None):
        super().__init__(master)
        self.model = model or WarehouseModel()
        self._raw_display_to_id: dict[str, str] = {}
        self._raw_id_to_display: dict[str, str] = {}
        self._raw_by_id: dict[str, dict] = {}
        self._build_ui()
        self._load_all()

    @staticmethod
    def _help(parent, row: int, text: str, column: int = 2):
        return add_help_button(parent, text, row=row, column=column, padx=(4, 0), pady=2, sticky="w")

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

    def _build_surowce(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        save_btn = ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_surowiec)
        save_btn.pack(side="right", padx=4)
        add_help_button(bar, HELP["save"]).pack(side="right", padx=(0, 2))
        delete_btn = ttk.Button(bar, text="Usuń", command=self._delete_surowiec)
        delete_btn.pack(side="right", padx=4)
        add_help_button(bar, HELP["delete"]).pack(side="right", padx=(0, 2))

        cols = ("kod", "nazwa", "rodzaj", "rozmiar", "dlugosc", "jednostka", "stan", "prog_alertu")
        headers = [
            ("kod", "ID pozycji"),
            ("nazwa", "Nazwa"),
            ("rodzaj", "Rodzaj"),
            ("rozmiar", "Rozmiar"),
            ("dlugosc", "Długość"),
            ("jednostka", "Jednostka miary"),
            ("stan", "Stan"),
            ("prog_alertu", "Próg alertu [%]"),
        ]
        tree_wrap = ttk.Frame(parent)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_sr = ttk.Treeview(tree_wrap, columns=cols, show="headings")
        self.tree_sr.pack(fill="both", expand=True)
        for key, label in headers:
            self.tree_sr.heading(key, text=label)
            self.tree_sr.column(key, width=100, anchor="w")
        self.tree_sr.bind("<<TreeviewSelect>>", self._on_sr_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.s_vars = {key: tk.StringVar() for key, _ in headers}
        labels_help = {
            "kod": HELP["raw_id"], "nazwa": HELP["raw_name"], "rodzaj": HELP["raw_type"],
            "rozmiar": HELP["raw_size"], "dlugosc": HELP["raw_length"], "jednostka": HELP["unit"],
            "stan": HELP["stock"], "prog_alertu": HELP["alert"],
        }
        for row, (key, label) in enumerate(headers):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            state = "readonly" if key == "kod" else "normal"
            ttk.Entry(form, textvariable=self.s_vars[key], state=state).grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._help(form, row, labels_help[key])
        form.columnconfigure(1, weight=1)
        self.s_vars["kod"].set(_next_code(self.model.surowce.keys(), "SUR"))

    def _on_sr_select(self, _event) -> None:
        sel = self.tree_sr.selection()
        if not sel:
            return
        values = self.tree_sr.item(sel[0], "values")
        keys = ("kod", "nazwa", "rodzaj", "rozmiar", "dlugosc", "jednostka", "stan", "prog_alertu")
        for key, value in zip(keys, values):
            self.s_vars[key].set(value)

    def _save_surowiec(self) -> None:
        rec = {key: (var.get() or "").strip() for key, var in self.s_vars.items()}
        if not rec.get("kod"):
            rec["kod"] = _next_code(self.model.surowce.keys(), "SUR")
            self.s_vars["kod"].set(rec["kod"])
        for field in ("kod", "nazwa", "rodzaj", "jednostka"):
            if not rec.get(field):
                _msg_error(self, "Surowce", f"Pole '{field}' jest wymagane.")
                return
        try:
            rec["dlugosc"] = float((rec.get("dlugosc") or "0").replace(",", "."))
            rec["stan"] = float((rec.get("stan") or "0").replace(",", "."))
            rec["prog_alertu"] = float((rec.get("prog_alertu") or "0").replace(",", "."))
        except ValueError:
            _msg_error(self, "Surowce", "Pola liczbowe muszą zawierać wartości numeryczne.")
            return
        self.model.add_or_update_surowiec(rec)
        self._load_surowce()
        self._refresh_raw_selector()
        self.s_vars["kod"].set(_next_code(self.model.surowce.keys(), "SUR"))

    def _delete_surowiec(self) -> None:
        kod = self.s_vars["kod"].get()
        if kod and messagebox.askyesno("Potwierdź", f"Usunąć surowiec '{kod}'?", parent=self):
            self.model.delete_surowiec(kod)
            self._load_surowce()
            self._refresh_raw_selector()
            self.s_vars["kod"].set(_next_code(self.model.surowce.keys(), "SUR"))

    def _raw_display(self, item_id: str, rec: dict) -> str:
        name = str(rec.get("nazwa") or rec.get("name") or "").strip()
        size = str(rec.get("rozmiar") or rec.get("wymiar") or rec.get("size") or "").strip()
        parts = [item_id]
        if name:
            parts.append(name)
        if size:
            parts.append(size)
        return " — ".join(parts)

    def _refresh_raw_selector(self) -> None:
        self._raw_by_id = self.model.inventory_raw_materials()
        self._raw_display_to_id = {}
        self._raw_id_to_display = {}
        values = []
        for item_id, rec in sorted(self._raw_by_id.items(), key=lambda pair: (str(pair[1].get("nazwa", "")).casefold(), pair[0].casefold())):
            display = self._raw_display(item_id, rec)
            values.append(display)
            self._raw_display_to_id[display] = item_id
            self._raw_id_to_display[item_id] = display
        if hasattr(self, "pp_raw_combo"):
            self.pp_raw_combo.set_values(values)

    def _build_polprodukty(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_polprodukt).pack(side="right", padx=4)
        add_help_button(bar, HELP["save"]).pack(side="right", padx=(0, 2))
        ttk.Button(bar, text="Usuń", command=self._delete_polprodukt).pack(side="right", padx=4)
        add_help_button(bar, HELP["delete"]).pack(side="right", padx=(0, 2))

        cols = ("kod", "nazwa", "sr_kod", "sr_ilosc", "sr_jednostka", "czynnosci", "norma_strat")
        headers = [
            ("kod", "Kod półproduktu"),
            ("nazwa", "Nazwa"),
            ("sr_kod", "Surowiec z magazynu"),
            ("sr_ilosc", "Ilość surowca na szt."),
            ("sr_jednostka", "Jednostka"),
            ("czynnosci", "Lista czynności"),
            ("norma_strat", "Norma strat [%]"),
        ]
        tree_wrap = ttk.Frame(parent)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_pp = ttk.Treeview(tree_wrap, columns=cols, show="headings")
        self.tree_pp.pack(fill="both", expand=True)
        for key, label in headers:
            self.tree_pp.heading(key, text=label)
            self.tree_pp.column(key, width=140, anchor="w")
        self.tree_pp.bind("<<TreeviewSelect>>", self._on_pp_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.pp_vars = {key: tk.StringVar() for key, _ in headers if key != "czynnosci"}
        self.pp_raw_choice = tk.StringVar()
        self.pp_ops = ConfigManager().get("czynnosci_technologiczne", [])
        help_by_key = {
            "kod": HELP["semi_code"], "nazwa": HELP["semi_name"], "sr_kod": HELP["raw_select"],
            "sr_ilosc": HELP["raw_qty"], "sr_jednostka": HELP["unit"], "czynnosci": HELP["ops"],
            "norma_strat": HELP["loss"],
        }
        for row, (key, label) in enumerate(headers):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            if key == "czynnosci":
                self.pp_lb = tk.Listbox(form, selectmode="multiple", exportselection=False)
                for op in self.pp_ops:
                    self.pp_lb.insert(tk.END, op)
                self.pp_lb.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            elif key == "sr_kod":
                self.pp_raw_combo = SearchableCombobox(form, textvariable=self.pp_raw_choice, state="normal")
                self.pp_raw_combo.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
                self.pp_raw_combo.bind("<<ComboboxSelected>>", self._on_raw_selected, add="+")
            else:
                state = "readonly" if key == "sr_jednostka" else "normal"
                ttk.Entry(form, textvariable=self.pp_vars[key], state=state).grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._help(form, row, help_by_key[key])
        ttk.Button(form, text="Zapisz", command=self._save_polprodukt).grid(row=len(headers), column=1, sticky="e", padx=4, pady=4)
        self._help(form, len(headers), HELP["save"])
        form.columnconfigure(1, weight=1)
        self._refresh_raw_selector()

    def _on_raw_selected(self, _event=None) -> None:
        display = self.pp_raw_choice.get().strip()
        item_id = self._raw_display_to_id.get(display)
        if not item_id and display in self._raw_by_id:
            item_id = display
        if not item_id:
            return
        rec = self._raw_by_id.get(item_id, {})
        self.pp_vars["sr_kod"].set(item_id)
        unit = str(rec.get("jednostka") or rec.get("unit") or rec.get("jm") or "").strip()
        if unit:
            self.pp_vars["sr_jednostka"].set(unit)

    def _resolve_raw_id(self) -> str:
        text = self.pp_raw_choice.get().strip()
        item_id = self._raw_display_to_id.get(text)
        if item_id:
            return item_id
        if text in self._raw_by_id:
            return text
        # pozwól filtrować tekst, ale zapis wymaga jednoznacznego istniejącego ID
        direct = self.pp_vars["sr_kod"].get().strip()
        if direct in self._raw_by_id:
            return direct
        return ""

    def _on_pp_select(self, _event) -> None:
        sel = self.tree_pp.selection()
        if not sel:
            return
        values = self.tree_pp.item(sel[0], "values")
        keys = ("kod", "nazwa", "sr_kod", "sr_ilosc", "sr_jednostka", "czynnosci", "norma_strat")
        for key, value in zip(keys, values):
            if key == "czynnosci":
                selected = [part.strip() for part in str(value).split(",") if part.strip()]
                self.pp_lb.selection_clear(0, tk.END)
                for idx, op in enumerate(self.pp_ops):
                    if op in selected:
                        self.pp_lb.selection_set(idx)
            else:
                self.pp_vars[key].set(value)
        raw_id = self.pp_vars["sr_kod"].get().strip()
        self.pp_raw_choice.set(self._raw_id_to_display.get(raw_id, raw_id))

    def _save_polprodukt(self) -> None:
        self._refresh_raw_selector()
        kod = self.pp_vars["kod"].get().strip()
        nazwa = self.pp_vars["nazwa"].get().strip()
        sr_kod = self._resolve_raw_id()
        sr_ilosc = self.pp_vars["sr_ilosc"].get().strip()
        if not kod or not nazwa or not sr_kod or not sr_ilosc:
            _msg_error(self, "Półprodukty", "Wymagane pola: kod, nazwa, istniejący surowiec z Magazynu oraz ilość.")
            return
        if sr_kod not in self._raw_by_id:
            _msg_error(self, "Półprodukty", "Wybrany surowiec nie istnieje już w Magazynie. Wybierz go ponownie z listy.")
            return
        try:
            sr_ilosc_val = float(sr_ilosc.replace(",", "."))
            if sr_ilosc_val <= 0:
                raise ValueError
        except ValueError:
            _msg_error(self, "Półprodukty", "Ilość surowca musi być liczbą większą od zera.")
            return
        try:
            norma = float((self.pp_vars["norma_strat"].get() or "0").replace(",", "."))
            if norma < 0:
                raise ValueError
        except ValueError:
            _msg_error(self, "Półprodukty", "Norma strat musi być liczbą nieujemną.")
            return
        raw_rec = self._raw_by_id[sr_kod]
        unit = str(raw_rec.get("jednostka") or raw_rec.get("unit") or self.pp_vars["sr_jednostka"].get()).strip()
        self.pp_vars["sr_kod"].set(sr_kod)
        self.pp_vars["sr_jednostka"].set(unit)
        rec = {
            "kod": kod,
            "nazwa": nazwa,
            "surowiec": {"kod": sr_kod, "ilosc_na_szt": sr_ilosc_val, "jednostka": unit},
            "czynnosci": [self.pp_lb.get(i) for i in self.pp_lb.curselection()],
            "norma_strat_procent": norma,
        }
        self.model.add_or_update_polprodukt(rec)
        self._load_polprodukty()

    def _delete_polprodukt(self) -> None:
        kod = self.pp_vars["kod"].get()
        if kod and messagebox.askyesno("Potwierdź", f"Usunąć półprodukt '{kod}'?", parent=self):
            self.model.delete_polprodukt(kod)
            self._load_polprodukty()

    def _build_produkty(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Dodaj / Zapisz", command=self._save_produkt).pack(side="right", padx=4)
        add_help_button(bar, HELP["save"]).pack(side="right", padx=(0, 2))
        ttk.Button(bar, text="Usuń", command=self._delete_produkt).pack(side="right", padx=4)
        add_help_button(bar, HELP["delete"]).pack(side="right", padx=(0, 2))

        cols = ("symbol", "nazwa", "bom")
        headers = [("symbol", "Oznaczenie produktu"), ("nazwa", "Nazwa"), ("bom", "BOM")]
        tree_wrap = ttk.Frame(parent)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_pr = ttk.Treeview(tree_wrap, columns=cols, show="headings")
        self.tree_pr.pack(fill="both", expand=True)
        for key, label in headers:
            self.tree_pr.heading(key, text=label)
            self.tree_pr.column(key, width=180, anchor="w")
        self.tree_pr.bind("<<TreeviewSelect>>", self._on_pr_select)

        form = ttk.Frame(parent)
        form.pack(fill="x", padx=6, pady=4)
        self.pr_vars = {key: tk.StringVar() for key, _ in headers}
        ttk.Label(form, text="Oznaczenie produktu").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["symbol"]).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 0, HELP["product_code"])
        ttk.Label(form, text="Nazwa").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["nazwa"]).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 1, HELP["product_name"])
        ttk.Label(form, text="BOM (np. typ=polprodukt;kod=DRUT;ilosc=2)").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["bom"]).grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 2, HELP["bom"])
        form.columnconfigure(1, weight=1)

    def _on_pr_select(self, _event) -> None:
        sel = self.tree_pr.selection()
        if not sel:
            return
        values = self.tree_pr.item(sel[0], "values")
        for key, value in zip(("symbol", "nazwa", "bom"), values):
            self.pr_vars[key].set(value)

    def _save_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        nazwa = self.pr_vars["nazwa"].get().strip()
        if not symbol or not nazwa:
            _msg_error(self, "Produkty", "Wymagane pola: oznaczenie produktu i nazwa.")
            return
        try:
            bom_list = self._parse_bom(self.pr_vars["bom"].get())
        except ValueError as exc:
            _msg_error(self, "Produkty", str(exc))
            return
        if not bom_list:
            _msg_error(self, "Produkty", "BOM musi mieć co najmniej jedną pozycję.")
            return
        rec = {"symbol": symbol, "nazwa": nazwa, "BOM": bom_list}
        self.model.add_or_update_produkt(rec)
        self._load_produkty()

    def _delete_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get()
        if symbol and messagebox.askyesno("Potwierdź", f"Usunąć produkt '{symbol}'?", parent=self):
            self.model.delete_produkt(symbol)
            self._load_produkty()

    def _parse_bom(self, text: str) -> list:
        out: list[dict] = []
        for chunk in [part.strip() for part in text.split("|") if part.strip()]:
            item: dict[str, str] = {}
            for part in [part.strip() for part in chunk.split(";") if part.strip()]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    item[key.strip()] = value.strip()
            if item:
                if "kod" not in item:
                    raise ValueError("Każda pozycja BOM musi mieć klucz 'kod'.")
                qty = item.get("ilosc") or item.get("ilosc_na_sztuke") or "1"
                try:
                    item["ilosc_na_sztuke"] = float(str(qty).replace(",", "."))
                except ValueError:
                    raise ValueError(f"Nieprawidłowa ilość BOM dla '{item.get('kod')}'.")
                item["typ"] = item.get("typ", "polprodukt")
                out.append({key: item[key] for key in ("typ", "kod", "ilosc_na_sztuke")})
        return out

    def _load_all(self) -> None:
        self._load_surowce()
        self._refresh_raw_selector()
        self._load_polprodukty()
        self._load_produkty()

    def _load_surowce(self) -> None:
        for iid in self.tree_sr.get_children():
            self.tree_sr.delete(iid)
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
        for iid in self.tree_pp.get_children():
            self.tree_pp.delete(iid)
        for kod, rec in sorted(self.model.polprodukty.items()):
            surowiec = rec.get("surowiec", {}) if isinstance(rec.get("surowiec"), dict) else {}
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
        for iid in self.tree_pr.get_children():
            self.tree_pr.delete(iid)
        for symbol, rec in sorted(self.model.produkty.items()):
            bom_txt = " | ".join(
                f"{item.get('typ', '?')}:{item.get('kod', '?')} x{item.get('ilosc_na_sztuke', 1)}"
                for item in rec.get("BOM", [])
            )
            self.tree_pr.insert("", "end", values=(symbol, rec.get("nazwa", ""), bom_txt))


def make_window(root: tk.Misc) -> ttk.Frame:
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
