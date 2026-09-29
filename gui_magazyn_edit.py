# Plik: gui_magazyn_edit.py
# version: 1.4
# - 1.4: pełna bezpieczna edycja surowca: metadane edytowalne, stan i rezerwacje tylko do odczytu.
# - 1.3: w edycji istniejącej pozycji ukryto zadania technologiczne bez zmiany zapisanych danych.
# - 1.2: automatyczne, stabilne ID pozycji oraz wspólna pomoc kontekstowa „!”.
# - 1.1: tryb Dodaj tworzy pełną kartotekę magazynową z walidacją.
#        Edycja istniejącej pozycji zachowuje dotychczasowy zakres pól.
#        Dodano wejście do istniejącego dialogu przyjęcia towaru dla wybranej pozycji.
# - 1.0: FIX: bezpieczny zapis (_safe_save) – fallback do logika_magazyn.save_magazyn,
#        jeśli magazyn_io.save nie istnieje.

import re
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM
from ui_context_help import add_help_button


SECTION_TO_TYPE = {
    "Surowce": "surowiec",
    "Półprodukty": "półprodukt",
    "Produkty": "produkt",
}

SECTION_TO_PREFIX = {
    "Surowce": "SUR",
    "Półprodukty": "POL",
    "Produkty": "PRO",
}

HELP = {
    "id": (
        "Unikalny numer pozycji magazynowej używany przez WM do powiązania danych. "
        "Jest nadawany automatycznie i po zapisie nie zmienia się."
    ),
    "sekcja": (
        "Określa, czy kartoteka jest surowcem, półproduktem czy produktem. "
        "Od sekcji zależy także automatyczny prefiks ID."
    ),
    "nazwa": "Wpisz czytelną nazwę pozycji. Nazwa może się później zmienić bez zrywania powiązań po ID.",
    "rozmiar": "Podaj rozmiar lub przekrój, np. Ø8, M10 albo 30×30×2. Pole ułatwia wyszukiwanie właściwego materiału.",
    "rodzaj": "Rodzaj surowca jest wspólny z Planistą. Od rodzaju zależy sposób opisu: Ø, Wymiar albo Szt.",
    "tryb": "Tryb Ø / Wymiar / Szt. wynika z wybranego rodzaju surowca i nie jest zmieniany osobno dla pojedynczej pozycji.",
    "dl_sztangi": "Długość jednej sztangi w mm. Dla surowca prowadzonego w sztukach pole nie jest używane.",
    "rezerwacje": "Rezerwacje są sterowane przez zlecenia i w tym oknie są tylko do odczytu.",
    "dostepne": "Dostępne = stan fizyczny minus rezerwacje. Wartość tylko do odczytu.",
    "sztangi": "Dostępna liczba pełnych sztang; dla surowca sztukowego jest to liczba dostępnych sztuk.",
    "stan": "Podaj ilość znajdującą się na magazynie w chwili tworzenia kartoteki. Kolejne przyjęcia wykonuj przez PZ, aby zachować historię ruchu.",
    "jednostka": "Wybierz jednostkę, w której prowadzony jest stan tej pozycji. Powinna być zgodna z ilościami używanymi później w półproduktach i BOM.",
    "lokalizacja": "Wpisz miejsce składowania, np. regał A2 lub hala 1. Dzięki temu pozycję można szybko odnaleźć fizycznie.",
    "stan_min": "Określa poziom, poniżej którego pozycja wymaga uzupełnienia. WM może używać tej wartości do ostrzeżeń i zamówień braków.",
    "zadania": "Wpisz czynności technologiczne rozdzielone przecinkami. Są to operacje powiązane z daną pozycją, np. cięcie, wiercenie lub szlifowanie.",
    "save": "Zapisuje wprowadzone dane i powiązania. Przed zapisem WM sprawdza wymagane pola i poprawność liczb.",
    "cancel": "Zamyka formularz bez zapisywania nowych zmian. Istniejące wcześniej dane pozostają bez zmian.",
    "pz": "Otwiera przyjęcie towaru dla tej kartoteki. Używaj go do zwiększania stanu, aby zachować historię ruchów magazynowych.",
}


