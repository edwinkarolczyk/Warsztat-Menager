# Plik: gui_magazyn_edit.py
# version: 1.3
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
    "rozmiar": "Podaj rozmiar lub przekrój, np. fi8 albo 30×30×2. Pole ułatwia wyszukiwanie właściwego materiału.",
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
