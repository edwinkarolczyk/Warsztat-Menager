# WM-VERSION: 0.2
# Wersja pliku: 1.6
"""Kartoteki produkcyjne Planisty: surowce, półprodukty i produkty/BOM."""

from __future__ import annotations

import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from config.paths import get_path
from config_manager import ConfigManager
from ui_context_help import SearchableCombobox, add_help_button
from ui_theme import ensure_theme_applied
from ui_utils import _msg_error
from wm_log import dbg as wm_dbg, err as wm_err

try:
    import logika_magazyn as LM
except Exception:  # pragma: no cover
    LM = None


def _data_dir() -> Path:
    """Zawsze korzysta z aktywnego katalogu danych WM."""
    try:
        value = ConfigManager().path_data()
        if value:
            return Path(value)
    except Exception:
        pass
    return Path("data")


# Zachowany alias dla zgodności starszych importów; model nie używa go jako źródła prawdy.
DATA_DIR = _data_dir()

HELP = {
    "new_raw": "Czyści kartę i przygotowuje nowe techniczne ID surowca. Nowy wpis powstanie dopiero po użyciu przycisku Zapisz.",
    "raw_id": "ID techniczne jest nadawane automatycznie i służy tylko do powiązań. Użytkownik pracuje nazwą i rozmiarem surowca.",
    "raw_name": "Wpisz czytelną nazwę surowca, np. Pręt fi8. Nazwę można później poprawić bez zrywania powiązań.",
    "raw_type": "Wybierz rodzaj surowca: rura, profil albo pręt. Wybór ustala, czy obok podajesz Fi, czy pełny wymiar profilu.",
    "raw_size": "Podaj Fi albo Wymiar zgodnie z ustawieniem wybranego rodzaju surowca.",
    "raw_kinds": "Dodaj tutaj rodzaje surowców używane w zakładce Surowce. Dla każdego wybierz, czy formularz ma pytać o Fi, czy o Wymiar.",
    "bars": "Podaj liczbę pełnych sztang znajdujących się na stanie. WM sam przeliczy łączną długość.",
    "bar_length": "Podaj długość jednej sztangi w milimetrach, np. 6000. Łączny stan jest liczony jako sztangi × długość.",
    "stock": "Łączny stan długości jest zapisywany w milimetrach. Dla surowca liniowego WM pokazuje także metry.",
    "alert": "Próg określa poziom ostrzegawczy zapasu.",
    "semi_code": "ID półproduktu jest nadawane automatycznie. W normalnej pracy rozpoznajesz półprodukt po nazwie oraz ilości surowca na jedną sztukę.",
    "semi_name": "Podaj nazwę półproduktu, np. Hak prosty. Gdy nazwa się powtarza, WM pokazuje obok długość lub ilość surowca na jedną sztukę.",
    "raw_select": "Wybierz surowiec z kartoteki. Lista pokazuje nazwę, rozmiar i ID techniczne.",
    "raw_qty": "Podaj ilość surowca na jedną sztukę półproduktu. Dla długości używaj mm.",
    "ops": "Zaznacz operacje technologiczne potrzebne do wykonania półproduktu.",
    "loss": "Opcjonalny procent dodatkowej straty materiału. Rzaz zlecenia jest liczony osobno przez Planistę.",
    "product_code": "Oznaczenie produktu, np. 1.775.250. Jest stałym symbolem produktu.",
    "product_name": "Czytelna nazwa produktu, np. Banaszak.",
    "bom": "Wybierz półprodukt z listy, wpisz ilość na jedną sztukę produktu i dodaj go do składu.",
    "save": "Zapisuje kartę i odświeża powiązane listy.",
    "delete": "Usuwa wybraną definicję po potwierdzeniu.",
}


def load_bom():
    path = get_path("bom.file")
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        wm_dbg("gui.bom", "bom loaded", path=path)
        return payload
    except Exception as exc:  # pragma: no cover
        wm_err("gui.bom", "bom load failed", exc, path=path)
        return []


def _load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _save_ops(lb: tk.Listbox) -> None:
    ops = list(lb.get(0, tk.END))
    path = _data_dir() / "czynnosci.json"
    _save_json(path, ops)
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


def _num(value, default=0.0) -> float:
    try:
        return float(str(value or default).replace(",", "."))
    except (TypeError, ValueError):
        return float(default)


def _fmt_num(value) -> str:
    n = _num(value)
    return str(int(n)) if n.is_integer() else f"{n:.3f}".rstrip("0").rstrip(".")


def _normalize_raw_kind(value: str) -> str:
    raw = str(value or "").strip().casefold()
    aliases = {"rura": "Rura", "profil": "Profil", "pręt": "Pręt", "pret": "Pręt"}
    return aliases.get(raw, str(value or "").strip())


def _raw_dimension_label(kind: str, mode: str | None = None) -> str:
    selected = str(mode or "").strip().casefold()
    if not selected:
        selected = "wymiar" if _normalize_raw_kind(kind) == "Profil" else "fi"
    return "Wymiar" if selected == "wymiar" else "Fi [mm]"