def _safe_load():
    """Czyta magazyn przez dostępny backend i zwraca zgodny słownik items."""
    try:
        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):
            data = magazyn_io.load()
        else:
            data = LM.load_magazyn()
    except Exception:
        data = {"items": {}, "meta": {}}

    if not isinstance(data, dict):
        data = {"items": {}, "meta": {}}

    items = data.get("items")
    if not isinstance(items, dict):
        items = data.get("pozycje") if isinstance(data.get("pozycje"), dict) else {}
        data["items"] = items
    if "pozycje" in data and isinstance(data.get("pozycje"), dict):
        data["pozycje"] = items
    data.setdefault("meta", {})
    return data


def _safe_save(data: dict):
    """Persistuje magazyn przez dostępny backend."""
    if HAVE_MAG_IO and hasattr(magazyn_io, "save"):
        return magazyn_io.save(data)
    if hasattr(LM, "save_magazyn"):
        return LM.save_magazyn(data)
    raise RuntimeError(
        "Brak implementacji zapisu magazynu "
        "(magazyn_io.save ani logika_magazyn.save_magazyn)"
    )


def _parse_non_negative_number(value: str, field_name: str) -> float:
    raw = str(value or "").strip().replace(",", ".")
    if not raw:
        return 0.0
    try:
        number = float(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} musi być liczbą.") from exc
    if number < 0:
        raise ValueError(f"{field_name} nie może być ujemny.")
    return number


