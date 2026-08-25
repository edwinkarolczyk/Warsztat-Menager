from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------
# polprodukty_store.py
# ---------------------------------------------------------------------
semi_path = Path("polprodukty_store.py")
semi = semi_path.read_text(encoding="utf-8")
semi = replace_once(semi, "# version: 1.0\n", "# version: 1.1\n", "semi version")
semi = replace_once(
    semi,
    "# U2A-2: jedno źródło półproduktów w aktywnym WM_DATA_ROOT/polprodukty.\n",
    "# U2A-2: jedno źródło półproduktów w aktywnym WM_DATA_ROOT/polprodukty.\n"
    "# Zmiany 1.1:\n"
    "# - Półprodukt może mieć własny wielopoziomowy skład z innych półproduktów.\n"
    "# - Dodano bezpieczny zapis składu z kopią pliku i bez migracji pozostałych danych.\n",
    "semi changelog",
)
semi = replace_once(
    semi,
    "    @staticmethod\n    def _normalise(raw: dict[str, Any], path: Path) -> dict[str, Any]:\n",
    "    @staticmethod\n"
    "    def _normalise_sklad(raw: dict[str, Any]) -> list[dict[str, Any]]:\n"
    "        value = raw.get('sklad')\n"
    "        if not isinstance(value, list):\n"
    "            value = raw.get('polprodukty')\n"
    "        if not isinstance(value, list):\n"
    "            value = raw.get('BOM')\n"
    "        if not isinstance(value, list):\n"
    "            return []\n"
    "        out: list[dict[str, Any]] = []\n"
    "        for row in value:\n"
    "            if not isinstance(row, dict):\n"
    "                continue\n"
    "            code = str(row.get('kod') or row.get('id') or row.get('symbol') or '').strip()\n"
    "            if not code:\n"
    "                continue\n"
    "            qty = row.get('ilosc_na_szt', row.get('ilosc_na_sztuke', row.get('ilosc', 1)))\n"
    "            out.append({'kod': code, 'ilosc_na_szt': qty})\n"
    "        return out\n\n"
    "    @staticmethod\n"
    "    def _normalise(raw: dict[str, Any], path: Path) -> dict[str, Any]:\n",
    "semi sklad helper",
)
semi = replace_once(
    semi,
    "            'surowiec': dict(material),\n            'norma_strat_proc': loss,\n",
    "            'surowiec': dict(material),\n"
    "            'sklad': SemiProductCatalog._normalise_sklad(raw),\n"
    "            'norma_strat_proc': loss,\n",
    "semi normalise sklad field",
)
semi = replace_once(
    semi,
    "    def delete(self, item: dict[str, Any]) -> None:\n",
    "    def save_sklad(self, item: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:\n"
    "        raw_path = item.get('_path')\n"
    "        if not raw_path:\n"
    "            raise SemiProductCatalogError('Nie można ustalić pliku półproduktu.')\n"
    "        path = Path(str(raw_path))\n"
    "        if not path.exists():\n"
    "            raise SemiProductCatalogError('Plik półproduktu już nie istnieje.')\n"
    "        raw = self._read_json(path)\n"
    "        if raw is None:\n"
    "            raise SemiProductCatalogError('Nie można odczytać pliku półproduktu.')\n"
    "        own_code = str(item.get('kod') or raw.get('kod') or raw.get('id') or '').strip()\n"
    "        clean: list[dict[str, Any]] = []\n"
    "        for entry in entries:\n"
    "            if not isinstance(entry, dict):\n"
    "                continue\n"
    "            code = str(entry.get('kod') or entry.get('id') or entry.get('symbol') or '').strip()\n"
    "            if not code:\n"
    "                raise SemiProductCatalogError('Każda pozycja składu musi mieć kod półproduktu.')\n"
    "            if own_code and code.casefold() == own_code.casefold():\n"
    "                raise SemiProductCatalogError('Półprodukt nie może zawierać samego siebie.')\n"
    "            qty_raw = entry.get('ilosc_na_szt', entry.get('ilosc_na_sztuke', entry.get('ilosc', 1)))\n"
    "            try:\n"
    "                qty = float(str(qty_raw).replace(',', '.'))\n"
    "            except (TypeError, ValueError):\n"
    "                raise SemiProductCatalogError(f\"Nieprawidłowa ilość składnika '{code}'.\") from None\n"
    "            if qty <= 0:\n"
    "                raise SemiProductCatalogError(f\"Ilość składnika '{code}' musi być większa od zera.\")\n"
    "            if qty.is_integer():\n"
    "                qty = int(qty)\n"
    "            clean.append({'kod': code, 'ilosc_na_szt': qty})\n"
    "        payload = dict(raw)\n"
    "        payload['sklad'] = clean\n"
    "        if isinstance(payload.get('polprodukty'), list):\n"
    "            payload['polprodukty'] = [dict(row) for row in clean]\n"
    "        self._backup(path)\n"
    "        tmp = path.with_suffix(path.suffix + '.tmp')\n"
    "        try:\n"
    "            with tmp.open('w', encoding='utf-8') as handle:\n"
    "                json.dump(payload, handle, ensure_ascii=False, indent=2)\n"
    "            os.replace(tmp, path)\n"
    "        finally:\n"
    "            try:\n"
    "                tmp.unlink(missing_ok=True)\n"
    "            except Exception:\n"
    "                pass\n"
    "        return self._normalise(payload, path)\n\n"
    "    def delete(self, item: dict[str, Any]) -> None:\n",
    "semi save sklad",
)
semi_path.write_text(semi, encoding="utf-8")