def _raw_dimension_fields(kind: str, value: str, mode: str | None = None) -> dict:
    normalized = _normalize_raw_kind(kind)
    size = str(value or "").strip()
    fields = {"rozmiar": size}
    selected = str(mode or "").strip().casefold()
    if selected == "wymiar" or (not selected and normalized == "Profil"):
        fields["wymiar"] = size
    else:
        fields["fi"] = size
    return fields


DEFAULT_RAW_KINDS = [
    {"nazwa": "Rura", "pole": "fi"},
    {"nazwa": "Pręt", "pole": "fi"},
    {"nazwa": "Profil", "pole": "wymiar"},
]


def _product_bom(record: dict) -> list[dict]:
    raw = record.get("BOM")
    if not isinstance(raw, list):
        raw = record.get("polprodukty")
    if isinstance(raw, dict):
        return [{"typ": "polprodukt", "kod": str(k), "ilosc_na_sztuke": _num(v, 1)} for k, v in raw.items()]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = item.get("kod") or item.get("id") or item.get("symbol")
        if not code:
            continue
        qty = item.get("ilosc_na_sztuke") or item.get("ilosc_na_szt") or item.get("ilosc") or item.get("qty") or 1
        out.append({"typ": "polprodukt", "kod": str(code), "ilosc_na_sztuke": _num(qty, 1)})
    return out