def _is_raw_item(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    item_type = str(item.get("typ") or "").strip().casefold()
    section = str(item.get("sekcja") or "").strip().casefold()
    return item_type in {"surowiec", "surowce", "materiał", "material"} or section == "surowce"


def _normalized_stock_unit(value) -> str:
    unit = str(value or "").strip().casefold()
    return "szt" if unit in {"szt", "szt."} else "mm"


def _fmt_edit_number(value) -> str:
    number = _parse_non_negative_number(str(value or "0"), "Wartość")
    return str(int(number)) if number.is_integer() else f"{number:.3f}".rstrip("0").rstrip(".")


def _raw_mode_label(mode: str) -> str:
    key = str(mode or "").strip().casefold()
    return "Ø" if key == "fi" else "Szt." if key == "szt" else "Wymiar"


def _raw_kind_modes_for_item(item: dict) -> dict[str, str]:
    try:
        from planista_stock_runtime import raw_kind_modes
        modes = dict(raw_kind_modes())
    except Exception:
        modes = {"Rura": "fi", "Pręt": "fi", "Profil": "wymiar"}

    current = str((item or {}).get("rodzaj") or "").strip()
    if current and current not in modes:
        unit = _normalized_stock_unit((item or {}).get("jednostka"))
        if unit == "szt":
            inferred = "szt"
        elif (item or {}).get("fi") not in (None, ""):
            inferred = "fi"
        else:
            inferred = "wymiar"
        modes[current] = inferred
    return modes


def _next_item_id(items: dict, section: str) -> str:
    """Wyznacza następne czytelne i unikalne ID bez zapisywania licznika."""
    prefix = SECTION_TO_PREFIX.get(section, "MAG")
    rx = re.compile(rf"^{re.escape(prefix)}[-_]?(\d+)$", re.IGNORECASE)
    maximum = 0
    used = {str(key).strip().casefold() for key in (items or {}).keys()}
    for key in (items or {}).keys():
        match = rx.match(str(key).strip())
        if match:
            maximum = max(maximum, int(match.group(1)))
    number = maximum + 1
    while True:
        candidate = f"{prefix}-{number:03d}"
        if candidate.casefold() not in used:
            return candidate
        number += 1


def _build_new_item_payload(values: dict) -> tuple[str, dict]:
    """Waliduje formularz i zwraca (ID, rekord) nowej pozycji."""
    item_id = str(values.get("id") or "").strip()
    name = str(values.get("nazwa") or "").strip()
    unit = str(values.get("jednostka") or "").strip()
    section = str(values.get("sekcja") or "").strip()

    if not item_id:
        raise ValueError("Nie udało się nadać ID pozycji.")
    if not name:
        raise ValueError("Podaj nazwę pozycji.")
    if not unit:
        raise ValueError("Podaj jednostkę.")
    if section not in SECTION_TO_TYPE:
        raise ValueError("Wybierz sekcję Magazynu.")

    stock = _parse_non_negative_number(values.get("stan", ""), "Stan początkowy")
    minimum = _parse_non_negative_number(values.get("stan_min", ""), "Stan minimalny")
    tasks_raw = str(values.get("zadania") or "").strip()
    tasks = [part.strip() for part in tasks_raw.split(",") if part.strip()]

    item = {
        "id": item_id,
        "kod": item_id,
        "sekcja": section,
        "typ": SECTION_TO_TYPE[section],
        "nazwa": name,
        "rozmiar": str(values.get("rozmiar") or "").strip(),
        "stan": stock,
        "rezerwacje": 0.0,
        "jednostka": unit,
        "lokalizacja": str(values.get("lokalizacja") or "").strip(),
        "stan_min": minimum,
        "zadania": tasks,
    }
    return item_id, item


class MagazynEditDialog:
    def __init__(self, master, item_id, on_saved=None):
        self.master = master
        self.item_id = item_id
        self.on_saved = on_saved
        self.is_new = item_id is None

        self.data = _safe_load()
        self.items = self.data.setdefault("items", {})
        self.item = self.items.get(item_id, {}) if item_id is not None else {}
        self.is_raw = (not self.is_new) and _is_raw_item(self.item)
        self.is_linked_raw = self.is_raw and bool(self.item.get("powiazanie_planista"))

        self.win = tk.Toplevel(master)
        self.win.title("Nowa pozycja Magazynu" if self.is_new else f"Edycja pozycji: {item_id}")
        self.win.resizable(False, False)

        frm = ttk.Frame(self.win, padding=12)
        frm.grid(sticky="nsew")
        self.win.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        if self.is_new:
            self._build_new_form(frm)
        else:
            self._build_edit_form(frm)

        self.win.transient(master)
        self.win.grab_set()
        self.win.wait_window(self.win)

    def _field(self, frm, row: int, label: str, widget, help_key: str):
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        widget.grid(row=row, column=1, sticky="ew", pady=3)
        add_help_button(
            frm,
            HELP[help_key],
            row=row,
            column=2,
            padx=(6, 0),
            pady=3,
            sticky="w",
        )

    def _build_new_form(self, frm):
        self.var_section = tk.StringVar(value="Surowce")
        self.var_id = tk.StringVar(value=_next_item_id(self.items, self.var_section.get()))
        self.var_name = tk.StringVar(value="")
        self.var_roz = tk.StringVar(value="")
        self.var_stock = tk.StringVar(value="0")
        self.var_unit = tk.StringVar(value="szt")
        self.var_location = tk.StringVar(value="")
        self.var_min = tk.StringVar(value="0")
        self.var_zad = tk.StringVar(value="")

        id_entry = ttk.Entry(frm, textvariable=self.var_id, width=42, state="readonly")
        section_box = ttk.Combobox(
            frm,
            textvariable=self.var_section,
            values=tuple(SECTION_TO_TYPE.keys()),
            state="readonly",
            width=39,
        )
        section_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.var_id.set(_next_item_id(self.items, self.var_section.get())),
        )

        fields = (
            (0, "ID pozycji:", id_entry, "id"),
            (1, "Sekcja:", section_box, "sekcja"),
            (2, "Nazwa:", ttk.Entry(frm, textvariable=self.var_name, width=42), "nazwa"),
            (3, "Rozmiar:", ttk.Entry(frm, textvariable=self.var_roz, width=42), "rozmiar"),
            (4, "Stan początkowy:", ttk.Entry(frm, textvariable=self.var_stock, width=42), "stan"),
            (5, "Jednostka:", ttk.Combobox(
                frm,
                textvariable=self.var_unit,
                values=("szt", "mb", "m", "kg", "l", "opak."),
                width=39,
            ), "jednostka"),
            (6, "Lokalizacja:", ttk.Entry(frm, textvariable=self.var_location, width=42), "lokalizacja"),
            (7, "Stan minimalny:", ttk.Entry(frm, textvariable=self.var_min, width=42), "stan_min"),
            (8, "Zadania tech. (przecinki):", ttk.Entry(frm, textvariable=self.var_zad, width=42), "zadania"),
        )
        for row, label, widget, help_key in fields:
            self._field(frm, row, label, widget, help_key)

        ttk.Label(
            frm,
            text=(
                "ID nadaje WM. Kolejne przyjęcia stanu wykonuj przez Przyjęcie towaru, "
                "żeby zachować historię ruchu."
            ),
            wraplength=520,
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 2))

        btns = ttk.Frame(frm)
        btns.grid(row=10, column=0, columnspan=3, pady=(10, 0), sticky="e")
        save_btn = ttk.Button(btns, text="Zapisz", command=self.on_save)
        save_btn.pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["save"]).pack(side="right", padx=(3, 0))
        cancel_btn = ttk.Button(btns, text="Anuluj", command=self.win.destroy)
        cancel_btn.pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["cancel"]).pack(side="right", padx=(3, 0))

    def _build_edit_form(self, frm):
        if self.is_raw:
            self._build_raw_edit_form(frm)
            return

        ttk.Label(frm, text="ID pozycji:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frm, text=str(self.item_id or "")).grid(row=0, column=1, sticky="w", pady=2)
        add_help_button(frm, HELP["id"], row=0, column=2, padx=(6, 0), pady=2, sticky="w")

        self.var_roz = tk.StringVar(value=str(self.item.get("rozmiar", "")))
        self._field(
            frm,
            1,
            "Rozmiar:",
            ttk.Entry(frm, textvariable=self.var_roz, width=42),
            "rozmiar",
        )

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=3, pady=(10, 0), sticky="e")
        save_btn = ttk.Button(btns, text="Zapisz", command=self.on_save)
        save_btn.pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["save"]).pack(side="right", padx=(3, 0))
        pz_btn = ttk.Button(btns, text="Przyjęcie towaru", command=self._open_pz)
        pz_btn.pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["pz"]).pack(side="right", padx=(3, 0))
        cancel_btn = ttk.Button(btns, text="Anuluj", command=self.win.destroy)
        cancel_btn.pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["cancel"]).pack(side="right", padx=(3, 0))

    def _build_raw_edit_form(self, frm):
        self.raw_kind_modes = _raw_kind_modes_for_item(self.item)
        current_kind = str(self.item.get("rodzaj") or "").strip()
        if not current_kind and self.raw_kind_modes:
            current_kind = next(iter(self.raw_kind_modes))

        self.var_edit_name = tk.StringVar(value=str(self.item.get("nazwa") or ""))
        self.var_edit_kind = tk.StringVar(value=current_kind)
        self.var_edit_mode = tk.StringVar()
        self.var_roz = tk.StringVar(
            value=str(
                self.item.get("rozmiar")
                or self.item.get("wymiar")
                or self.item.get("fi")
                or ""
            )
        )
        self.var_edit_bar = tk.StringVar(
            value=_fmt_edit_number(
                self.item.get("dlugosc_sztangi_mm", self.item.get("dlugosc", 0))
            )
        )
        self.var_edit_location = tk.StringVar(value=str(self.item.get("lokalizacja") or ""))
        self.var_edit_min = tk.StringVar(value=_fmt_edit_number(self.item.get("stan_min", 0)))
        self.var_edit_unit = tk.StringVar()
        self.var_edit_stock = tk.StringVar()
        self.var_edit_reserved = tk.StringVar()
        self.var_edit_available = tk.StringVar()
        self.var_edit_bars = tk.StringVar()
        self._last_linear_bar_length = self.var_edit_bar.get()

        self._field(
            frm, 0, "ID pozycji:",
            ttk.Entry(frm, textvariable=tk.StringVar(value=str(self.item_id or "")), width=42, state="readonly"),
            "id",
        )
        self._field(
            frm, 1, "Nazwa:",
            ttk.Entry(frm, textvariable=self.var_edit_name, width=42),
            "nazwa",
        )
        kind_box = ttk.Combobox(
            frm,
            textvariable=self.var_edit_kind,
            values=tuple(self.raw_kind_modes.keys()),
            state="readonly",
            width=39,
        )
        self._field(frm, 2, "Rodzaj:", kind_box, "rodzaj")
        self._field(
            frm, 3, "Sposób wymiaru:",
            ttk.Entry(frm, textvariable=self.var_edit_mode, width=42, state="readonly"),
            "tryb",
        )
        self._field(
            frm, 4, "Rozmiar / oznaczenie:",
            ttk.Entry(frm, textvariable=self.var_roz, width=42),
            "rozmiar",
        )
        self.ent_edit_bar = ttk.Entry(frm, textvariable=self.var_edit_bar, width=42)
        self._field(frm, 5, "Długość sztangi [mm]:", self.ent_edit_bar, "dl_sztangi")
        self._field(
            frm, 6, "Stan minimalny:",
            ttk.Entry(frm, textvariable=self.var_edit_min, width=42),
            "stan_min",
        )
        self._field(
            frm, 7, "Lokalizacja:",
            ttk.Entry(frm, textvariable=self.var_edit_location, width=42),
            "lokalizacja",
        )
        self._field(
            frm, 8, "Jednostka:",
            ttk.Entry(frm, textvariable=self.var_edit_unit, width=42, state="readonly"),
            "jednostka",
        )
        self._field(
            frm, 9, "Stan fizyczny:",
            ttk.Entry(frm, textvariable=self.var_edit_stock, width=42, state="readonly"),
            "stan",
        )
        self._field(
            frm, 10, "Zarezerwowane:",
            ttk.Entry(frm, textvariable=self.var_edit_reserved, width=42, state="readonly"),
            "rezerwacje",
        )
        self._field(
            frm, 11, "Dostępne:",
            ttk.Entry(frm, textvariable=self.var_edit_available, width=42, state="readonly"),
            "dostepne",
        )
        self._field(
            frm, 12, "Dostępne sztangi / sztuki:",
            ttk.Entry(frm, textvariable=self.var_edit_bars, width=42, state="readonly"),
            "sztangi",
        )

        kind_box.bind("<<ComboboxSelected>>", lambda _e: self._sync_raw_edit_mode())
        self._sync_raw_edit_mode()
        self._refresh_raw_readonly_values()

        ttk.Label(
            frm,
            text=(
                "Stan fizyczny i rezerwacje są tylko do odczytu. "
                "Stan zmieniaj przez Przyjęcie towaru / korektę, aby zachować historię."
            ),
            wraplength=560,
        ).grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 2))

        btns = ttk.Frame(frm)
        btns.grid(row=14, column=0, columnspan=3, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["save"]).pack(side="right", padx=(3, 0))
        ttk.Button(btns, text="Przyjęcie towaru", command=self._open_pz).pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["pz"]).pack(side="right", padx=(3, 0))
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right", padx=(8, 0))
        add_help_button(btns, HELP["cancel"]).pack(side="right", padx=(3, 0))

    def _sync_raw_edit_mode(self):
        if not self.is_raw:
            return
        mode = str(self.raw_kind_modes.get(self.var_edit_kind.get()) or "wymiar").casefold()
        self.var_edit_mode.set(_raw_mode_label(mode))
        self.var_edit_unit.set("szt" if mode == "szt" else "mm")
        if mode == "szt":
            current = self.var_edit_bar.get().strip()
            if current not in {"", "0", "0.0"}:
                self._last_linear_bar_length = current
            self.var_edit_bar.set("0")
            self.ent_edit_bar.configure(state="readonly")
        else:
            self.ent_edit_bar.configure(state="normal")
            if self.var_edit_bar.get().strip() in {"", "0", "0.0"}:
                self.var_edit_bar.set(self._last_linear_bar_length or "6000")
        self._refresh_raw_readonly_values()

    def _refresh_raw_readonly_values(self):
        if not self.is_raw:
            return
        stock = _parse_non_negative_number(self.item.get("stan", 0), "Stan")
        reserved = _parse_non_negative_number(self.item.get("rezerwacje", 0), "Rezerwacje")
        available = max(0.0, stock - reserved)
        unit = self.var_edit_unit.get().strip() or _normalized_stock_unit(self.item.get("jednostka"))
        length = _parse_non_negative_number(self.var_edit_bar.get(), "Długość sztangi")
        if unit == "szt":
            bars = available
        else:
            bars = available / length if length > 0 else 0.0

        self.var_edit_stock.set(f"{_fmt_edit_number(stock)} {unit}".strip())
        self.var_edit_reserved.set(f"{_fmt_edit_number(reserved)} {unit}".strip())
        self.var_edit_available.set(f"{_fmt_edit_number(available)} {unit}".strip())
        suffix = "szt." if unit == "szt" else "sztang"
        self.var_edit_bars.set(f"{_fmt_edit_number(bars)} {suffix}")

    def _save_raw_edit(self):
        name = self.var_edit_name.get().strip()
        kind = self.var_edit_kind.get().strip()
        size = self.var_roz.get().strip()
        if not name:
            raise ValueError("Podaj nazwę surowca.")
        if not kind or kind not in self.raw_kind_modes:
            raise ValueError("Wybierz poprawny rodzaj surowca.")
        if not size:
            raise ValueError("Podaj rozmiar / oznaczenie surowca.")

        mode = str(self.raw_kind_modes.get(kind) or "wymiar").casefold()
        bar_length = _parse_non_negative_number(
            self.var_edit_bar.get(),
            "Długość sztangi",
        )
        stock_min = _parse_non_negative_number(self.var_edit_min.get(), "Stan minimalny")
        new_unit = "szt" if mode == "szt" else "mm"
        old_unit = _normalized_stock_unit(self.item.get("jednostka"))
        stock = _parse_non_negative_number(self.item.get("stan", 0), "Stan")
        reserved = _parse_non_negative_number(self.item.get("rezerwacje", 0), "Rezerwacje")
        if old_unit != new_unit and (stock > 0 or reserved > 0):
            raise ValueError(
                "Nie można zmienić sposobu ewidencji mm ↔ szt., gdy surowiec ma "
                "stan lub rezerwacje. Najpierw rozlicz stan i rezerwacje."
            )

        if self.is_linked_raw:
            from planista_stock_runtime import update_linked_raw_definition
            update_linked_raw_definition(
                str(self.item_id),
                name=name,
                kind=kind,
                size=size,
                bar_length_mm=bar_length,
                location=self.var_edit_location.get(),
                stock_min=stock_min,
            )
            self.data = _safe_load()
            self.items = self.data.setdefault("items", {})
            self.item = self.items.get(self.item_id, {})
            return

        self.item["nazwa"] = name
        self.item["rodzaj"] = kind
        self.item["rozmiar"] = size
        self.item["jednostka"] = new_unit
        self.item["lokalizacja"] = self.var_edit_location.get().strip()
        self.item["stan_min"] = stock_min
        self.item.pop("fi", None)
        self.item.pop("wymiar", None)
        if mode == "fi":
            self.item["fi"] = size
        elif mode == "wymiar":
            self.item["wymiar"] = size
        length = 0.0 if new_unit == "szt" else bar_length
        self.item["dlugosc_sztangi_mm"] = length
        self.item["dlugosc"] = length
        _safe_save(self.data)

    def _open_pz(self):
        if self.is_new or not self.item_id:
            return
        try:
            from gui_magazyn_pz import open_pz_dialog
            open_pz_dialog(self.win, str(self.item_id), on_saved=self._after_pz_saved)
        except TypeError:
            from gui_magazyn_pz import open_pz_dialog
            open_pz_dialog(self.win, str(self.item_id))
            self._after_pz_saved()
        except Exception as exc:
            messagebox.showerror(
                "Przyjęcie towaru",
                f"Nie udało się otworzyć przyjęcia towaru:\n{exc}",
                parent=self.win,
            )

    def _after_pz_saved(self):
        self.data = _safe_load()
        self.items = self.data.setdefault("items", {})
        self.item = self.items.get(self.item_id, {})
        if self.is_raw:
            self._refresh_raw_readonly_values()
        if callable(self.on_saved):
            try:
                self.on_saved(self.item_id)
            except Exception:
                pass

    def on_save(self):
        if self.is_new:
            values = {
                "id": self.var_id.get(),
                "sekcja": self.var_section.get(),
                "nazwa": self.var_name.get(),
                "rozmiar": self.var_roz.get(),
                "stan": self.var_stock.get(),
                "jednostka": self.var_unit.get(),
                "lokalizacja": self.var_location.get(),
                "stan_min": self.var_min.get(),
                "zadania": self.var_zad.get(),
            }
            try:
                new_id, new_item = _build_new_item_payload(values)
            except ValueError as exc:
                messagebox.showerror("Nowa pozycja", str(exc), parent=self.win)
                return

            existing = {str(key).strip().casefold() for key in self.items.keys()}
            if new_id.casefold() in existing:
                # Dane mogły zmienić się po otwarciu okna. Nadaj świeże ID zamiast
                # zmuszać użytkownika do poprawiania technicznego identyfikatora.
                new_id = _next_item_id(self.items, self.var_section.get())
                self.var_id.set(new_id)
                new_item["id"] = new_id
                new_item["kod"] = new_id

            self.items[new_id] = new_item
            meta = self.data.setdefault("meta", {})
            order = meta.setdefault("order", [])
            if isinstance(order, list) and new_id not in order:
                order.append(new_id)

            try:
                _safe_save(self.data)
            except Exception as exc:
                self.items.pop(new_id, None)
                messagebox.showerror(
                    "Błąd zapisu",
                    f"Nie udało się zapisać magazynu:\n{exc}",
                    parent=self.win,
                )
                return

            self.item_id = new_id
        else:
            if self.is_raw:
                try:
                    self._save_raw_edit()
                except Exception as exc:
                    messagebox.showerror(
                        "Edycja surowca",
                        str(exc),
                        parent=self.win,
                    )
                    return
            else:
                self.item["rozmiar"] = self.var_roz.get().strip()

                try:
                    _safe_save(self.data)
                except Exception as exc:
                    messagebox.showerror(
                        "Błąd zapisu",
                        f"Nie udało się zapisać magazynu:\n{exc}",
                        parent=self.win,
                    )
                    return

        if callable(self.on_saved):
            try:
                self.on_saved(self.item_id)
            except Exception:
                pass

        self.win.destroy()


def open_edit_dialog(master, item_id, on_saved=None):
    MagazynEditDialog(master, item_id, on_saved)


# ⏹ KONIEC KODU