# ---------------------------------------------------------------------
# gui_polprodukt_sklad.py
# ---------------------------------------------------------------------
composition_gui = r'''# version: 1.0
# Moduł: gui_polprodukt_sklad
# Edytor wielopoziomowego składu półproduktu.

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from polprodukty_store import SemiProductCatalog, SemiProductCatalogError


def open_semiproduct_composition(master, catalog: SemiProductCatalog, item: dict, on_saved=None):
    code = str(item.get('kod') or '').strip()
    win = tk.Toplevel(master)
    win.title(f"Skład półproduktu — {code}")
    win.geometry('820x520')
    win.transient(master.winfo_toplevel())
    win.grab_set()

    entries = copy.deepcopy(item.get('sklad') or [])
    rows: dict[str, dict] = {}

    top = ttk.Frame(win, padding=10)
    top.pack(fill='x')
    ttk.Label(top, text=f"Półprodukt: {code} — {item.get('nazwa','')}", font=('Segoe UI', 11, 'bold')).pack(side='left')

    btns = ttk.Frame(top)
    btns.pack(side='right')

    tree = ttk.Treeview(win, columns=('kod', 'nazwa', 'ilosc'), show='headings', height=16)
    tree.heading('kod', text='Półprodukt składowy')
    tree.heading('nazwa', text='Nazwa')
    tree.heading('ilosc', text='Ilość na 1 szt.')
    tree.column('kod', width=220, anchor='w')
    tree.column('nazwa', width=360, anchor='w')
    tree.column('ilosc', width=120, anchor='center')
    tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    status_var = tk.StringVar(value='Skład półproduktu może mieć kolejne poziomy. Silnik zapotrzebowania wykrywa pętle.')
    ttk.Label(win, textvariable=status_var, wraplength=780).pack(fill='x', padx=10, pady=(0, 8))

    def catalog_map():
        try:
            return {str(x.get('kod') or ''): x for x in catalog.list_items()}
        except Exception:
            return {}

    def refresh():
        tree.delete(*tree.get_children())
        rows.clear()
        cmap = catalog_map()
        for idx, entry in enumerate(entries):
            child = str(entry.get('kod') or '').strip()
            child_item = cmap.get(child, {})
            iid = f'sklad-{idx}'
            rows[iid] = entry
            tree.insert('', 'end', iid=iid, values=(child, child_item.get('nazwa', ''), entry.get('ilosc_na_szt', 1)))

    def selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0].split('-', 1)[1])
        except Exception:
            return None

    def edit_entry(idx=None):
        cmap = catalog_map()
        choices = [k for k in sorted(cmap, key=str.casefold) if k and k.casefold() != code.casefold()]
        existing = entries[idx] if idx is not None else {}
        child_var = tk.StringVar(value=str(existing.get('kod') or ''))
        qty_var = tk.StringVar(value=str(existing.get('ilosc_na_szt') or 1))
        dlg = tk.Toplevel(win)
        dlg.title('Pozycja składu półproduktu')
        dlg.transient(win)
        dlg.grab_set()
        form = ttk.Frame(dlg, padding=12)
        form.pack(fill='both', expand=True)
        ttk.Label(form, text='Półprodukt:').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Combobox(form, textvariable=child_var, values=choices, state='normal', width=44).grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Ilość na 1 szt.:').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=qty_var).grid(row=1, column=1, sticky='ew', pady=4)
        form.columnconfigure(1, weight=1)

        def accept():
            child = child_var.get().strip()
            if not child:
                messagebox.showerror('Skład półproduktu', 'Wybierz półprodukt.', parent=dlg)
                return
            if child.casefold() == code.casefold():
                messagebox.showerror('Skład półproduktu', 'Półprodukt nie może zawierać samego siebie.', parent=dlg)
                return
            try:
                qty = float(qty_var.get().replace(',', '.'))
            except ValueError:
                messagebox.showerror('Skład półproduktu', 'Ilość musi być liczbą.', parent=dlg)
                return
            if qty <= 0:
                messagebox.showerror('Skład półproduktu', 'Ilość musi być większa od zera.', parent=dlg)
                return
            if qty.is_integer():
                qty = int(qty)
            row = {'kod': child, 'ilosc_na_szt': qty}
            if idx is None:
                entries.append(row)
            else:
                entries[idx] = row
            dlg.destroy()
            refresh()

        controls = ttk.Frame(form)
        controls.grid(row=2, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(controls, text='Anuluj', command=dlg.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(controls, text='OK', command=accept).pack(side='right')

    def remove():
        idx = selected_index()
        if idx is None:
            return
        del entries[idx]
        refresh()

    def save():
        try:
            saved = catalog.save_sklad(item, entries)
        except SemiProductCatalogError as exc:
            messagebox.showerror('Skład półproduktu', str(exc), parent=win)
            return
        except Exception as exc:
            messagebox.showerror('Skład półproduktu', f'Nie udało się zapisać:\n{exc}', parent=win)
            return
        if callable(on_saved):
            try:
                on_saved(saved)
            except Exception:
                pass
        win.destroy()

    ttk.Button(btns, text='Dodaj', command=lambda: edit_entry(None)).pack(side='left', padx=3)
    ttk.Button(btns, text='Edytuj', command=lambda: edit_entry(selected_index()) if selected_index() is not None else None).pack(side='left', padx=3)
    ttk.Button(btns, text='Usuń', command=remove).pack(side='left', padx=3)
    ttk.Button(btns, text='Zapisz skład', command=save).pack(side='left', padx=(12, 3))
    tree.bind('<Double-1>', lambda _e: edit_entry(selected_index()) if selected_index() is not None else None)
    refresh()
    return win
'''
Path("gui_polprodukt_sklad.py").write_text(composition_gui, encoding="utf-8")


