# Plik: gui_magazyn_edit.py
# version: 1.1
# - 1.1: tryb Dodaj tworzy pełną kartotekę magazynową z walidacją.
#        Edycja istniejącej pozycji zachowuje dotychczasowy zakres pól.
#        Dodano wejście do istniejącego dialogu PZ dla wybranej pozycji.
# - 1.0: FIX: bezpieczny zapis (_safe_save) – fallback do logika_magazyn.save_magazyn,
#        jeśli magazyn_io.save nie istnieje.

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import magazyn_io
    HAVE_MAG_IO = True
except Exception:
    magazyn_io = None
    HAVE_MAG_IO = False

import logika_magazyn as LM


SECTION_TO_TYPE = {
    "Surowce": "surowiec",
    "Półprodukty": "półprodukt",
    "Produkty": "produkt",
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


def _build_new_item_payload(values: dict) -> tuple[str, dict]:
    """Waliduje formularz i zwraca (ID, rekord) nowej pozycji."""
    item_id = str(values.get("id") or "").strip()
    name = str(values.get("nazwa") or "").strip()
    unit = str(values.get("jednostka") or "").strip()
    section = str(values.get("sekcja") or "").strip()

    if not item_id:
        raise ValueError("Podaj Kod / ID pozycji.")
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

    def _build_new_form(self, frm):
        self.var_id = tk.StringVar(value="")
        self.var_section = tk.StringVar(value="Surowce")
        self.var_name = tk.StringVar(value="")
        self.var_roz = tk.StringVar(value="")
        self.var_stock = tk.StringVar(value="0")
        self.var_unit = tk.StringVar(value="szt")
        self.var_location = tk.StringVar(value="")
        self.var_min = tk.StringVar(value="0")
        self.var_zad = tk.StringVar(value="")

        fields = (
            (0, "Kod / ID:", ttk.Entry(frm, textvariable=self.var_id, width=42)),
            (1, "Sekcja:", ttk.Combobox(
                frm,
                textvariable=self.var_section,
                values=tuple(SECTION_TO_TYPE.keys()),
                state="readonly",
                width=39,
            )),
            (2, "Nazwa:", ttk.Entry(frm, textvariable=self.var_name, width=42)),
            (3, "Rozmiar:", ttk.Entry(frm, textvariable=self.var_roz, width=42)),
            (4, "Stan początkowy:", ttk.Entry(frm, textvariable=self.var_stock, width=42)),
            (5, "Jednostka:", ttk.Combobox(
                frm,
                textvariable=self.var_unit,
                values=("szt", "mb", "m", "kg", "l", "opak."),
                width=39,
            )),
            (6, "Lokalizacja:", ttk.Entry(frm, textvariable=self.var_location, width=42)),
            (7, "Stan minimalny:", ttk.Entry(frm, textvariable=self.var_min, width=42)),
            (8, "Zadania tech. (przecinki):", ttk.Entry(frm, textvariable=self.var_zad, width=42)),
        )
        for row, label, widget in fields:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            widget.grid(row=row, column=1, sticky="ew", pady=3)

        ttk.Label(
            frm,
            text=(
                "Dodaj tworzy kartotekę pozycji. Kolejne przyjęcia stanu wykonuj przez PZ, "
                "żeby zachować historię ruchu."
            ),
            wraplength=520,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 2))

        btns = ttk.Frame(frm)
        btns.grid(row=10, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right")

    def _build_edit_form(self, frm):
        ttk.Label(frm, text="Rozmiar:").grid(row=0, column=0, sticky="w", pady=2)
        self.var_roz = tk.StringVar(value=str(self.item.get("rozmiar", "")))
        ttk.Entry(frm, textvariable=self.var_roz, width=42).grid(
            row=0, column=1, sticky="ew", pady=2
        )

        ttk.Label(frm, text="Zadania tech. (oddziel przecinkami):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        zad = self.item.get("zadania", [])
        if isinstance(zad, list):
            zadania_txt = ", ".join(str(z).strip() for z in zad if str(z).strip())
        else:
            zadania_txt = str(zad or "")
        self.var_zad = tk.StringVar(value=zadania_txt)
        ttk.Entry(frm, textvariable=self.var_zad, width=42).grid(
            row=1, column=1, sticky="ew", pady=2
        )

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Przyjęcie PZ", command=self._open_pz).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Anuluj", command=self.win.destroy).pack(side="right")

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
            messagebox.showerror("PZ", f"Nie udało się otworzyć przyjęcia PZ:\n{exc}", parent=self.win)

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
                messagebox.showerror(
                    "Nowa pozycja",
                    f"Pozycja o Kodzie / ID '{new_id}' już istnieje.",
                    parent=self.win,
                )
                return

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
            rozmiar = self.var_roz.get().strip()
            zadania_raw = self.var_zad.get().strip()
            zadania = [z.strip() for z in zadania_raw.split(",")] if zadania_raw else []
            zadania = [z for z in zadania if z]
            self.item["rozmiar"] = rozmiar
            self.item["zadania"] = zadania

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
