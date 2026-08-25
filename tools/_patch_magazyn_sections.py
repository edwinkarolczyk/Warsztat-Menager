from pathlib import Path

path = Path('gui_magazyn.py')
s = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one match, got {count}: {old[:100]!r}')
    s = s.replace(old, new, 1)

replace_once(
    '# version: 1.0\n# Zmiany 1.7.0:',
    '# version: 1.8.0\n# Zmiany 1.8.0:\n# - Podział widoku Magazynu na sekcje: Surowce / Półprodukty / Produkty.\n# - Tabela pokazuje osobno: Stan, Zarezerwowane, Dostępne, Jednostkę i Lokalizację.\n# - Widok korzysta ze wspólnego loadera Magazynu z dołączeniem surowców i półproduktów.\n# - Brak zmian w mechanice rezerwacji i zapisu stanów.\n# Zmiany 1.7.0:'
)

replace_once(
    'COLUMNS = ("id", "typ", "rozmiar", "nazwa", "stan", "zadania")\n',
    '''COLUMNS = (\n    "id",\n    "sekcja",\n    "typ",\n    "rozmiar",\n    "nazwa",\n    "stan",\n    "rezerwacje",\n    "dostepne",\n    "jednostka",\n    "lokalizacja",\n    "zadania",\n)\n\nWAREHOUSE_SECTIONS = ("(wszystkie)", "Surowce", "Półprodukty", "Produkty")\n\n\ndef _warehouse_section(item: dict) -> str:\n    """Mapuje istniejące typy Magazynu na trzy sekcje robocze UI."""\n    raw = str(\n        item.get("typ")\n        or item.get("type")\n        or item.get("rodzaj")\n        or ""\n    ).strip().lower()\n    normalized = (\n        raw.replace("ł", "l")\n        .replace("ó", "o")\n        .replace("ą", "a")\n        .replace("ę", "e")\n        .replace("ś", "s")\n        .replace("ć", "c")\n        .replace("ń", "n")\n        .replace("ż", "z")\n        .replace("ź", "z")\n    )\n    normalized = " ".join(normalized.replace("_", " ").replace("-", " ").split())\n\n    if normalized in {\n        "surowiec", "surowce", "material", "materialy", "raw material", "raw materials"\n    }:\n        return "Surowce"\n    if normalized in {\n        "polprodukt", "polprodukty", "komponent", "komponenty", "semi product", "semiproduct"\n    }:\n        return "Półprodukty"\n    if normalized in {\n        "produkt", "produkty", "produkt gotowy", "produkty gotowe",\n        "wyrob", "wyroby", "wyrob gotowy", "gotowy", "finished product"\n    }:\n        return "Produkty"\n    return ""\n\n\ndef _warehouse_number(value) -> float:\n    try:\n        if isinstance(value, str):\n            value = value.strip().replace(",", ".")\n        return float(value or 0)\n    except (TypeError, ValueError):\n        return 0.0\n\n\ndef _warehouse_number_text(value) -> str:\n    return f"{_warehouse_number(value):g}"\n'''
)

replace_once(
    '''def build_magazyn_toolbar(toolbar: ttk.Frame, owner):\n    ttk.Label(toolbar, text="Typ:", style="WM.TLabel").pack(side="left", padx=(0, 6))\n''',
    '''def build_magazyn_toolbar(toolbar: ttk.Frame, owner):\n    ttk.Label(toolbar, text="Sekcja:", style="WM.TLabel").pack(side="left", padx=(0, 6))\n    owner.cbo_section = ttk.Combobox(\n        toolbar,\n        textvariable=owner._filter_section,\n        values=WAREHOUSE_SECTIONS,\n        state="readonly",\n        width=15,\n    )\n    owner.cbo_section.pack(side="left", padx=(0, 10))\n    owner.cbo_section.bind("<<ComboboxSelected>>", lambda _e: owner._apply_filters())\n\n    ttk.Label(toolbar, text="Typ:", style="WM.TLabel").pack(side="left", padx=(0, 6))\n'''
)