# ---------------------------------------------------------------------
# gui_planowanie_bom.py
# ---------------------------------------------------------------------
bom_path = Path("gui_planowanie_bom.py")
bom = bom_path.read_text(encoding="utf-8")
bom = replace_once(bom, "# version: 1.1\n", "# version: 1.2\n", "bom ui version")
bom = replace_once(
    bom,
    "# - Nazwy wewnętrzne pozostają bez zmian dla zgodności danych.\n",
    "# - Nazwy wewnętrzne pozostają bez zmian dla zgodności danych.\n"
    "# Zmiany 1.2:\n"
    "# - Dodano edytor wielopoziomowego Składu półproduktu.\n"
    "# - Usuwanie półproduktu uwzględnia użycie w produktach i innych półproduktach.\n",
    "bom ui changelog",
)
bom = replace_once(
    bom,
    "from polprodukty_store import SemiProductCatalog, SemiProductCatalogError\n",
    "from polprodukty_store import SemiProductCatalog, SemiProductCatalogError\n"
    "from gui_polprodukt_sklad import open_semiproduct_composition\n",
    "bom composition import",
)
bom = replace_once(
    bom,
    "            ttk.Button(top, text='Edytuj', command=self._edit).pack(side='right', padx=3)\n            ttk.Button(top, text='Dodaj', command=self._add).pack(side='right', padx=3)\n",
    "            ttk.Button(top, text='Skład półproduktu', command=self._composition).pack(side='right', padx=3)\n"
    "            ttk.Button(top, text='Edytuj', command=self._edit).pack(side='right', padx=3)\n"
    "            ttk.Button(top, text='Dodaj', command=self._add).pack(side='right', padx=3)\n",
    "bom composition button",
)
bom = replace_once(
    bom,
    "    def _form(self, item):\n",
    "    def _composition(self):\n"
    "        if not self.can_manage:\n"
    "            return\n"
    "        item = self._selected()\n"
    "        if not item:\n"
    "            messagebox.showinfo('Półprodukty', 'Najpierw wybierz półprodukt.', parent=self)\n"
    "            return\n"
    "        open_semiproduct_composition(self, self.catalog, item, on_saved=lambda _saved: self.refresh())\n\n"
    "    def _form(self, item):\n",
    "bom composition method",
)
bom = replace_once(
    bom,
    "        if used_by:\n            messagebox.showerror('Półprodukt', 'Nie można usunąć — półprodukt jest używany w składzie produktu: ' + ', '.join(used_by[:12]), parent=self)\n            return\n",
    "        try:\n"
    "            for parent in self.catalog.list_items():\n"
    "                parent_code = str(parent.get('kod') or '')\n"
    "                if parent_code.casefold() == code.casefold():\n"
    "                    continue\n"
    "                if any(str(row.get('kod') or '').casefold() == code.casefold() for row in (parent.get('sklad') or [])):\n"
    "                    used_by.append(f\"półprodukt {parent_code}\")\n"
    "        except Exception:\n"
    "            pass\n"
    "        if used_by:\n"
    "            messagebox.showerror('Półprodukt', 'Nie można usunąć — półprodukt jest używany w: ' + ', '.join(used_by[:12]), parent=self)\n"
    "            return\n",
    "bom delete relation check",
)
bom_path.write_text(bom, encoding="utf-8")


