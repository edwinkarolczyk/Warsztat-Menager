# WM-VERSION: 0.1
# Plik: planista_stock_runtime.py
# version: 1.0
"""Jedno źródło stanu surowców: Magazyn; Planista przechowuje definicję."""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager


_DYNAMIC_RAW_FIELDS = {
    "stan",
    "liczba_sztang",
    "rezerwacje",
    "dostepne",
    "dostępne",
    "lokalizacja",
}


def _num(value, default=0.0) -> float:
    try:
        return float(str(value if value is not None else default).strip().replace(",", "."))
    except (TypeError, ValueError):
        return float(default)


def _fmt_num(value) -> str:
    number = _num(value)
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _raw_file() -> Path:
    value = ConfigManager().path_data()
    root = Path(value) if value else Path("data")
    return root / "magazyn" / "surowce.json"


def _load_raw_definitions() -> tuple[Path, dict[str, dict]]:
    path = _raw_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = []

    records: dict[str, dict] = {}
    if isinstance(payload, list):
        iterable = payload
    elif isinstance(payload, dict):
        iterable = []
        for key, value in payload.items():
            if isinstance(value, dict):
                rec = dict(value)
                rec.setdefault("kod", key)
                iterable.append(rec)
    else:
        iterable = []

    for rec in iterable:
        if not isinstance(rec, dict):
            continue
        code = str(rec.get("kod") or rec.get("id") or "").strip()
        if code:
            records[code] = dict(rec)
    return path, records