old_load = '''def _load_data():\n    """Czyta magazyn; preferuje ``magazyn_io`` z fallbackiem na plik."""\n    path = get_path("warehouse.stock_source")\n    _log_magazyn_paths("_load_data")\n    print(f"[WM-ROOT][MAGAZYN] loader path from config.paths = {path}")\n    data = {}\n    if HAVE_MAG_IO and hasattr(magazyn_io, "load"):\n        try:\n            if path:\n                try:\n                    data = magazyn_io.load(path)\n                except TypeError:\n                    data = magazyn_io.load()\n            else:\n                data = magazyn_io.load()\n        except Exception:\n            data = {}\n\n    if not isinstance(data, dict) or not data:\n        data = load_stock()\n\n    if not isinstance(data, dict) or not data:\n        try:\n            data = LM.load_magazyn()\n        except Exception:\n            data = {}\n\n    items, order, format_name = _normalize_magazyn_payload(data)\n'''
new_load = '''def _load_data():\n    """Czyta wspólny Magazyn, łącznie z surowcami i półproduktami."""\n    path = get_path("warehouse.stock_source")\n    _log_magazyn_paths("_load_data")\n    print(f"[WM-ROOT][MAGAZYN] loader path from config.paths = {path}")\n\n    data = {}\n    try:\n        data = LM.load_magazyn(include_external=True)\n    except Exception as exc:\n        wm_err("gui.magazyn", "canonical stock load failed", exc, path=path)\n        data = {}\n\n    # Fallbacki tylko dla starszych instalacji / testów.\n    if not isinstance(data, dict) or not data:\n        if HAVE_MAG_IO and hasattr(magazyn_io, "load"):\n            try:\n                if path:\n                    try:\n                        data = magazyn_io.load(path)\n                    except TypeError:\n                        data = magazyn_io.load()\n                else:\n                    data = magazyn_io.load()\n            except Exception:\n                data = {}\n\n    if not isinstance(data, dict) or not data:\n        data = load_stock()\n\n    items, order, format_name = _normalize_magazyn_payload(data)\n'''
replace_once(old_load, new_load)

old_format = '''def _format_row(item_id: str, item: dict):\n    """Mapowanie rekordu na 6 kolumn z miękkimi fallbackami."""\n    typ = (item.get("typ") or "").strip()\n    rozmiar = (item.get("rozmiar") or "").strip()\n    nazwa = (item.get("nazwa") or "").strip()\n\n    # Stan + jednostka (opcjonalnie)\n    stan_val = item.get("stan", "")\n    try:\n        stan_txt = f"{float(stan_val):g}"\n    except Exception:\n        stan_txt = str(stan_val)\n    jm = (item.get("jednostka") or "").strip()\n    if jm:\n        stan_txt = f"{stan_txt} {jm}"\n\n    # Zadania (lista lub string)\n    z = item.get("zadania", [])\n    if isinstance(z, list):\n        zadania = ", ".join([str(x).strip() for x in z if str(x).strip()])\n    else:\n        zadania = str(z).strip()\n\n    return (item_id, typ or "-", rozmiar or "-", nazwa or "-", stan_txt or "-", zadania)\n'''
new_format = '''def _format_row(item_id: str, item: dict):\n    """Mapowanie rekordu na czytelny stan: fizyczny, rezerwacje i dostępne."""\n    sekcja = _warehouse_section(item)\n    typ = str(item.get("typ") or "").strip()\n    rozmiar = str(item.get("rozmiar") or "").strip()\n    nazwa = str(item.get("nazwa") or "").strip()\n\n    stan = _warehouse_number(item.get("stan", item.get("ilosc", item.get("ilość", 0))))\n    rezerwacje = max(0.0, _warehouse_number(item.get("rezerwacje", 0)))\n    dostepne = max(0.0, stan - rezerwacje)\n    jednostka = str(item.get("jednostka") or item.get("jm") or "").strip()\n    lokalizacja = str(\n        item.get("lokalizacja")\n        or item.get("location")\n        or item.get("miejsce")\n        or item.get("regał")\n        or item.get("regal")\n        or ""\n    ).strip()\n\n    z = item.get("zadania", [])\n    if isinstance(z, list):\n        zadania = ", ".join([str(x).strip() for x in z if str(x).strip()])\n    else:\n        zadania = str(z).strip()\n\n    return (\n        item_id,\n        sekcja or "-",\n        typ or "-",\n        rozmiar or "-",\n        nazwa or "-",\n        f"{stan:g}",\n        f"{rezerwacje:g}",\n        f"{dostepne:g}",\n        jednostka or "-",\n        lokalizacja or "-",\n        zadania,\n    )\n'''
replace_once(old_format, new_format)

replace_once(
    '''        # stan filtrów\n        self._filter_typ = tk.StringVar(value="(wszystkie)")\n        self._filter_query = tk.StringVar(value="")\n''',
    '''        # stan filtrów\n        self._filter_section = tk.StringVar(value="(wszystkie)")\n        self._filter_typ = tk.StringVar(value="(wszystkie)")\n        self._filter_query = tk.StringVar(value="")\n'''
)