# ---------------------------------------------------------------------
# planowanie_magazyn.py
# ---------------------------------------------------------------------
warehouse_bridge = r'''# version: 1.0
# Moduł: planowanie_magazyn
# Most Planowanie <-> istniejący Magazyn. Nie tworzy równoległej bazy stanów.

from __future__ import annotations

from typing import Any


class WarehouseIntegrationError(RuntimeError):
    pass


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def load_stock_snapshot() -> dict[str, dict[str, Any]]:
    try:
        import logika_magazyn as LM
        data = LM.load_magazyn(include_external=True)
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się wczytać Magazynu: {exc}') from exc
    items = data.get('items') or data.get('pozycje') or {}
    if not isinstance(items, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, raw in items.items():
        if not isinstance(raw, dict):
            continue
        code = str(raw.get('kod') or raw.get('id') or key or '').strip()
        if not code:
            continue
        stock = _num(raw.get('stan', raw.get('ilosc', 0)))
        reserved = max(0.0, _num(raw.get('rezerwacje', 0)))
        free = max(0.0, stock - reserved)
        out[code.casefold()] = {
            'id': str(raw.get('id') or key or code),
            'kod': code,
            'nazwa': str(raw.get('nazwa') or code),
            'typ': str(raw.get('typ') or '').strip(),
            'jednostka': str(raw.get('jednostka') or '').strip(),
            'stan': stock,
            'rezerwacje': reserved,
            'wolne': free,
        }
    return out


def add_semiproduct_surplus(code: str, qty: float, *, name: str = '', user: str = '', context: str = '') -> dict[str, Any]:
    code = str(code or '').strip()
    qty = _num(qty)
    if not code:
        raise WarehouseIntegrationError('Brak kodu półproduktu dla naddatku.')
    if qty <= 0:
        return {'kod': code, 'dodano': 0.0}
    try:
        import logika_magazyn as LM
        data = LM.load_magazyn(include_external=True)
        items = data.get('items') or {}
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się wczytać Magazynu: {exc}') from exc

    existing_id = None
    existing = None
    for iid, raw in items.items():
        if not isinstance(raw, dict):
            continue
        item_code = str(raw.get('kod') or raw.get('id') or iid or '').strip()
        if item_code.casefold() == code.casefold():
            existing_id = str(raw.get('id') or iid or code)
            existing = dict(raw)
            break

    if existing is not None:
        typ = str(existing.get('typ') or '').strip().casefold()
        if typ and typ not in {'półprodukt', 'polprodukt', 'semi', 'semiproduct', 'komponent'}:
            raise WarehouseIntegrationError(
                f"Pozycja '{code}' istnieje w Magazynie jako typ '{existing.get('typ')}', nie jako półprodukt."
            )
        new_state = _num(existing.get('stan')) + qty
        payload = dict(existing)
        payload.update({
            'id': existing_id or code,
            'nazwa': str(existing.get('nazwa') or name or code),
            'typ': 'półprodukt',
            'jednostka': str(existing.get('jednostka') or 'szt'),
            'stan': new_state,
        })
    else:
        payload = {
            'id': code,
            'nazwa': str(name or code),
            'typ': 'półprodukt',
            'jednostka': 'szt',
            'stan': qty,
            'min_poziom': 0,
            'rezerwacje': 0,
        }
    try:
        saved = LM.upsert_item(payload)
    except Exception as exc:
        raise WarehouseIntegrationError(f"Nie udało się dopisać naddatku '{code}' do Magazynu: {exc}") from exc
    try:
        logger = getattr(LM, '_log_mag', None)
        if callable(logger):
            logger('naddatek_polproduktu', {'item_id': code, 'ilosc': qty, 'by': user, 'ctx': context})
    except Exception:
        pass
    return {'kod': code, 'dodano': qty, 'stan': _num((saved or {}).get('stan'))}
'''
Path("planowanie_magazyn.py").write_text(warehouse_bridge, encoding="utf-8")