def _save_raw_definitions(path: Path, records: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(list(records.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _physical_items() -> tuple[object, dict, dict]:
    import logika_magazyn as LM

    data = LM.load_magazyn(include_external=False)
    if not isinstance(data, dict):
        data = {"items": {}, "meta": {}}
    items = data.get("items")
    if not isinstance(items, dict):
        items = data.get("pozycje") if isinstance(data.get("pozycje"), dict) else {}
    data["items"] = items
    if isinstance(data.get("pozycje"), dict):
        data["pozycje"] = items
    return LM, data, items


def _definition_name(rec: dict, code: str) -> str:
    name = str(rec.get("nazwa") or "").strip()
    if name:
        return name
    kind = str(rec.get("rodzaj") or rec.get("typ") or "").strip()
    size = str(rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or "").strip()
    return f"{kind} - {size}".strip(" -") or code


def sync_raw_material_cards() -> dict[str, dict]:
    """Zapewnia fizyczną kartę Magazynu dla każdego surowca Planisty.

    Stary stan zapisany w ``surowce.json`` jest migrowany tylko wtedy, gdy
    karta fizyczna o danym ID jeszcze nie istnieje. Następnie pola stanu są
    usuwane z definicji, aby jedynym źródłem stanu był Magazyn.
    """
    path, definitions = _load_raw_definitions()
    if not definitions:
        return {}

    LM, data, items = _physical_items()
    warehouse_changed = False
    definitions_changed = False

    for code, rec in definitions.items():
        item = items.get(code)
        if not isinstance(item, dict):
            legacy_stock = max(0.0, _num(rec.get("stan", 0)))
            item = {
                "id": code,
                "kod": code,
                "sekcja": "Surowce",
                "typ": "surowiec",
                "nazwa": _definition_name(rec, code),
                "rozmiar": str(
                    rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or ""
                ).strip(),
                "stan": legacy_stock,
                "rezerwacje": 0.0,
                "jednostka": str(rec.get("jednostka") or "mm").strip() or "mm",
                "lokalizacja": "",
                "stan_min": 0.0,
                "zadania": [],
                "powiazanie_planista": True,
            }
            items[code] = item
            warehouse_changed = True

        metadata = {
            "id": code,
            "kod": code,
            "sekcja": "Surowce",
            "typ": "surowiec",
            "nazwa": _definition_name(rec, code),
            "rozmiar": str(
                rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or ""
            ).strip(),
            "jednostka": str(rec.get("jednostka") or "mm").strip() or "mm",
            "rodzaj": str(rec.get("rodzaj") or "").strip(),
            "dlugosc_sztangi_mm": max(
                0.0, _num(rec.get("dlugosc_sztangi_mm", rec.get("dlugosc", 0)))
            ),
            "powiazanie_planista": True,
        }
        for key, value in metadata.items():
            if item.get(key) != value:
                item[key] = value
                warehouse_changed = True
        if "stan" not in item:
            item["stan"] = 0.0
            warehouse_changed = True
        if "rezerwacje" not in item:
            item["rezerwacje"] = 0.0
            warehouse_changed = True

        for key in tuple(_DYNAMIC_RAW_FIELDS):
            if key in rec:
                rec.pop(key, None)
                definitions_changed = True
        if rec.get("jednostka") != "mm":
            rec["jednostka"] = "mm"
            definitions_changed = True

    if warehouse_changed:
        data["items"] = items
        if isinstance(data.get("pozycje"), dict):
            data["pozycje"] = items
        LM.save_magazyn(data)

    if definitions_changed:
        _save_raw_definitions(path, definitions)

    return items


def physical_raw_states() -> dict[str, dict]:
    """Zwraca wyłącznie fizyczne karty surowców z Magazynu."""
    try:
        _LM, _data, items = _physical_items()
    except Exception:
        return {}
    out = {}
    for code, item in items.items():
        if not isinstance(item, dict):
            continue
        raw_type = str(item.get("typ") or "").strip().casefold()
        section = str(item.get("sekcja") or "").strip().casefold()
        if raw_type not in {"surowiec", "surowce", "materiał", "material"} and section != "surowce":
            continue
        out[str(code)] = item
    return out


def _stock_view(code: str, definition: dict, states: dict[str, dict] | None = None) -> dict:
    states = states if states is not None else physical_raw_states()
    item = states.get(str(code)) if isinstance(states, dict) else None
    linked = isinstance(item, dict)
    item = item if linked else {}
    stock = max(0.0, _num(item.get("stan", 0)))
    reserved = max(0.0, _num(item.get("rezerwacje", 0)))
    available = max(0.0, stock - reserved)
    length = max(
        0.0,
        _num(
            definition.get(
                "dlugosc_sztangi_mm",
                definition.get("dlugosc", item.get("dlugosc_sztangi_mm", 0)),
            )
        ),
    )
    bars = stock / length if length > 0 else 0.0
    return {
        "linked": linked,
        "stock": stock,
        "reserved": reserved,
        "available": available,
        "bars": bars,
        "length": length,
        "location": str(item.get("lokalizacja") or "").strip(),
        "unit": str(item.get("jednostka") or definition.get("jednostka") or "mm").strip(),
    }


def _install_model_link() -> None:
    import gui_magazyn_bom as GMB

    Model = GMB.WarehouseModel
    if getattr(Model, "_wm_physical_stock_link", False):
        return

    old_init = Model.__init__
    old_add_raw = Model.add_or_update_surowiec

    def init_with_stock_link(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        sync_raw_material_cards()
        path, records = _load_raw_definitions()
        if path == self.src_file:
            self.surowce = records

    def add_raw_definition(self, record):
        rec = dict(record)
        for key in _DYNAMIC_RAW_FIELDS:
            rec.pop(key, None)
        rec["jednostka"] = "mm"
        result = old_add_raw(self, rec)
        sync_raw_material_cards()
        path, records = _load_raw_definitions()
        if path == self.src_file:
            self.surowce = records
        return result

    def warehouse_raw_states(self):
        return physical_raw_states()

    Model.__init__ = init_with_stock_link
    Model.add_or_update_surowiec = add_raw_definition
    Model.warehouse_raw_states = warehouse_raw_states
    Model._wm_physical_stock_link = True


def _install_planista_raw_ui() -> None:
    import gui_magazyn_bom as GMB

    UI = GMB.MagazynBOM
    if getattr(UI, "_wm_physical_stock_ui", False):
        return

    help_text = {
        "bar_length": (
            "Standardowa długość jednej sztangi używana przez Planistę do przeliczeń. "
            "Nie zmienia stanu Magazynu."
        ),
        "bars": (
            "Liczba sztang jest wyliczana z fizycznego stanu Magazynu i długości sztangi. "
            "Tego pola nie edytuje się w Planista."
        ),
        "stock": (
            "Fizyczny stan pochodzi wyłącznie z karty Magazynu o tym samym ID. "
            "Przyjęcia i rozchody wykonuj w module Magazyn."
        ),
        "reserved": (
            "Ilość zarezerwowana przez zlecenia w Magazynie. "
            "Wartość jest tylko do odczytu w Planista."
        ),
        "available": (
            "Dostępne = stan fizyczny minus rezerwacje. "
            "To jest ilość, którą Planista może jeszcze wykorzystać."
        ),
        "location": (
            "Lokalizacja pochodzi z karty Magazynu. "
            "Zmieniaj ją w module Magazyn."
        ),
        "link": (
            "Surowiec i karta Magazynu są połączone tym samym ID technicznym. "
            "Po zapisie nowego surowca WM automatycznie zakłada kartę Magazynu."
        ),
    }

    def build_surowce(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Nowy", command=self._new_surowiec).pack(side="left")
        GMB.add_help_button(bar, GMB.HELP["new_raw"], command_only=False).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(bar, text="Zapisz", command=self._save_surowiec).pack(side="right", padx=4)
        GMB.add_help_button(bar, GMB.HELP["save"]).pack(side="right", padx=(0, 4))
        ttk.Button(bar, text="Usuń", command=self._delete_surowiec).pack(side="right", padx=4)
        GMB.add_help_button(bar, GMB.HELP["delete"]).pack(side="right", padx=(0, 4))

        cols = (
            "nazwa", "rodzaj", "rozmiar", "dl_sztangi", "sztangi",
            "stan", "rezerwacje", "dostepne", "lokalizacja", "id",
        )
        labels = {
            "nazwa": "Nazwa",
            "rodzaj": "Rodzaj",
            "rozmiar": "Rozmiar",
            "dl_sztangi": "Długość sztangi [mm]",
            "sztangi": "Sztangi",
            "stan": "Stan Magazynu",
            "rezerwacje": "Zarezerwowane",
            "dostepne": "Dostępne",
            "lokalizacja": "Lokalizacja",
            "id": "ID",
        }
        self.tree_sr = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for key in cols:
            self.tree_sr.heading(key, text=labels[key])
            width = 150
            if key in {"sztangi", "id"}:
                width = 90
            elif key in {"stan", "rezerwacje", "dostepne"}:
                width = 115
            self.tree_sr.column(key, width=width, anchor="w")
        self.tree_sr.pack(fill="both", expand=True, padx=6, pady=4)
        self.tree_sr.bind("<<TreeviewSelect>>", self._on_sr_select)

        form = ttk.LabelFrame(parent, text="Karta surowca", padding=8)
        form.pack(fill="x", padx=6, pady=(2, 6))
        self.s_vars = {
            key: tk.StringVar()
            for key in (
                "kod", "rodzaj", "rozmiar", "dlugosc_sztangi_mm",
                "liczba_sztang", "stan", "rezerwacje", "dostepne",
                "lokalizacja", "prog_alertu", "powiazanie",
            )
        }

        ttk.Label(form, text="Rodzaj").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.s_kind_combo = ttk.Combobox(
            form,
            textvariable=self.s_vars["rodzaj"],
            values=tuple(self._kind_dimension_modes),
            state="readonly",
        )
        self.s_kind_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self._help(form, 0, GMB.HELP["raw_type"])

        self.s_size_label = ttk.Label(form, text="Fi [mm]")
        self.s_size_label.grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.s_vars["rozmiar"]).grid(
            row=1, column=1, sticky="ew", padx=4, pady=2
        )
        self._help(form, 1, GMB.HELP["raw_size"])

        fields = (
            ("dlugosc_sztangi_mm", "Standardowa długość sztangi [mm]", help_text["bar_length"], False),
            ("liczba_sztang", "Liczba sztang z Magazynu", help_text["bars"], True),
            ("stan", "Stan magazynowy", help_text["stock"], True),
            ("rezerwacje", "Zarezerwowane", help_text["reserved"], True),
            ("dostepne", "Dostępne", help_text["available"], True),
            ("lokalizacja", "Lokalizacja", help_text["location"], True),
            ("prog_alertu", "Próg alertu [%]", GMB.HELP["alert"], False),
            ("kod", "ID techniczne", GMB.HELP["raw_id"], True),
            ("powiazanie", "Karta Magazynu", help_text["link"], True),
        )
        for row, (key, label, field_help, readonly) in enumerate(fields, start=2):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(
                form,
                textvariable=self.s_vars[key],
                state="readonly" if readonly else "normal",
            ).grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._help(form, row, field_help)

        self.s_vars["dlugosc_sztangi_mm"].trace_add(
            "write", lambda *_: self._refresh_raw_stock_fields()
        )
        self.s_vars["rodzaj"].trace_add(
            "write", lambda *_: self._update_raw_dimension_label()
        )
        form.columnconfigure(1, weight=1)
        self._new_surowiec()

    def refresh_raw_stock_fields(self, states=None):
        if not hasattr(self, "s_vars"):
            return
        code = self.s_vars["kod"].get().strip()
        definition = dict(self.model.surowce.get(code, {}))
        definition["dlugosc_sztangi_mm"] = self.s_vars["dlugosc_sztangi_mm"].get()
        state = _stock_view(code, definition, states)
        self.s_vars["liczba_sztang"].set(_fmt_num(state["bars"]))
        if state["unit"] == "mm":
            self.s_vars["stan"].set(
                f"{_fmt_num(state['stock'])} mm ({state['stock'] / 1000:g} m)"
            )
        else:
            self.s_vars["stan"].set(
                f"{_fmt_num(state['stock'])} {state['unit']}".strip()
            )
        self.s_vars["rezerwacje"].set(
            f"{_fmt_num(state['reserved'])} {state['unit']}".strip()
        )
        self.s_vars["dostepne"].set(
            f"{_fmt_num(state['available'])} {state['unit']}".strip()
        )
        self.s_vars["lokalizacja"].set(state["location"] or "—")
        self.s_vars["powiazanie"].set(
            "Połączona" if state["linked"] else "Powstanie po zapisie"
        )

    def new_surowiec(self):
        for var in self.s_vars.values():
            var.set("")
        self.s_vars["kod"].set(GMB._next_code(self.model.surowce.keys(), "SUR"))
        kinds = tuple(self._kind_dimension_modes)
        self.s_vars["rodzaj"].set(kinds[0] if kinds else "")
        self.s_vars["prog_alertu"].set("0")
        if hasattr(self, "tree_sr"):
            self.tree_sr.selection_remove(self.tree_sr.selection())
        self._refresh_raw_stock_fields()

    def on_sr_select(self, _event=None):
        sel = self.tree_sr.selection()
        if not sel:
            return
        code = str(self.tree_sr.item(sel[0], "values")[-1])
        rec = self.model.surowce.get(code, {})
        self.s_vars["kod"].set(code)
        self.s_vars["rodzaj"].set(GMB._normalize_raw_kind(rec.get("rodzaj", "")))
        self.s_vars["rozmiar"].set(
            rec.get("rozmiar") or rec.get("wymiar") or rec.get("fi") or ""
        )
        length = rec.get("dlugosc_sztangi_mm", rec.get("dlugosc", 0))
        self.s_vars["dlugosc_sztangi_mm"].set(_fmt_num(length or 0))
        self.s_vars["prog_alertu"].set(_fmt_num(rec.get("prog_alertu", 0)))
        self._refresh_raw_stock_fields()

    def save_surowiec(self):
        code = self.s_vars["kod"].get().strip() or GMB._next_code(
            self.model.surowce.keys(), "SUR"
        )
        kind = self.s_vars["rodzaj"].get().strip()
        size = self.s_vars["rozmiar"].get().strip()
        length = _num(self.s_vars["dlugosc_sztangi_mm"].get())
        alert = _num(self.s_vars["prog_alertu"].get())
        if not kind or not size:
            GMB._msg_error(self, "Surowce", "Wymagane pola: rodzaj i Fi/Wymiar.")
            return
        if length < 0 or alert < 0:
            GMB._msg_error(
                self, "Surowce", "Długość sztangi i próg alertu nie mogą być ujemne."
            )
            return

        rec = {
            "kod": code,
            "id": code,
            "rodzaj": kind,
            "nazwa": f"{kind} - {size}",
            "dlugosc_sztangi_mm": length,
            "dlugosc": length,
            "jednostka": "mm",
            "prog_alertu": alert,
        }
        rec.update(
            GMB._raw_dimension_fields(
                kind,
                size,
                self._kind_dimension_modes.get(kind),
            )
        )
        self.model.add_or_update_surowiec(rec)
        self._load_surowce()
        self._refresh_raw_selector()
        self._new_surowiec()

    def load_surowce(self):
        sync_raw_material_cards()
        states = physical_raw_states()
        self.tree_sr.delete(*self.tree_sr.get_children())
        for code, rec in sorted(
            self.model.surowce.items(),
            key=lambda pair: str(pair[1].get("nazwa", "")).casefold(),
        ):
            state = _stock_view(code, rec, states)
            unit = state["unit"] or "mm"
            stock_txt = (
                f"{_fmt_num(state['stock'])} mm ({state['stock'] / 1000:g} m)"
                if unit == "mm"
                else f"{_fmt_num(state['stock'])} {unit}".strip()
            )
            self.tree_sr.insert(
                "",
                "end",
                values=(
                    rec.get("nazwa", ""),
                    rec.get("rodzaj", ""),
                    rec.get("rozmiar", ""),
                    _fmt_num(state["length"]),
                    _fmt_num(state["bars"]),
                    stock_txt,
                    f"{_fmt_num(state['reserved'])} {unit}".strip(),
                    f"{_fmt_num(state['available'])} {unit}".strip(),
                    state["location"] or "—",
                    code,
                ),
            )

    UI._build_surowce = build_surowce
    UI._refresh_raw_stock_fields = refresh_raw_stock_fields
    UI._new_surowiec = new_surowiec
    UI._on_sr_select = on_sr_select
    UI._save_surowiec = save_surowiec
    UI._load_surowce = load_surowce
    UI._wm_physical_stock_ui = True


def _install_magazyn_sync_before_load() -> None:
    import gui_magazyn as GM

    if getattr(GM._load_data, "_wm_sync_planista_raw", False):
        return

    old_load_data = GM._load_data

    def load_data_with_raw_sync():
        try:
            sync_raw_material_cards()
        except Exception as exc:
            print(f"[WM-WARN][PLANISTA_STOCK] synchronizacja kart surowców: {exc}")
        return old_load_data()

    load_data_with_raw_sync._wm_sync_planista_raw = True
    load_data_with_raw_sync._wm_original = old_load_data
    GM._load_data = load_data_with_raw_sync


def install_planista_stock_runtime() -> None:
    _install_model_link()
    _install_planista_raw_ui()
    _install_magazyn_sync_before_load()