old_headers = '''        # Nagłówki\n        self.tree.heading("id", text="ID")\n        self.tree.heading("typ", text="Typ")\n        self.tree.heading("rozmiar", text="Rozmiar")\n        self.tree.heading("nazwa", text="Nazwa")\n        self.tree.heading("stan", text="Stan")\n        self.tree.heading("zadania", text="Tech. zadania")\n\n        # Szerokości startowe\n        self.tree.column("id", width=110, anchor="w")\n        self.tree.column("typ", width=140, anchor="w")\n        self.tree.column("rozmiar", width=160, anchor="w")\n        self.tree.column("nazwa", width=380, anchor="w")\n        self.tree.column("stan", width=120, anchor="center")\n        self.tree.column("zadania", width=280, anchor="w")\n'''
new_headers = '''        # Nagłówki\n        self.tree.heading("id", text="ID")\n        self.tree.heading("sekcja", text="Sekcja")\n        self.tree.heading("typ", text="Typ")\n        self.tree.heading("rozmiar", text="Rozmiar")\n        self.tree.heading("nazwa", text="Nazwa")\n        self.tree.heading("stan", text="Stan")\n        self.tree.heading("rezerwacje", text="Zarezerwowane")\n        self.tree.heading("dostepne", text="Dostępne")\n        self.tree.heading("jednostka", text="Jednostka")\n        self.tree.heading("lokalizacja", text="Lokalizacja")\n        self.tree.heading("zadania", text="Tech. zadania")\n\n        # Szerokości startowe\n        self.tree.column("id", width=95, anchor="w")\n        self.tree.column("sekcja", width=115, anchor="w")\n        self.tree.column("typ", width=110, anchor="w")\n        self.tree.column("rozmiar", width=130, anchor="w")\n        self.tree.column("nazwa", width=240, anchor="w")\n        self.tree.column("stan", width=85, anchor="center")\n        self.tree.column("rezerwacje", width=110, anchor="center")\n        self.tree.column("dostepne", width=95, anchor="center")\n        self.tree.column("jednostka", width=80, anchor="center")\n        self.tree.column("lokalizacja", width=120, anchor="w")\n        self.tree.column("zadania", width=200, anchor="w")\n'''
replace_once(old_headers, new_headers)

replace_once(
    '''    def _clear_filters(self):\n        self._filter_typ.set("(wszystkie)")\n        self._filter_query.set("")\n''',
    '''    def _clear_filters(self):\n        self._filter_section.set("(wszystkie)")\n        self._filter_typ.set("(wszystkie)")\n        self._filter_query.set("")\n        section = getattr(self, "cbo_section", None)\n        if section is not None:\n            try:\n                section.set(self._filter_section.get())\n            except Exception:\n                pass\n'''
)

replace_once(
    '''        q = self._filter_query.get().strip().lower()\n        cbo = getattr(self, "cbo_typ", None)\n        if cbo is None:\n            return\n        try:\n            t = cbo.get()\n        except Exception:\n            t = self._filter_typ.get()\n''',
    '''        q = self._filter_query.get().strip().lower()\n        cbo = getattr(self, "cbo_typ", None)\n        section_box = getattr(self, "cbo_section", None)\n        if cbo is None:\n            return\n        try:\n            t = cbo.get()\n        except Exception:\n            t = self._filter_typ.get()\n        try:\n            section = section_box.get() if section_box is not None else self._filter_section.get()\n        except Exception:\n            section = self._filter_section.get()\n'''
)

replace_once(
    '''        for item_id, item in getattr(self, "_all_rows", []):\n            # filtr po typie\n            typ_val = str(item.get("typ", "")).strip()\n            if t != "(wszystkie)" and typ_val.lower() != t.lower():\n                continue\n\n            # filtr po szukajce (Nazwa/Rozmiar)\n''',
    '''        for item_id, item in getattr(self, "_all_rows", []):\n            # filtr po sekcji roboczej\n            section_val = _warehouse_section(item)\n            if section != "(wszystkie)" and section_val != section:\n                continue\n\n            # filtr po dokładnym typie źródłowym\n            typ_val = str(item.get("typ", "")).strip()\n            if t != "(wszystkie)" and typ_val.lower() != t.lower():\n                continue\n\n            # filtr po szukajce (Nazwa/Rozmiar)\n'''
)

path.write_text(s, encoding='utf-8')
print('patched gui_magazyn.py')