# ---------------------------------------------------------------------
# planowanie_zapotrzebowanie.py -- replace with warehouse-aware engine
# ---------------------------------------------------------------------
requirements_engine = r'''# version: 1.1
# Moduł: planowanie_zapotrzebowanie
# U2A-3: wyliczanie zapotrzebowania bez ruchów magazynowych i bez Dyspozycji.
# Zmiany 1.1:
# - Zapotrzebowanie może uwzględniać wolne stany istniejącego Magazynu.
# - Naddatek półproduktu jest wykorzystywany przed rozwinięciem go do niższych poziomów i surowców.
# - Obsługa wielopoziomowego składu półproduktu oraz agregacji surowców.

from __future__ import annotations

from typing import Any

from planowanie_magazyn import load_stock_snapshot
from polprodukty_store import SemiProductCatalog
from produkty_store import ProductCatalog


class RequirementError(RuntimeError):
    pass


def unique_order_number(proposed: str, orders: list[dict[str, Any]], *, exclude_id: str | None = None) -> str:
    base = str(proposed or '').strip()
    if not base:
        raise RequirementError('Nr zlecenia jest wymagany.')
    used = {
        str(row.get('number') or '').strip().casefold()
        for row in orders
        if str(row.get('id') or '') != str(exclude_id or '')
    }
    if base.casefold() not in used:
        return base
    index = 2
    while f'{base}_{index}'.casefold() in used:
        index += 1
    return f'{base}_{index}'


def _number(value: Any, default: float | None = None) -> float:
    if value is None or value == '':
        if default is not None:
            return default
        raise ValueError
    if isinstance(value, str):
        value = value.strip().replace(',', '.')
    return float(value)


def _entry_code(entry: dict[str, Any]) -> str:
    return str(entry.get('kod') or entry.get('id') or entry.get('symbol') or '').strip()


def _entry_qty(entry: dict[str, Any]) -> float:
    return _number(entry.get('ilosc_na_szt', entry.get('ilosc_na_sztuke', entry.get('ilosc', 1))), 1.0)


def _nested_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ('sklad', 'polprodukty'):
        value = raw.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, dict)]
    value = raw.get('BOM')
    if isinstance(value, list):
        out = []
        for row in value:
            if not isinstance(row, dict):
                continue
            typ = str(row.get('typ') or 'polprodukt').strip().casefold()
            if typ not in {'polprodukt', 'półprodukt', 'semi', 'semiproduct'}:
                continue
            out.append({
                'kod': _entry_code(row),
                'ilosc_na_szt': row.get('ilosc_na_szt', row.get('ilosc_na_sztuke', row.get('ilosc', 1))),
            })
        return out
    value = raw.get('bom')
    if isinstance(value, dict):
        return [{'kod': str(code), 'ilosc_na_szt': qty} for code, qty in value.items()]
    return []


class RequirementCalculator:
    def __init__(self, product_catalog: ProductCatalog, semi_catalog: SemiProductCatalog | None = None) -> None:
        self.product_catalog = product_catalog
        self.semi_catalog = semi_catalog or SemiProductCatalog(product_catalog.cfg)

    def _product_map(self):
        return {
            str(item.get('kod') or '').strip().casefold(): item
            for item in self.product_catalog.list_products()
            if str(item.get('kod') or '').strip()
        }

    def _semi_map(self):
        return {
            str(item.get('kod') or '').strip().casefold(): item
            for item in self.semi_catalog.list_items()
            if str(item.get('kod') or '').strip()
        }

    def calculate(self, product_code: str, product_qty: int | float) -> dict[str, Any]:
        return self._calculate_product(product_code, product_qty, use_stock=False)

    def calculate_with_stock(self, product_code: str, product_qty: int | float) -> dict[str, Any]:
        return self._calculate_product(product_code, product_qty, use_stock=True)

    def calculate_semi_with_stock(self, semi_code: str, qty: int | float, *, ignore_root_stock: bool = True) -> dict[str, Any]:
        code = str(semi_code or '').strip()
        if not code:
            raise RequirementError('Brak kodu półproduktu.')
        try:
            amount = _number(qty)
        except (TypeError, ValueError):
            raise RequirementError('Ilość półproduktu musi być liczbą.') from None
        if amount <= 0:
            raise RequirementError('Ilość półproduktu musi być większa od zera.')
        semi_map = self._semi_map()
        if code.casefold() not in semi_map:
            raise RequirementError(f"Nie znaleziono półproduktu '{code}'.")
        return self._calculate_from_roots(
            roots=[{'kod': code, 'ilosc_na_szt': amount}],
            product_code=code,
            product_name=str(semi_map[code.casefold()].get('nazwa') or ''),
            product_qty=1,
            revision=1,
            semi_map=semi_map,
            use_stock=True,
            root_ignore_stock={code.casefold()} if ignore_root_stock else set(),
        )

    def _calculate_product(self, product_code: str, product_qty: int | float, *, use_stock: bool) -> dict[str, Any]:
        code = str(product_code or '').strip()
        if not code:
            raise RequirementError('Zlecenie nie ma wybranego produktu.')
        try:
            qty = _number(product_qty)
        except (TypeError, ValueError):
            raise RequirementError('Ilość produktu musi być liczbą.') from None
        if qty <= 0:
            raise RequirementError('Ilość produktu musi być większa od zera.')
        products = self._product_map()
        product = products.get(code.casefold())
        if product is None:
            raise RequirementError(f"Nie znaleziono produktu '{code}' w katalogu produktów.")
        roots = product.get('polprodukty') or []
        if not isinstance(roots, list):
            roots = []
        scaled = []
        for entry in roots:
            if not isinstance(entry, dict):
                continue
            row = dict(entry)
            try:
                row['ilosc_na_szt'] = _entry_qty(row) * qty
            except (TypeError, ValueError):
                row['ilosc_na_szt'] = 0
            scaled.append(row)
        return self._calculate_from_roots(
            roots=scaled,
            product_code=code,
            product_name=str(product.get('nazwa') or ''),
            product_qty=qty,
            revision=product.get('bom_revision', 1),
            semi_map=self._semi_map(),
            use_stock=use_stock,
            root_ignore_stock=set(),
        )

    def _calculate_from_roots(self, *, roots, product_code, product_name, product_qty, revision, semi_map, use_stock, root_ignore_stock):
        try:
            stock = load_stock_snapshot() if use_stock else {}
        except Exception as exc:
            stock = {}
            stock_error = str(exc)
        else:
            stock_error = ''
        stock_remaining = {key: float(row.get('wolne', 0) or 0) for key, row in stock.items()}
        semi_totals: dict[str, dict[str, Any]] = {}
        raw_totals: dict[tuple[str, str], dict[str, Any]] = {}
        warnings: list[str] = []
        if stock_error:
            warnings.append(stock_error)
        if not roots:
            warnings.append(f"'{product_code}' nie ma zdefiniowanego składu.")

        def walk(code: str, qty: float, path: tuple[str, ...], source: str, ignore_stock_here: bool = False):
            key = str(code or '').strip().casefold()
            if not key or qty <= 0:
                return
            if key in path:
                warnings.append('Wykryto pętlę w składzie półproduktów: ' + ' → '.join((*path, key)))
                return
            semi = semi_map.get(key)
            bucket = semi_totals.setdefault(key, {
                'kod': str(code).strip(),
                'nazwa': str((semi or {}).get('nazwa') or ''),
                'ilosc': 0.0,
                'z_magazynu': 0.0,
                'do_wykonania': 0.0,
                'zrodla': set(),
            })
            bucket['ilosc'] += qty
            bucket['zrodla'].add(source)
            use_here = use_stock and not ignore_stock_here
            available = stock_remaining.get(key, 0.0) if use_here else 0.0
            taken = min(qty, available)
            if taken > 0:
                stock_remaining[key] = max(0.0, available - taken)
            missing = max(0.0, qty - taken)
            bucket['z_magazynu'] += taken
            bucket['do_wykonania'] += missing
            if semi is None:
                warnings.append(f"Brak definicji półproduktu '{code}'.")
                return
            if missing <= 0:
                return
            raw = semi.get('_raw') if isinstance(semi.get('_raw'), dict) else {}
            nested = _nested_entries(raw)
            for child in nested:
                child_code = _entry_code(child)
                if not child_code:
                    warnings.append(f"Półprodukt '{code}' zawiera pozycję bez kodu.")
                    continue
                try:
                    child_qty = _entry_qty(child)
                except (TypeError, ValueError):
                    warnings.append(f"Półprodukt '{code}' ma nieprawidłową ilość składnika '{child_code}'.")
                    continue
                if child_qty > 0:
                    walk(child_code, missing * child_qty, (*path, key), f"Półprodukt {code}")

            material = semi.get('surowiec') if isinstance(semi.get('surowiec'), dict) else {}
            material_code = str(material.get('kod') or material.get('symbol') or material.get('typ') or '').strip()
            if material_code:
                try:
                    per_piece = _number(material.get('ilosc_na_szt', material.get('ilosc', material.get('dlugosc'))))
                except (TypeError, ValueError):
                    warnings.append(f"Półprodukt '{code}' ma nieprawidłową ilość surowca '{material_code}'.")
                else:
                    if per_piece > 0:
                        try:
                            loss = max(0.0, _number(semi.get('norma_strat_proc'), 0.0))
                        except (TypeError, ValueError):
                            loss = 0.0
                        unit = str(material.get('jednostka') or '').strip()
                        raw_key = (material_code.casefold(), unit.casefold())
                        raw_bucket = raw_totals.setdefault(raw_key, {
                            'kod': material_code,
                            'nazwa': str(material.get('nazwa') or ''),
                            'ilosc': 0.0,
                            'jednostka': unit,
                            'zrodla': set(),
                        })
                        raw_bucket['ilosc'] += missing * per_piece * (1.0 + loss / 100.0)
                        raw_bucket['zrodla'].add(str(code))
            elif not nested:
                warnings.append(f"Półprodukt '{code}' nie ma surowca ani własnego składu.")

        for entry in roots:
            if not isinstance(entry, dict):
                continue
            child = _entry_code(entry)
            if not child:
                warnings.append('Pominięto pozycję składu bez kodu półproduktu.')
                continue
            try:
                child_qty = _entry_qty(entry)
            except (TypeError, ValueError):
                warnings.append(f"Półprodukt '{child}' ma nieprawidłową ilość.")
                continue
            if child_qty <= 0:
                continue
            walk(child, child_qty, (), f"Produkt {product_code}", child.casefold() in root_ignore_stock)

        rows = []
        for item in sorted(semi_totals.values(), key=lambda x: str(x['kod']).casefold()):
            stock_item = stock.get(str(item['kod']).casefold(), {})
            rows.append({
                'typ': 'Półprodukt',
                'kod': item['kod'],
                'nazwa': item.get('nazwa', ''),
                'ilosc': item['ilosc'],
                'jednostka': 'szt.',
                'stan': float(stock_item.get('stan', 0) or 0),
                'wolne': float(stock_item.get('wolne', 0) or 0),
                'z_magazynu': item['z_magazynu'],
                'brak': item['do_wykonania'],
                'zrodlo': ', '.join(sorted(item.get('zrodla') or [])),
            })

        for item in sorted(raw_totals.values(), key=lambda x: (str(x['kod']).casefold(), str(x['jednostka']).casefold())):
            stock_item = stock.get(str(item['kod']).casefold(), {}) if use_stock else {}
            available = float(stock_item.get('wolne', 0) or 0)
            stock_unit = str(stock_item.get('jednostka') or '').strip()
            req_unit = str(item.get('jednostka') or '').strip()
            if use_stock and available > 0 and stock_unit and req_unit and stock_unit.casefold() != req_unit.casefold():
                warnings.append(f"Surowiec '{item['kod']}' ma w Magazynie jednostkę '{stock_unit}', a skład wymaga '{req_unit}'.")
                available = 0.0
            taken = min(float(item['ilosc']), available) if use_stock else 0.0
            rows.append({
                'typ': 'Surowiec',
                'kod': item['kod'],
                'nazwa': item.get('nazwa', '') or str(stock_item.get('nazwa') or ''),
                'ilosc': item['ilosc'],
                'jednostka': req_unit or stock_unit,
                'stan': float(stock_item.get('stan', 0) or 0),
                'wolne': float(stock_item.get('wolne', 0) or 0),
                'z_magazynu': taken,
                'brak': max(0.0, float(item['ilosc']) - taken),
                'zrodlo': ', '.join(sorted(item.get('zrodla') or [])),
            })

        return {
            'product_code': product_code,
            'product_name': product_name,
            'product_qty': product_qty,
            'composition_revision': revision,
            'rows': rows,
            'warnings': warnings,
            'warehouse_checked': bool(use_stock),
        }
'''
Path("planowanie_zapotrzebowanie.py").write_text(requirements_engine, encoding="utf-8")