class WarehouseModel:
    def __init__(self):
        self.data_dir = _data_dir()
        self.src_file = self.data_dir / "magazyn" / "surowce.json"
        self.raw_kinds_file = self.data_dir / "magazyn" / "rodzaje_surowcow.json"
        self.pol_dir = self.data_dir / "polprodukty"
        self.prd_dir = self.data_dir / "produkty"
        for path in (self.src_file.parent, self.pol_dir, self.prd_dir):
            path.mkdir(parents=True, exist_ok=True)

        payload = _load_json(self.src_file, [])
        if isinstance(payload, list):
            self.surowce = {
                str(rec.get("kod") or rec.get("id")): rec
                for rec in payload
                if isinstance(rec, dict) and (rec.get("kod") or rec.get("id"))
            }
        elif isinstance(payload, dict):
            self.surowce = {str(k): v for k, v in payload.items() if isinstance(v, dict)}
        else:
            self.surowce = {}
        kinds = _load_json(self.raw_kinds_file, DEFAULT_RAW_KINDS)
        self.raw_kinds = [dict(item) for item in kinds if isinstance(item, dict) and item.get("nazwa")]
        if not self.raw_kinds:
            self.raw_kinds = [dict(item) for item in DEFAULT_RAW_KINDS]
        self.polprodukty = self._load_dir(self.pol_dir)
        self.produkty = self._load_dir(self.prd_dir)
        self._load_bom_file()

    @staticmethod
    def _load_dir(folder: Path) -> dict[str, dict]:
        out = {}
        for pth in folder.glob("*.json"):
            rec = _load_json(pth, None)
            if isinstance(rec, dict):
                key = rec.get("kod") or rec.get("symbol") or pth.stem
                out[str(key)] = rec
        return out

    def _load_bom_file(self) -> None:
        path_str = get_path("bom.file")
        if not path_str:
            return
        payload = load_bom()
        if not payload:
            return
        records = payload if isinstance(payload, list) else payload.get("produkty", []) if isinstance(payload, dict) else []
        if isinstance(payload, dict) and not records and (payload.get("symbol") or payload.get("kod")):
            records = [payload]
        for raw in records:
            if not isinstance(raw, dict):
                continue
            symbol = raw.get("symbol") or raw.get("kod")
            if not symbol:
                continue
            current = self.produkty.get(str(symbol), {})
            merged = dict(current)
            merged.setdefault("symbol", str(symbol))
            merged.setdefault("nazwa", raw.get("nazwa") or raw.get("name") or symbol)
            if not merged.get("BOM"):
                merged["BOM"] = _product_bom(raw)
            self.produkty[str(symbol)] = merged

    def inventory_raw_materials(self) -> dict[str, dict]:
        out = {}
        for key, rec in self.surowce.items():
            if not isinstance(rec, dict):
                continue
            item_id = str(rec.get("id") or rec.get("kod") or key).strip()
            if item_id:
                out[item_id] = {**rec, "id": item_id, "kod": item_id}
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
                    if raw_type not in {"surowiec", "surowce", "materiał", "material"} and section != "surowce":
                        continue
                    item_id = str(rec.get("id") or rec.get("kod") or key).strip()
                    if item_id:
                        out[item_id] = {**out.get(item_id, {}), **rec, "id": item_id, "kod": item_id}
        return out

    def add_or_update_surowiec(self, record: dict) -> None:
        code = str(record.get("kod") or record.get("id") or "").strip()
        if not code:
            raise ValueError("ID surowca jest wymagane.")
        rec = dict(record)
        rec["kod"] = code
        rec.setdefault("id", code)
        self.surowce[code] = rec
        _save_json(self.src_file, list(self.surowce.values()))

    def delete_surowiec(self, code: str) -> None:
        self.surowce.pop(code, None)
        _save_json(self.src_file, list(self.surowce.values()))

    def save_raw_kinds(self, records: list[dict]) -> None:
        self.raw_kinds = [dict(item) for item in records]
        _save_json(self.raw_kinds_file, self.raw_kinds)

    def add_or_update_polprodukt(self, record: dict) -> None:
        code = str(record.get("kod") or "").strip()
        if not code:
            raise ValueError("ID półproduktu jest wymagane.")
        self.polprodukty[code] = record
        _save_json(self.pol_dir / f"{code}.json", record)

    def delete_polprodukt(self, code: str) -> None:
        self.polprodukty.pop(code, None)
        path = self.pol_dir / f"{code}.json"
        if path.exists():
            path.unlink()

    def add_or_update_produkt(self, record: dict) -> None:
        symbol = str(record.get("symbol") or "").strip()
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
        self._raw_by_id = {}
        self._raw_display_to_id = {}
        self._raw_id_to_display = {}
        self._semi_display_to_id = {}
        self._semi_id_to_display = {}
        self._product_bom_rows: list[dict] = []
        self._kind_dimension_modes = {
            str(item["nazwa"]): str(item.get("pole") or "wymiar").casefold()
            for item in self.model.raw_kinds
        }
        self._build_ui()
        self._load_all()

    @staticmethod
    def _help(parent, row: int, text: str, column: int = 2):
        return add_help_button(parent, text, row=row, column=column, padx=(4, 0), pady=2, sticky="w")

    def _build_ui(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        frm_sr, frm_pp, frm_pr, frm_types = (
            ttk.Frame(self.nb), ttk.Frame(self.nb), ttk.Frame(self.nb), ttk.Frame(self.nb)
        )
        self.nb.add(frm_sr, text="Surowce")
        self.nb.add(frm_pp, text="Półprodukty")
        self.nb.add(frm_pr, text="Produkty")
        self.nb.add(frm_types, text="Rodzaje surowców")
        self._build_surowce(frm_sr)
        self._build_polprodukty(frm_pp)
        self._build_produkty(frm_pr)
        self._build_raw_kinds(frm_types)

    def _build_surowce(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Nowy", command=self._new_surowiec).pack(side="left")
        add_help_button(bar, HELP["new_raw"], command_only=False).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Zapisz", command=self._save_surowiec).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_surowiec).pack(side="right", padx=4)

        cols = ("nazwa", "rodzaj", "rozmiar", "sztangi", "dl_sztangi", "stan", "id")
        labels = {
            "nazwa": "Nazwa", "rodzaj": "Rodzaj", "rozmiar": "Rozmiar",
            "sztangi": "Sztangi", "dl_sztangi": "Długość sztangi [mm]",
            "stan": "Stan łączny", "id": "ID",
        }
        self.tree_sr = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for key in cols:
            self.tree_sr.heading(key, text=labels[key])
            self.tree_sr.column(key, width=150 if key != "id" else 90, anchor="w")
        self.tree_sr.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_sr.bind("<<TreeviewSelect>>", self._on_sr_select)

        form = ttk.LabelFrame(parent, text="Karta surowca", padding=8)
        form.pack(fill="x", padx=6, pady=(2, 6))
        self.s_vars = {k: tk.StringVar() for k in ("kod", "nazwa", "rodzaj", "rozmiar", "liczba_sztang", "dlugosc_sztangi_mm", "stan", "prog_alertu")}
        fields = [
            ("nazwa", "Nazwa", HELP["raw_name"], False),
            ("liczba_sztang", "Liczba sztang", HELP["bars"], False),
            ("dlugosc_sztangi_mm", "Długość sztangi [mm]", HELP["bar_length"], False),
            ("stan", "Stan łączny [mm]", HELP["stock"], True),
            ("prog_alertu", "Próg alertu [%]", HELP["alert"], False),
            ("kod", "ID techniczne", HELP["raw_id"], True),
        ]
        ttk.Label(form, text="Rodzaj").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.s_kind_combo = ttk.Combobox(
            form,
            textvariable=self.s_vars["rodzaj"],
            values=tuple(self._kind_dimension_modes),
            state="readonly",
        )
        self.s_kind_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 1, HELP["raw_type"])
        self.s_size_label = ttk.Label(form, text="Fi [mm]")
        self.s_size_label.grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.s_vars["rozmiar"]).grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 2, HELP["raw_size"])
        for row, (key, label, help_text, readonly) in enumerate(fields):
            if row:
                row += 2
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(form, textvariable=self.s_vars[key], state="readonly" if readonly else "normal").grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._help(form, row, help_text)
        self.s_vars["liczba_sztang"].trace_add("write", lambda *_: self._recalc_raw_total())
        self.s_vars["dlugosc_sztangi_mm"].trace_add("write", lambda *_: self._recalc_raw_total())
        self.s_vars["rodzaj"].trace_add("write", lambda *_: self._update_raw_dimension_label())
        form.columnconfigure(1, weight=1)
        self._new_surowiec()

    def _new_surowiec(self) -> None:
        for var in self.s_vars.values():
            var.set("")
        self.s_vars["kod"].set(_next_code(self.model.surowce.keys(), "SUR"))
        kinds = tuple(self._kind_dimension_modes)
        self.s_vars["rodzaj"].set(kinds[0] if kinds else "")
        self.s_vars["prog_alertu"].set("0")
        self.s_vars["stan"].set("0 mm (0 m)")
        if hasattr(self, "tree_sr"):
            self.tree_sr.selection_remove(self.tree_sr.selection())

    def _update_raw_dimension_label(self) -> None:
        if hasattr(self, "s_size_label"):
            kind = self.s_vars["rodzaj"].get()
            self.s_size_label.configure(
                text=_raw_dimension_label(kind, self._kind_dimension_modes.get(kind))
            )

    def _recalc_raw_total(self) -> None:
        if not hasattr(self, "s_vars"):
            return
        total = _num(self.s_vars["liczba_sztang"].get()) * _num(self.s_vars["dlugosc_sztangi_mm"].get())
        self.s_vars["stan"].set(f"{_fmt_num(total)} mm ({total / 1000:g} m)")

    def _on_sr_select(self, _event=None) -> None:
        sel = self.tree_sr.selection()
        if not sel:
            return
        code = str(self.tree_sr.item(sel[0], "values")[-1])
        rec = self.model.surowce.get(code, {})
        self.s_vars["kod"].set(code)
        self.s_vars["nazwa"].set(rec.get("nazwa", ""))
        self.s_vars["rodzaj"].set(_normalize_raw_kind(rec.get("rodzaj", "")))
        self.s_vars["rozmiar"].set(rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or "")
        length = rec.get("dlugosc_sztangi_mm", rec.get("dlugosc", 0))
        bars = rec.get("liczba_sztang")
        if bars is None and _num(length) > 0:
            bars = _num(rec.get("stan")) / _num(length)
        self.s_vars["liczba_sztang"].set(_fmt_num(bars or 0))
        self.s_vars["dlugosc_sztangi_mm"].set(_fmt_num(length or 0))
        self.s_vars["prog_alertu"].set(_fmt_num(rec.get("prog_alertu", 0)))
        self._recalc_raw_total()

    def _save_surowiec(self) -> None:
        code = self.s_vars["kod"].get().strip() or _next_code(self.model.surowce.keys(), "SUR")
        name = self.s_vars["nazwa"].get().strip()
        kind = self.s_vars["rodzaj"].get().strip()
        if not name or not kind:
            _msg_error(self, "Surowce", "Wymagane pola: nazwa i rodzaj.")
            return
        bars = _num(self.s_vars["liczba_sztang"].get())
        length = _num(self.s_vars["dlugosc_sztangi_mm"].get())
        alert = _num(self.s_vars["prog_alertu"].get())
        if bars < 0 or length < 0 or alert < 0:
            _msg_error(self, "Surowce", "Ilości i długości nie mogą być ujemne.")
            return
        total = bars * length
        rec = {
            "kod": code, "id": code, "nazwa": name, "rodzaj": kind,
            "liczba_sztang": bars, "dlugosc_sztangi_mm": length,
            "dlugosc": length, "jednostka": "mm", "stan": total,
            "prog_alertu": alert,
        }
        rec.update(_raw_dimension_fields(
            kind,
            self.s_vars["rozmiar"].get(),
            self._kind_dimension_modes.get(kind),
        ))
        self.model.add_or_update_surowiec(rec)
        self._load_surowce()
        self._refresh_raw_selector()
        self._new_surowiec()

    def _build_raw_kinds(self, parent) -> None:
        top = ttk.Frame(parent, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Rodzaj surowca").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Pole wymiaru").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.raw_kind_name = tk.StringVar()
        self.raw_kind_mode = tk.StringVar(value="Wymiar")
        ttk.Entry(top, textvariable=self.raw_kind_name, width=28).grid(row=1, column=0, sticky="ew")
        ttk.Combobox(
            top,
            textvariable=self.raw_kind_mode,
            values=("Fi", "Wymiar"),
            state="readonly",
            width=14,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Button(top, text="Dodaj", command=self._add_raw_kind).grid(row=1, column=2, padx=(8, 0))
        add_help_button(top, HELP["raw_kinds"], row=1, column=3, padx=(4, 0))
        top.columnconfigure(0, weight=1)

        self.tree_raw_kinds = ttk.Treeview(
            parent, columns=("nazwa", "pole"), show="headings", height=12
        )
        self.tree_raw_kinds.heading("nazwa", text="Rodzaj surowca")
        self.tree_raw_kinds.heading("pole", text="Pole w karcie surowca")
        self.tree_raw_kinds.column("nazwa", width=260, anchor="w")
        self.tree_raw_kinds.column("pole", width=180, anchor="w")
        self.tree_raw_kinds.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        ttk.Button(parent, text="Usuń zaznaczony", command=self._delete_raw_kind).pack(
            anchor="e", padx=8, pady=(0, 8)
        )
        self._refresh_raw_kinds_tree()

    def _refresh_raw_kinds_tree(self) -> None:
        if not hasattr(self, "tree_raw_kinds"):
            return
        self.tree_raw_kinds.delete(*self.tree_raw_kinds.get_children())
        for idx, item in enumerate(self.model.raw_kinds):
            mode = "Fi" if str(item.get("pole")).casefold() == "fi" else "Wymiar"
            self.tree_raw_kinds.insert("", "end", iid=str(idx), values=(item["nazwa"], mode))

    def _add_raw_kind(self) -> None:
        name = self.raw_kind_name.get().strip()
        if not name:
            _msg_error(self, "Rodzaje surowców", "Podaj nazwę rodzaju surowca.")
            return
        if any(str(item.get("nazwa", "")).casefold() == name.casefold() for item in self.model.raw_kinds):
            _msg_error(self, "Rodzaje surowców", "Taki rodzaj surowca już istnieje.")
            return
        mode = "fi" if self.raw_kind_mode.get() == "Fi" else "wymiar"
        records = [*self.model.raw_kinds, {"nazwa": name, "pole": mode}]
        self.model.save_raw_kinds(records)
        self._kind_dimension_modes[name] = mode
        self.s_kind_combo.configure(values=tuple(self._kind_dimension_modes))
        self.raw_kind_name.set("")
        self._refresh_raw_kinds_tree()

    def _delete_raw_kind(self) -> None:
        selection = self.tree_raw_kinds.selection()
        if not selection:
            _msg_error(self, "Rodzaje surowców", "Zaznacz rodzaj do usunięcia.")
            return
        idx = int(selection[0])
        item = self.model.raw_kinds[idx]
        name = str(item.get("nazwa") or "")
        if any(str(rec.get("rodzaj") or "").casefold() == name.casefold() for rec in self.model.surowce.values()):
            _msg_error(self, "Rodzaje surowców", "Nie można usunąć rodzaju używanego przez surowce.")
            return
        records = [rec for pos, rec in enumerate(self.model.raw_kinds) if pos != idx]
        self.model.save_raw_kinds(records)
        self._kind_dimension_modes.pop(name, None)
        self.s_kind_combo.configure(values=tuple(self._kind_dimension_modes))
        self._refresh_raw_kinds_tree()

    def _delete_surowiec(self) -> None:
        code = self.s_vars["kod"].get().strip()
        if code and code in self.model.surowce and messagebox.askyesno("Potwierdź", f"Usunąć surowiec '{self.model.surowce[code].get('nazwa') or code}'?", parent=self):
            self.model.delete_surowiec(code)
            self._load_surowce()
            self._refresh_raw_selector()
            self._new_surowiec()

    def _raw_display(self, item_id: str, rec: dict) -> str:
        name = str(rec.get("nazwa") or rec.get("name") or "").strip()
        size = str(rec.get("rozmiar") or rec.get("wymiar") or rec.get("size") or "").strip()
        left = " — ".join(part for part in (name, size) if part) or item_id
        return f"{left}  [{item_id}]"

    def _refresh_raw_selector(self) -> None:
        self._raw_by_id = self.model.inventory_raw_materials()
        self._raw_display_to_id.clear()
        self._raw_id_to_display.clear()
        values = []
        for item_id, rec in sorted(self._raw_by_id.items(), key=lambda pair: (str(pair[1].get("nazwa", "")).casefold(), pair[0])):
            display = self._raw_display(item_id, rec)
            values.append(display)
            self._raw_display_to_id[display] = item_id
            self._raw_id_to_display[item_id] = display
        if hasattr(self, "pp_raw_combo"):
            self.pp_raw_combo.set_values(values)

    def _build_polprodukty(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Nowy", command=self._new_polprodukt).pack(side="left")
        ttk.Button(bar, text="Zapisz", command=self._save_polprodukt).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_polprodukt).pack(side="right", padx=4)

        cols = ("nazwa", "surowiec", "ilosc", "jednostka", "czynnosci", "id")
        labels = {
            "nazwa": "Nazwa", "surowiec": "Surowiec", "ilosc": "Na szt.",
            "jednostka": "Jedn.", "czynnosci": "Operacje", "id": "ID",
        }
        self.tree_pp = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for key in cols:
            self.tree_pp.heading(key, text=labels[key])
            self.tree_pp.column(key, width=190 if key in {"nazwa", "surowiec", "czynnosci"} else 90, anchor="w")
        self.tree_pp.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_pp.bind("<<TreeviewSelect>>", self._on_pp_select)

        form = ttk.LabelFrame(parent, text="Karta półproduktu", padding=8)
        form.pack(fill="x", padx=6, pady=(2, 6))
        self.pp_vars = {k: tk.StringVar() for k in ("kod", "nazwa", "sr_kod", "sr_ilosc", "sr_jednostka", "norma_strat")}
        self.pp_raw_choice = tk.StringVar()
        self.pp_ops = list(ConfigManager().get("czynnosci_technologiczne", []) or [])
        rows = [
            ("nazwa", "Nazwa", HELP["semi_name"]),
            ("sr_kod", "Surowiec", HELP["raw_select"]),
            ("sr_ilosc", "Ilość surowca na szt.", HELP["raw_qty"]),
            ("sr_jednostka", "Jednostka", HELP["raw_qty"]),
        ]
        for row, (key, label, help_text) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            if key == "sr_kod":
                self.pp_raw_combo = SearchableCombobox(form, textvariable=self.pp_raw_choice, state="normal")
                self.pp_raw_combo.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
                self.pp_raw_combo.bind("<<ComboboxSelected>>", self._on_raw_selected, add="+")
            else:
                ttk.Entry(form, textvariable=self.pp_vars[key], state="readonly" if key == "sr_jednostka" else "normal").grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._help(form, row, help_text)
        ttk.Label(form, text="Operacje").grid(row=4, column=0, sticky="nw", padx=4, pady=2)
        self.pp_lb = tk.Listbox(form, selectmode="multiple", exportselection=False, height=4)
        for op in self.pp_ops:
            self.pp_lb.insert(tk.END, op)
        self.pp_lb.grid(row=4, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 4, HELP["ops"])
        ttk.Label(form, text="Norma strat [%]").grid(row=5, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pp_vars["norma_strat"]).grid(row=5, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 5, HELP["loss"])
        ttk.Label(form, text="ID techniczne").grid(row=6, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pp_vars["kod"], state="readonly").grid(row=6, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 6, HELP["semi_code"])
        form.columnconfigure(1, weight=1)
        self._new_polprodukt()

    def _new_polprodukt(self) -> None:
        if not hasattr(self, "pp_vars"):
            return
        for var in self.pp_vars.values():
            var.set("")
        self.pp_vars["kod"].set(_next_code(self.model.polprodukty.keys(), "POL"))
        self.pp_vars["norma_strat"].set("0")
        self.pp_raw_choice.set("")
        self.pp_lb.selection_clear(0, tk.END)

    def _on_raw_selected(self, _event=None) -> None:
        item_id = self._raw_display_to_id.get(self.pp_raw_choice.get().strip())
        if not item_id:
            return
        rec = self._raw_by_id.get(item_id, {})
        self.pp_vars["sr_kod"].set(item_id)
        self.pp_vars["sr_jednostka"].set(str(rec.get("jednostka") or rec.get("unit") or "mm"))

    def _resolve_raw_id(self) -> str:
        display = self.pp_raw_choice.get().strip()
        item_id = self._raw_display_to_id.get(display)
        if item_id:
            return item_id
        direct = self.pp_vars["sr_kod"].get().strip()
        return direct if direct in self._raw_by_id else ""

    def _on_pp_select(self, _event=None) -> None:
        sel = self.tree_pp.selection()
        if not sel:
            return
        code = str(self.tree_pp.item(sel[0], "values")[-1])
        rec = self.model.polprodukty.get(code, {})
        raw = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
        self.pp_vars["kod"].set(code)
        self.pp_vars["nazwa"].set(rec.get("nazwa", ""))
        raw_id = str(raw.get("kod") or "")
        self.pp_vars["sr_kod"].set(raw_id)
        self.pp_raw_choice.set(self._raw_id_to_display.get(raw_id, raw_id))
        self.pp_vars["sr_ilosc"].set(_fmt_num(raw.get("ilosc_na_szt", 0)))
        self.pp_vars["sr_jednostka"].set(raw.get("jednostka", ""))
        self.pp_vars["norma_strat"].set(_fmt_num(rec.get("norma_strat_procent", 0)))
        selected = set(rec.get("czynnosci", []) or [])
        self.pp_lb.selection_clear(0, tk.END)
        for idx, op in enumerate(self.pp_ops):
            if op in selected:
                self.pp_lb.selection_set(idx)

    def _save_polprodukt(self) -> None:
        self._refresh_raw_selector()
        code = self.pp_vars["kod"].get().strip() or _next_code(self.model.polprodukty.keys(), "POL")
        name = self.pp_vars["nazwa"].get().strip()
        raw_id = self._resolve_raw_id()
        qty = _num(self.pp_vars["sr_ilosc"].get())
        if not name or not raw_id or qty <= 0:
            _msg_error(self, "Półprodukty", "Wymagane: nazwa półproduktu, istniejący surowiec i ilość większa od zera.")
            return
        raw_rec = self._raw_by_id[raw_id]
        unit = str(raw_rec.get("jednostka") or raw_rec.get("unit") or "mm")
        rec = {
            "kod": code, "nazwa": name,
            "surowiec": {"kod": raw_id, "ilosc_na_szt": qty, "jednostka": unit},
            "czynnosci": [self.pp_lb.get(i) for i in self.pp_lb.curselection()],
            "norma_strat_procent": max(0, _num(self.pp_vars["norma_strat"].get())),
        }
        self.model.add_or_update_polprodukt(rec)
        self._load_polprodukty()
        self._refresh_semi_selector()
        self._new_polprodukt()

    def _delete_polprodukt(self) -> None:
        code = self.pp_vars["kod"].get().strip()
        if code and code in self.model.polprodukty and messagebox.askyesno("Potwierdź", f"Usunąć półprodukt '{self.model.polprodukty[code].get('nazwa') or code}'?", parent=self):
            self.model.delete_polprodukt(code)
            self._load_polprodukty()
            self._refresh_semi_selector()
            self._new_polprodukt()

    @staticmethod
    def _semi_measure(rec: dict) -> str:
        raw = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
        qty = _num(raw.get("ilosc_na_szt", 0))
        if qty <= 0:
            return ""
        unit = str(raw.get("jednostka") or "mm").strip()
        return f"{_fmt_num(qty)} {unit}".strip()

    def _semi_display(self, code: str, rec: dict) -> str:
        name = str(rec.get("nazwa") or code).strip()
        measure = self._semi_measure(rec)
        label = f"{name} — {measure}" if measure else name
        return f"{label}  [{code}]"

    def _refresh_semi_selector(self) -> None:
        self._semi_display_to_id.clear()
        self._semi_id_to_display.clear()
        values = []
        for code, rec in sorted(
            self.model.polprodukty.items(),
            key=lambda pair: (str(pair[1].get("nazwa", "")).casefold(), self._semi_measure(pair[1]), pair[0]),
        ):
            display = self._semi_display(code, rec)
            values.append(display)
            self._semi_display_to_id[display] = code
            self._semi_id_to_display[code] = display
        if hasattr(self, "pr_semi_combo"):
            self.pr_semi_combo.set_values(values)

    def _build_produkty(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Nowy", command=self._new_produkt).pack(side="left")
        ttk.Button(bar, text="Zapisz produkt", command=self._save_produkt).pack(side="right", padx=4)
        ttk.Button(bar, text="Usuń", command=self._delete_produkt).pack(side="right", padx=4)

        self.tree_pr = ttk.Treeview(parent, columns=("symbol", "nazwa", "sklad"), show="headings", height=9)
        for key, label, width in (("symbol", "Oznaczenie", 150), ("nazwa", "Nazwa produktu", 240), ("sklad", "Skład", 420)):
            self.tree_pr.heading(key, text=label)
            self.tree_pr.column(key, width=width, anchor="w")
        self.tree_pr.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_pr.bind("<<TreeviewSelect>>", self._on_pr_select)

        form = ttk.LabelFrame(parent, text="Karta produktu", padding=8)
        form.pack(fill="x", padx=6, pady=(2, 6))
        self.pr_vars = {"symbol": tk.StringVar(), "nazwa": tk.StringVar()}
        ttk.Label(form, text="Oznaczenie produktu").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["symbol"]).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 0, HELP["product_code"])
        ttk.Label(form, text="Nazwa").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.pr_vars["nazwa"]).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 1, HELP["product_name"])

        bom_box = ttk.LabelFrame(form, text="Półprodukty w produkcie", padding=6)
        bom_box.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(8, 2))
        self.pr_semi_choice = tk.StringVar()
        self.pr_semi_qty = tk.StringVar(value="1")
        self.pr_semi_combo = SearchableCombobox(bom_box, textvariable=self.pr_semi_choice, state="normal")
        self.pr_semi_combo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Entry(bom_box, textvariable=self.pr_semi_qty, width=8).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(bom_box, text="Dodaj / zmień", command=self._add_bom_row).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(bom_box, text="Usuń ze składu", command=self._remove_bom_row).grid(row=0, column=3)
        self.pr_bom_tree = ttk.Treeview(bom_box, columns=("nazwa", "wymiar", "ilosc", "id"), show="headings", height=5)
        self.pr_bom_tree.heading("nazwa", text="Półprodukt")
        self.pr_bom_tree.heading("wymiar", text="Długość / surowiec na 1 szt.")
        self.pr_bom_tree.heading("ilosc", text="Ilość na produkt")
        self.pr_bom_tree.heading("id", text="ID")
        self.pr_bom_tree.column("nazwa", width=260)
        self.pr_bom_tree.column("wymiar", width=220)
        self.pr_bom_tree.column("ilosc", width=120)
        self.pr_bom_tree.column("id", width=100)
        self.pr_bom_tree.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        bom_box.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        self._refresh_semi_selector()

    def _new_produkt(self) -> None:
        if not hasattr(self, "pr_vars"):
            return
        self.pr_vars["symbol"].set("")
        self.pr_vars["nazwa"].set("")
        self._product_bom_rows = []
        self._render_bom_rows()
        self.pr_semi_choice.set("")
        self.pr_semi_qty.set("1")

    def _add_bom_row(self) -> None:
        code = self._semi_display_to_id.get(self.pr_semi_choice.get().strip())
        qty = _num(self.pr_semi_qty.get())
        if not code or code not in self.model.polprodukty or qty <= 0:
            _msg_error(self, "Produkty", "Wybierz półprodukt i podaj ilość większą od zera.")
            return
        updated = False
        for row in self._product_bom_rows:
            if row["kod"] == code:
                row["ilosc_na_sztuke"] = qty
                updated = True
                break
        if not updated:
            self._product_bom_rows.append({"typ": "polprodukt", "kod": code, "ilosc_na_sztuke": qty})
        self._render_bom_rows()

    def _remove_bom_row(self) -> None:
        sel = self.pr_bom_tree.selection()
        if not sel:
            return
        code = str(self.pr_bom_tree.item(sel[0], "values")[-1])
        self._product_bom_rows = [row for row in self._product_bom_rows if row.get("kod") != code]
        self._render_bom_rows()

    def _render_bom_rows(self) -> None:
        if not hasattr(self, "pr_bom_tree"):
            return
        self.pr_bom_tree.delete(*self.pr_bom_tree.get_children())
        for row in self._product_bom_rows:
            code = str(row.get("kod") or "")
            rec = self.model.polprodukty.get(code, {})
            name = rec.get("nazwa") or code
            measure = self._semi_measure(rec)
            self.pr_bom_tree.insert("", "end", values=(name, measure, _fmt_num(row.get("ilosc_na_sztuke", 1)), code))

    def _on_pr_select(self, _event=None) -> None:
        sel = self.tree_pr.selection()
        if not sel:
            return
        symbol = str(self.tree_pr.item(sel[0], "values")[0])
        rec = self.model.produkty.get(symbol, {})
        self.pr_vars["symbol"].set(symbol)
        self.pr_vars["nazwa"].set(rec.get("nazwa", ""))
        self._product_bom_rows = _product_bom(rec)
        self._render_bom_rows()

    def _save_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        name = self.pr_vars["nazwa"].get().strip()
        if not symbol or not name:
            _msg_error(self, "Produkty", "Wymagane pola: oznaczenie produktu i nazwa.")
            return
        if not self._product_bom_rows:
            _msg_error(self, "Produkty", "Dodaj przynajmniej jeden półprodukt do składu produktu.")
            return
        rec = {"symbol": symbol, "nazwa": name, "BOM": [dict(row) for row in self._product_bom_rows]}
        self.model.add_or_update_produkt(rec)
        self._load_produkty()
        self._new_produkt()

    def _delete_produkt(self) -> None:
        symbol = self.pr_vars["symbol"].get().strip()
        if symbol and symbol in self.model.produkty and messagebox.askyesno("Potwierdź", f"Usunąć produkt '{self.model.produkty[symbol].get('nazwa') or symbol}'?", parent=self):
            self.model.delete_produkt(symbol)
            self._load_produkty()
            self._new_produkt()

    # Zachowana dla zgodności ze starszymi testami/importami.
    def _parse_bom(self, text: str) -> list:
        out = []
        for chunk in [part.strip() for part in str(text).split("|") if part.strip()]:
            item = {}
            for part in [part.strip() for part in chunk.split(";") if part.strip()]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    item[key.strip()] = value.strip()
            if not item.get("kod"):
                continue
            qty = _num(item.get("ilosc") or item.get("ilosc_na_sztuke") or 1, 1)
            out.append({"typ": "polprodukt", "kod": item["kod"], "ilosc_na_sztuke": qty})
        return out

    def _load_all(self) -> None:
        self._load_surowce()
        self._refresh_raw_selector()
        self._load_polprodukty()
        self._refresh_semi_selector()
        self._load_produkty()

    def _load_surowce(self) -> None:
        self.tree_sr.delete(*self.tree_sr.get_children())
        for code, rec in sorted(self.model.surowce.items(), key=lambda pair: str(pair[1].get("nazwa", "")).casefold()):
            bars = rec.get("liczba_sztang", "")
            length = rec.get("dlugosc_sztangi_mm", rec.get("dlugosc", ""))
            total = _num(rec.get("stan", 0))
            self.tree_sr.insert("", "end", values=(rec.get("nazwa", ""), rec.get("rodzaj", ""), rec.get("rozmiar", ""), _fmt_num(bars), _fmt_num(length), f"{_fmt_num(total)} mm ({total / 1000:g} m)", code))

    def _load_polprodukty(self) -> None:
        self.tree_pp.delete(*self.tree_pp.get_children())
        for code, rec in sorted(self.model.polprodukty.items(), key=lambda pair: str(pair[1].get("nazwa", "")).casefold()):
            raw = rec.get("surowiec") if isinstance(rec.get("surowiec"), dict) else {}
            raw_id = str(raw.get("kod") or "")
            raw_name = self._raw_by_id.get(raw_id, {}).get("nazwa") or raw_id
            self.tree_pp.insert("", "end", values=(rec.get("nazwa", ""), raw_name, _fmt_num(raw.get("ilosc_na_szt", 0)), raw.get("jednostka", ""), ", ".join(rec.get("czynnosci", []) or []), code))

    def _load_produkty(self) -> None:
        self.tree_pr.delete(*self.tree_pr.get_children())
        for symbol, rec in sorted(self.model.produkty.items(), key=lambda pair: str(pair[1].get("nazwa", "")).casefold()):
            parts = []
            for item in _product_bom(rec):
                code = item["kod"]
                semi = self.model.polprodukty.get(code, {})
                name = semi.get("nazwa") or code
                measure = self._semi_measure(semi)
                label = f"{name} — {measure}" if measure else name
                parts.append(f"{label} ×{_fmt_num(item.get('ilosc_na_sztuke', 1))}")
            self.tree_pr.insert("", "end", values=(symbol, rec.get("nazwa", ""), ", ".join(parts)))


def make_window(root: tk.Misc) -> ttk.Frame:
    return MagazynBOM(root)


if __name__ == "__main__":  # pragma: no cover
    root = tk.Tk()
    ensure_theme_applied(root)
    root.title("Kartoteki produkcyjne")
    MagazynBOM(root).pack(fill="both", expand=True)
    root.mainloop()