# ---------------------------------------------------------------------
# gui_planowanie.py
# ---------------------------------------------------------------------
plan_path = Path("gui_planowanie.py")
plan = plan_path.read_text(encoding="utf-8")
plan = replace_once(plan, "# version: 1.4\n", "# version: 1.5\n", "planning version")
plan = replace_once(
    plan,
    "# =========================================================\n# Zmiany 1.4:\n",
    "# =========================================================\n"
    "# Zmiany 1.5:\n"
    "# - Zapotrzebowanie zlecenia porównuje półprodukty i surowce z istniejącym Magazynem.\n"
    "# - Naddatek półproduktu zmniejsza ilość do wykonania przed liczeniem surowców.\n"
    "# - Podgląd pokazuje stan, wolne, wykorzystanie z magazynu i brak/do wykonania.\n"
    "# Zmiany 1.4:\n",
    "planning changelog",
)
plan = replace_once(
    plan,
    "        req_cols = (\"typ\", \"kod\", \"nazwa\", \"ilosc\", \"jednostka\", \"zrodlo\")\n",
    "        req_cols = (\"typ\", \"kod\", \"nazwa\", \"ilosc\", \"jednostka\", \"stan\", \"wolne\", \"z_magazynu\", \"brak\", \"zrodlo\")\n",
    "planning requirement columns",
)
plan = replace_once(
    plan,
    "            (\"typ\", \"Typ\", 90), (\"kod\", \"Kod\", 150), (\"nazwa\", \"Nazwa\", 180),\n            (\"ilosc\", \"Potrzeba\", 100), (\"jednostka\", \"Jedn.\", 70), (\"zrodlo\", \"Wynika z\", 260),\n",
    "            (\"typ\", \"Typ\", 90), (\"kod\", \"Kod\", 140), (\"nazwa\", \"Nazwa\", 160),\n"
    "            (\"ilosc\", \"Potrzeba\", 90), (\"jednostka\", \"Jedn.\", 60), (\"stan\", \"Stan\", 80),\n"
    "            (\"wolne\", \"Wolne\", 80), (\"z_magazynu\", \"Z magazynu\", 95), (\"brak\", \"Brak / do wyk.\", 105),\n"
    "            (\"zrodlo\", \"Wynika z\", 220),\n",
    "planning requirement headings",
)
plan = replace_once(
    plan,
    "            result = self.requirement_calculator.calculate(product_code, qty)\n",
    "            result = self.requirement_calculator.calculate_with_stock(product_code, qty)\n",
    "planning stock calculate",
)
plan = replace_once(
    plan,
    "                row.get(\"typ\", \"\"), row.get(\"kod\", \"\"), row.get(\"nazwa\", \"\"),\n                self._format_requirement_qty(row.get(\"ilosc\")), row.get(\"jednostka\", \"\"), row.get(\"zrodlo\", \"\"),\n",
    "                row.get(\"typ\", \"\"), row.get(\"kod\", \"\"), row.get(\"nazwa\", \"\"),\n"
    "                self._format_requirement_qty(row.get(\"ilosc\")), row.get(\"jednostka\", \"\"),\n"
    "                self._format_requirement_qty(row.get(\"stan\")), self._format_requirement_qty(row.get(\"wolne\")),\n"
    "                self._format_requirement_qty(row.get(\"z_magazynu\")), self._format_requirement_qty(row.get(\"brak\")),\n"
    "                row.get(\"zrodlo\", \"\"),\n",
    "planning requirement row values",
)
plan = replace_once(
    plan,
    "            f\"| rewizja składu {result.get('composition_revision', 1)}\"\n",
    "            f\"| rewizja składu {result.get('composition_revision', 1)} | Magazyn: sprawdzony\"\n",
    "planning status warehouse",
)
plan_path.write_text(plan, encoding="utf-8")

print('U2A-4 foundation patch prepared')
