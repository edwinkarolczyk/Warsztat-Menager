from pathlib import Path

PLAN = Path('gui_planowanie.py')
PRODUCTS = Path('produkty_store.py')
SEMI = Path('polprodukty_store.py')
BOMGUI = Path('gui_planowanie_bom.py')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1 match, got {n}')
    return text.replace(old, new, 1)

semi_content = r'''# version: 1.0
# Moduł: polprodukty_store
# U2A-2: jedno źródło półproduktów w aktywnym WM_DATA_ROOT/polprodukty.

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from config_manager import ConfigManager


class SemiProductCatalogError(RuntimeError):
    pass


class SemiProductCatalog:
    _FORBIDDEN_FILENAME_CHARS = set('<>:"/\\|?*')

    def __init__(self, cfg: ConfigManager | None = None) -> None:
        self.cfg = cfg or ConfigManager()
        self.data_dir = Path(self.cfg.path_data('polprodukty'))
        self.backup_dir = Path(self.cfg.path_backup('polprodukty'))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            with path.open('r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _filename_for_code(cls, code: str) -> str:
        value = str(code or '').strip()
        if not value:
            raise SemiProductCatalogError('Kod półproduktu jest wymagany.')
        if value in {'.', '..'} or value.endswith((' ', '.')):
            raise SemiProductCatalogError('Nieprawidłowy kod półproduktu.')
        if any(ord(ch) < 32 or ch in cls._FORBIDDEN_FILENAME_CHARS for ch in value):
            raise SemiProductCatalogError('Kod zawiera znak niedozwolony w nazwie pliku Windows.')
        return f'{value}.json'

    @staticmethod
    def _normalise(raw: dict[str, Any], path: Path) -> dict[str, Any]:
        code = str(raw.get('kod') or raw.get('id') or path.stem).strip()
        name = str(raw.get('nazwa') or raw.get('name') or code).strip()
        material = raw.get('surowiec') if isinstance(raw.get('surowiec'), dict) else {}
        ops = raw.get('czynnosci') or raw.get('operacje') or []
        if not isinstance(ops, list):
            ops = []
        loss = raw.get('norma_strat_proc', raw.get('norma_strat_procent', 0))
        try:
            loss = float(loss or 0)
        except (TypeError, ValueError):
            loss = 0.0
        return {
            'kod': code,
            'nazwa': name,
            'czynnosci': [str(x) for x in ops if str(x).strip()],
            'surowiec': dict(material),
            'norma_strat_proc': loss,
            '_path': str(path),
            '_legacy_id': 'kod' not in raw and 'id' in raw,
            '_raw': raw,
        }

    def list_items(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.data_dir.glob('*.json'), key=lambda p: p.name.lower()):
            raw = self._read_json(path)
            if raw is None:
                continue
            item = self._normalise(raw, path)
            if item.get('kod'):
                out.append(item)
        return out

    def get(self, code: str) -> dict[str, Any] | None:
        wanted = str(code or '').strip().casefold()
        for item in self.list_items():
            if str(item.get('kod') or '').casefold() == wanted:
                return item
        return None

    def _backup(self, path: Path) -> None:
        if not path.exists():
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        shutil.copy2(path, self.backup_dir / f'{path.stem}_{stamp}{path.suffix}')

    def save(self, fields: dict[str, Any], *, original_path: str | Path | None = None) -> dict[str, Any]:
        code = str(fields.get('kod') or '').strip()
        name = str(fields.get('nazwa') or '').strip()
        if not name:
            raise SemiProductCatalogError('Nazwa półproduktu jest wymagana.')
        filename = self._filename_for_code(code)
        target = self.data_dir / filename
        source = Path(original_path) if original_path else None
        try:
            target_resolved = target.resolve()
        except Exception:
            target_resolved = target
        try:
            source_resolved = source.resolve() if source else None
        except Exception:
            source_resolved = source
        if target.exists() and (source is None or source_resolved != target_resolved):
            raise SemiProductCatalogError(f"Półprodukt o kodzie '{code}' już istnieje.")

        raw = self._read_json(source) if source and source.exists() else {}
        payload = dict(raw or {})
        payload['kod'] = code
        if 'id' in payload:
            payload['id'] = code
        payload['nazwa'] = name

        material_code = str(fields.get('material_kod') or '').strip()
        material_qty_raw = fields.get('material_ilosc', '')
        material_unit = str(fields.get('material_jednostka') or '').strip()
        if material_code or str(material_qty_raw).strip() or material_unit:
            if not material_code:
                raise SemiProductCatalogError('Podaj kod materiału albo wyczyść całą sekcję materiału.')
            try:
                material_qty = float(material_qty_raw)
            except (TypeError, ValueError):
                raise SemiProductCatalogError('Ilość materiału na sztukę musi być liczbą.') from None
            if material_qty <= 0:
                raise SemiProductCatalogError('Ilość materiału na sztukę musi być większa od zera.')
            if not material_unit:
                raise SemiProductCatalogError('Jednostka materiału jest wymagana.')
            payload['surowiec'] = {
                'kod': material_code,
                'ilosc_na_szt': material_qty,
                'jednostka': material_unit,
            }
        elif 'surowiec' in payload:
            payload['surowiec'] = {}

        ops = fields.get('czynnosci') or []
        if isinstance(ops, str):
            ops = [x.strip() for x in ops.split(',') if x.strip()]
        payload['czynnosci'] = [str(x).strip() for x in ops if str(x).strip()]
        if 'operacje' in payload:
            payload['operacje'] = list(payload['czynnosci'])

        try:
            loss = float(fields.get('norma_strat_proc') or 0)
        except (TypeError, ValueError):
            raise SemiProductCatalogError('Norma strat musi być liczbą.') from None
        if loss < 0:
            raise SemiProductCatalogError('Norma strat nie może być ujemna.')
        payload['norma_strat_proc'] = loss
        if 'norma_strat_procent' in payload:
            payload['norma_strat_procent'] = loss

        if source and source.exists():
            self._backup(source)
        tmp = target.with_suffix(target.suffix + '.tmp')
        try:
            with tmp.open('w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

        if source and source.exists():
            try:
                same = source.resolve() == target.resolve()
            except Exception:
                same = source == target
            if not same:
                source.unlink()
        return self._normalise(payload, target)

    def delete(self, item: dict[str, Any]) -> None:
        raw_path = item.get('_path')
        if not raw_path:
            raise SemiProductCatalogError('Nie można ustalić pliku półproduktu.')
        path = Path(str(raw_path))
        if not path.exists():
            raise SemiProductCatalogError('Plik półproduktu już nie istnieje.')
        self._backup(path)
        path.unlink()
'''

bom_gui_content = r'''# version: 1.0
# Moduł: gui_planowanie_bom
# U2A-2: Półprodukty i edytor BOM w Planowaniu.

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from polprodukty_store import SemiProductCatalog, SemiProductCatalogError
from produkty_store import ProductCatalog, ProductCatalogError


class SemiProductsPanel(ttk.Frame):
    def __init__(self, master, *, product_catalog: ProductCatalog, can_manage: bool = False):
        super().__init__(master)
        self.product_catalog = product_catalog
        self.catalog = SemiProductCatalog()
        self.can_manage = bool(can_manage)
        self.search_var = tk.StringVar(value='')
        self.rows: dict[str, dict] = {}
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=8)
        ttk.Label(top, text='Szukaj:').pack(side='left')
        ent = ttk.Entry(top, textvariable=self.search_var)
        ent.pack(side='left', fill='x', expand=True, padx=6)
        ent.bind('<KeyRelease>', lambda _e: self.refresh())
        ttk.Button(top, text='Odśwież', command=self.refresh).pack(side='right')
        if self.can_manage:
            ttk.Button(top, text='Usuń', command=self._delete).pack(side='right', padx=3)
            ttk.Button(top, text='Edytuj', command=self._edit).pack(side='right', padx=3)
            ttk.Button(top, text='Dodaj', command=self._add).pack(side='right', padx=3)

        cols = ('kod', 'nazwa', 'material', 'ilosc', 'jednostka', 'strata', 'czynnosci')
        self.tree = ttk.Treeview(self, columns=cols, show='headings', height=17)
        for key, label, width in (
            ('kod', 'Kod', 170), ('nazwa', 'Nazwa', 260), ('material', 'Materiał', 150),
            ('ilosc', 'Na szt.', 80), ('jednostka', 'Jedn.', 70), ('strata', 'Strata %', 75),
            ('czynnosci', 'Czynności', 260),
        ):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.tree.bind('<Double-1>', lambda _e: self._edit())

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        query = self.search_var.get().strip().casefold()
        try:
            items = self.catalog.list_items()
        except Exception as exc:
            messagebox.showerror('Półprodukty', f'Nie udało się wczytać półproduktów:\n{exc}', parent=self)
            return
        items.sort(key=lambda x: str(x.get('kod') or '').casefold())
        for idx, item in enumerate(items):
            blob = f"{item.get('kod','')} {item.get('nazwa','')}".casefold()
            if query and query not in blob:
                continue
            mat = item.get('surowiec') if isinstance(item.get('surowiec'), dict) else {}
            iid = f'pp-{idx}'
            self.rows[iid] = item
            self.tree.insert('', 'end', iid=iid, values=(
                item.get('kod', ''), item.get('nazwa', ''), mat.get('kod', ''),
                mat.get('ilosc_na_szt', ''), mat.get('jednostka', ''),
                item.get('norma_strat_proc', 0), ', '.join(item.get('czynnosci') or []),
            ))

    def _selected(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def _add(self):
        if self.can_manage:
            self._form(None)

    def _edit(self):
        if not self.can_manage:
            return
        item = self._selected()
        if item:
            self._form(item)

    def _form(self, item):
        values = item or {}
        mat = values.get('surowiec') if isinstance(values.get('surowiec'), dict) else {}
        win = tk.Toplevel(self)
        win.title('Półprodukt' if item else 'Nowy półprodukt')
        win.transient(self.winfo_toplevel())
        win.grab_set()
        form = ttk.Frame(win, padding=12)
        form.pack(fill='both', expand=True)
        form.columnconfigure(1, weight=1)

        vars_ = {
            'kod': tk.StringVar(value=str(values.get('kod') or '')),
            'nazwa': tk.StringVar(value=str(values.get('nazwa') or '')),
            'material_kod': tk.StringVar(value=str(mat.get('kod') or '')),
            'material_ilosc': tk.StringVar(value=str(mat.get('ilosc_na_szt') or '')),
            'material_jednostka': tk.StringVar(value=str(mat.get('jednostka') or '')),
            'norma_strat_proc': tk.StringVar(value=str(values.get('norma_strat_proc') or 0)),
            'czynnosci': tk.StringVar(value=', '.join(values.get('czynnosci') or [])),
        }
        labels = (
            ('Kod półproduktu:', 'kod'), ('Nazwa:', 'nazwa'), ('Kod materiału:', 'material_kod'),
            ('Ilość materiału na szt.:', 'material_ilosc'), ('Jednostka:', 'material_jednostka'),
            ('Norma strat [%]:', 'norma_strat_proc'), ('Czynności (po przecinku):', 'czynnosci'),
        )
        for row, (label, key) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=4)
            ttk.Entry(form, textvariable=vars_[key], width=52).grid(row=row, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Rodzaje, jednostki i czynności są danymi edytowalnymi — nic nie jest wpisane na sztywno.', wraplength=560).grid(
            row=7, column=0, columnspan=2, sticky='w', pady=(6, 10)
        )

        def save():
            payload = {key: var.get() for key, var in vars_.items()}
            try:
                self.catalog.save(payload, original_path=(values.get('_path') if item else None))
            except SemiProductCatalogError as exc:
                messagebox.showerror('Półprodukt', str(exc), parent=win)
                return
            except Exception as exc:
                messagebox.showerror('Półprodukt', f'Nie udało się zapisać:\n{exc}', parent=win)
                return
            win.destroy()
            self.refresh()

        btns = ttk.Frame(form)
        btns.grid(row=8, column=0, columnspan=2, sticky='e')
        ttk.Button(btns, text='Anuluj', command=win.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(btns, text='Zapisz', command=save).pack(side='right')

    def _delete(self):
        item = self._selected()
        if not item:
            return
        code = str(item.get('kod') or '')
        used_by = []
        try:
            for product in self.product_catalog.list_products():
                if any(str(row.get('kod') or '') == code for row in (product.get('polprodukty') or [])):
                    used_by.append(str(product.get('kod') or ''))
        except Exception:
            pass
        if used_by:
            messagebox.showerror('Półprodukt', 'Nie można usunąć — półprodukt jest używany w BOM: ' + ', '.join(used_by[:12]), parent=self)
            return
        if not messagebox.askyesno('Usuń półprodukt', f"Usunąć '{code}'?\nPrzed usunięciem zostanie wykonana kopia.", parent=self):
            return
        try:
            self.catalog.delete(item)
        except SemiProductCatalogError as exc:
            messagebox.showerror('Półprodukt', str(exc), parent=self)
            return
        self.refresh()


class BomEditorPanel(ttk.Frame):
    def __init__(self, master, *, product_catalog: ProductCatalog, semi_catalog: SemiProductCatalog, can_manage: bool = False):
        super().__init__(master)
        self.product_catalog = product_catalog
        self.semi_catalog = semi_catalog
        self.can_manage = bool(can_manage)
        self.product_var = tk.StringVar(value='')
        self.status_var = tk.StringVar(value='Wybierz produkt.')
        self.products_by_label: dict[str, dict] = {}
        self.entries: list[dict] = []
        self.current_product: dict | None = None
        self.dirty = False
        self._build()
        self.refresh_products()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=8)
        ttk.Label(top, text='Produkt:').pack(side='left')
        self.product_cb = ttk.Combobox(top, textvariable=self.product_var, state='readonly', width=48)
        self.product_cb.pack(side='left', padx=6)
        self.product_cb.bind('<<ComboboxSelected>>', self._on_product_selected)
        ttk.Button(top, text='Odśwież', command=self.refresh_products).pack(side='left', padx=3)
        if self.can_manage:
            ttk.Button(top, text='Zapisz BOM', command=self._save_bom).pack(side='right')
            ttk.Button(top, text='Usuń pozycję', command=self._remove_entry).pack(side='right', padx=3)
            ttk.Button(top, text='Edytuj pozycję', command=self._edit_entry).pack(side='right', padx=3)
            ttk.Button(top, text='Dodaj pozycję', command=self._add_entry).pack(side='right', padx=3)

        cols = ('pp', 'nazwa', 'ilosc', 'material', 'czynnosci')
        self.tree = ttk.Treeview(self, columns=cols, show='headings', height=17)
        for key, label, width in (
            ('pp', 'Półprodukt', 180), ('nazwa', 'Nazwa', 260), ('ilosc', 'Ilość na produkt', 110),
            ('material', 'Materiał z półproduktu', 220), ('czynnosci', 'Czynności', 280),
        ):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        self.tree.bind('<Double-1>', lambda _e: self._edit_entry())
        ttk.Label(self, textvariable=self.status_var).pack(anchor='w', padx=8, pady=(0, 8))

    def refresh_products(self):
        if self.dirty and not messagebox.askyesno('BOM', 'Masz niezapisane zmiany BOM. Odrzucić je?', parent=self):
            return
        old_code = str((self.current_product or {}).get('kod') or '')
        self.products_by_label = {}
        labels = []
        try:
            products = self.product_catalog.list_products()
        except Exception as exc:
            messagebox.showerror('BOM', f'Nie udało się wczytać produktów:\n{exc}', parent=self)
            return
        for product in sorted(products, key=lambda p: str(p.get('kod') or '').casefold()):
            label = f"{product.get('kod','')} — {product.get('nazwa','')}"
            labels.append(label)
            self.products_by_label[label] = product
        self.product_cb.configure(values=labels)
        chosen = next((label for label, p in self.products_by_label.items() if str(p.get('kod') or '') == old_code), '')
        if chosen:
            self.product_var.set(chosen)
            self._load_product(self.products_by_label[chosen])
        elif labels:
            self.product_var.set(labels[0])
            self._load_product(self.products_by_label[labels[0]])
        else:
            self.product_var.set('')
            self.current_product = None
            self.entries = []
            self._render()
            self.status_var.set('Brak produktów.')

    def _on_product_selected(self, _event=None):
        selected = self.products_by_label.get(self.product_var.get())
        if not selected:
            return
        if self.dirty and not messagebox.askyesno('BOM', 'Masz niezapisane zmiany BOM. Odrzucić je i przejść do innego produktu?', parent=self):
            current_code = str((self.current_product or {}).get('kod') or '')
            label = next((lbl for lbl, p in self.products_by_label.items() if str(p.get('kod') or '') == current_code), '')
            self.product_var.set(label)
            return
        self._load_product(selected)

    def _load_product(self, product):
        self.current_product = product
        self.entries = copy.deepcopy(product.get('polprodukty') or [])
        self.dirty = False
        self._render()
        self.status_var.set(f"BOM produktu {product.get('kod','')} | rewizja {product.get('bom_revision', 1)}")

    def _semi_map(self):
        try:
            return {str(x.get('kod') or ''): x for x in self.semi_catalog.list_items()}
        except Exception:
            return {}

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        semi = self._semi_map()
        for idx, entry in enumerate(self.entries):
            code = str(entry.get('kod') or entry.get('id') or entry.get('symbol') or '')
            pp = semi.get(code, {})
            mat = pp.get('surowiec') if isinstance(pp.get('surowiec'), dict) else {}
            material_txt = ''
            if mat:
                material_txt = f"{mat.get('kod','')} {mat.get('ilosc_na_szt','')} {mat.get('jednostka','')}".strip()
            elif isinstance(entry.get('surowiec'), dict):
                old_mat = entry.get('surowiec') or {}
                material_txt = f"{old_mat.get('kod') or old_mat.get('typ') or ''} {old_mat.get('dlugosc') or old_mat.get('ilosc_na_szt') or ''}".strip()
            qty = entry.get('ilosc_na_szt', entry.get('ilosc_na_sztuke', entry.get('ilosc', 1)))
            ops = entry.get('czynnosci') if isinstance(entry.get('czynnosci'), list) else pp.get('czynnosci', [])
            self.tree.insert('', 'end', iid=f'bom-{idx}', values=(code, pp.get('nazwa', ''), qty, material_txt, ', '.join(ops or [])))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0].split('-', 1)[1])
        except Exception:
            return None

    def _add_entry(self):
        if self.can_manage and self.current_product:
            self._entry_form(None)

    def _edit_entry(self):
        if not self.can_manage:
            return
        idx = self._selected_index()
        if idx is not None and 0 <= idx < len(self.entries):
            self._entry_form(idx)

    def _entry_form(self, idx):
        existing = self.entries[idx] if idx is not None else {}
        semi_items = self.semi_catalog.list_items()
        semi_codes = [str(x.get('kod') or '') for x in semi_items]
        current_code = str(existing.get('kod') or existing.get('id') or existing.get('symbol') or '')
        if current_code and current_code not in semi_codes:
            semi_codes.append(current_code)
        win = tk.Toplevel(self)
        win.title('Pozycja BOM')
        win.transient(self.winfo_toplevel())
        win.grab_set()
        form = ttk.Frame(win, padding=12)
        form.pack(fill='both', expand=True)
        code_var = tk.StringVar(value=current_code)
        qty_val = existing.get('ilosc_na_szt', existing.get('ilosc_na_sztuke', existing.get('ilosc', 1)))
        qty_var = tk.StringVar(value=str(qty_val or 1))
        ops_var = tk.StringVar(value=', '.join(existing.get('czynnosci') or []))
        ttk.Label(form, text='Półprodukt:').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Combobox(form, textvariable=code_var, values=semi_codes, state='normal', width=42).grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Ilość na produkt:').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=qty_var).grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Czynności BOM (opcjonalne):').grid(row=2, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=ops_var).grid(row=2, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='Materiał nie jest kopiowany do BOM — pochodzi z definicji półproduktu.', wraplength=520).grid(row=3, column=0, columnspan=2, sticky='w', pady=(6, 10))
        form.columnconfigure(1, weight=1)

        def accept():
            code = code_var.get().strip()
            if not code:
                messagebox.showerror('BOM', 'Wybierz lub wpisz kod półproduktu.', parent=win)
                return
            try:
                qty = float(qty_var.get())
            except ValueError:
                messagebox.showerror('BOM', 'Ilość musi być liczbą.', parent=win)
                return
            if qty <= 0:
                messagebox.showerror('BOM', 'Ilość musi być większa od zera.', parent=win)
                return
            if qty.is_integer():
                qty = int(qty)
            row = dict(existing)
            row['kod'] = code
            row['ilosc_na_szt'] = qty
            row.pop('ilosc_na_sztuke', None)
            row.pop('ilosc', None)
            ops = [x.strip() for x in ops_var.get().split(',') if x.strip()]
            if ops:
                row['czynnosci'] = ops
            elif 'czynnosci' in row:
                row['czynnosci'] = []
            # Canonical BOM does not duplicate material. Old material is kept only
            # for legacy entries until the row is explicitly edited.
            row.pop('surowiec', None)
            if idx is None:
                self.entries.append(row)
            else:
                self.entries[idx] = row
            self.dirty = True
            self._render()
            self.status_var.set('Niezapisane zmiany BOM.')
            win.destroy()

        btns = ttk.Frame(form)
        btns.grid(row=4, column=0, columnspan=2, sticky='e')
        ttk.Button(btns, text='Anuluj', command=win.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(btns, text='OK', command=accept).pack(side='right')

    def _remove_entry(self):
        idx = self._selected_index()
        if idx is None or not self.can_manage:
            return
        del self.entries[idx]
        self.dirty = True
        self._render()
        self.status_var.set('Niezapisane zmiany BOM.')

    def _save_bom(self):
        if not self.current_product or not self.can_manage:
            return
        if not self.dirty:
            self.status_var.set('Brak zmian do zapisania.')
            return
        try:
            saved = self.product_catalog.save_bom(self.current_product, self.entries)
        except ProductCatalogError as exc:
            messagebox.showerror('BOM', str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror('BOM', f'Nie udało się zapisać BOM:\n{exc}', parent=self)
            return
        self.current_product = saved
        self.entries = copy.deepcopy(saved.get('polprodukty') or [])
        self.dirty = False
        self._render()
        self.status_var.set(f"Zapisano BOM | rewizja {saved.get('bom_revision', 1)}")
'''

if SEMI.exists() or BOMGUI.exists():
    raise RuntimeError('U2A-2 target new files already exist; aborting')
SEMI.write_text(semi_content, encoding='utf-8')
BOMGUI.write_text(bom_gui_content, encoding='utf-8')

# Extend product store with canonical BOM save.
p = PRODUCTS.read_text(encoding='utf-8')
p = replace_once(p, '# version: 1.0\n', '# version: 1.1\n# U2A-2: zapis kanonicznego BOM produktu z kopią bezpieczeństwa i automatyczną rewizją.\n', 'product store version')
insert_before = '''    def delete_product(self, product: dict[str, Any]) -> None:\n'''
method = r'''    def save_bom(self, product: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
        raw_path = product.get('_path')
        if not raw_path:
            raise ProductCatalogError('Nie można ustalić pliku produktu.')
        path = Path(str(raw_path))
        if not path.exists():
            raise ProductCatalogError('Plik produktu już nie istnieje.')
        raw = self._read_json(path)
        if raw is None:
            raise ProductCatalogError('Nie można odczytać pliku produktu.')

        clean_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get('kod') or entry.get('id') or entry.get('symbol') or '').strip()
            if not code:
                raise ProductCatalogError('Każda pozycja BOM musi mieć kod półproduktu.')
            qty_raw = entry.get('ilosc_na_szt', entry.get('ilosc_na_sztuke', entry.get('ilosc', 1)))
            try:
                qty = float(qty_raw)
            except (TypeError, ValueError):
                raise ProductCatalogError(f"Nieprawidłowa ilość BOM dla '{code}'.") from None
            if qty <= 0:
                raise ProductCatalogError(f"Ilość BOM dla '{code}' musi być większa od zera.")
            if qty.is_integer():
                qty = int(qty)
            row = dict(entry)
            row['kod'] = code
            row['ilosc_na_szt'] = qty
            row.pop('id', None)
            row.pop('symbol', None)
            row.pop('ilosc_na_sztuke', None)
            row.pop('ilosc', None)
            clean_entries.append(row)

        payload = dict(raw)
        payload['polprodukty'] = clean_entries
        try:
            current_revision = int(payload.get('bom_revision') or 0)
        except (TypeError, ValueError):
            current_revision = 0
        payload['bom_revision'] = max(0, current_revision) + 1

        # Keep legacy alternate representations in sync when they already exist.
        if isinstance(payload.get('bom'), dict):
            payload['bom'] = {row['kod']: row['ilosc_na_szt'] for row in clean_entries}
        if isinstance(payload.get('BOM'), list):
            payload['BOM'] = [
                {'typ': 'polprodukt', 'kod': row['kod'], 'ilosc_na_sztuke': row['ilosc_na_szt']}
                for row in clean_entries
            ]

        self._backup(path)
        tmp = path.with_suffix(path.suffix + '.tmp')
        try:
            with tmp.open('w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        return self._normalise(payload, path)

'''
p = replace_once(p, insert_before, method + insert_before, 'save_bom method')
PRODUCTS.write_text(p, encoding='utf-8')

# Add tabs to planning with minimal changes.
s = PLAN.read_text(encoding='utf-8')
s = replace_once(
    s,
    '# version: 1.1\n# =========================================================\n# Zmiany 1.1:\n',
    '# version: 1.2\n# =========================================================\n# Zmiany 1.2:\n# - U2A-2: dodano Półprodukty i edytor BOM w Planowaniu.\n# - BOM odwołuje się do półproduktów zamiast dublować definicję materiału.\n# Zmiany 1.1:\n',
    'planning version',
)
s = replace_once(
    s,
    'from produkty_store import ProductCatalog, ProductCatalogError\n',
    'from produkty_store import ProductCatalog, ProductCatalogError\nfrom gui_planowanie_bom import BomEditorPanel, SemiProductsPanel\n',
    'planning imports',
)
old_tabs = '''        tab_cal = ttk.Frame(notebook)\n        tab_ord = ttk.Frame(notebook)\n        tab_prod = ttk.Frame(notebook)\n        notebook.add(tab_cal, text="KALENDARZ")\n        notebook.add(tab_ord, text="ZLECENIA")\n        notebook.add(tab_prod, text="PRODUKTY")\n        self._build_calendar_tab(tab_cal)\n        self._build_orders_tab(tab_ord)\n        self._build_products_tab(tab_prod)\n'''
new_tabs = '''        tab_cal = ttk.Frame(notebook)\n        tab_ord = ttk.Frame(notebook)\n        tab_prod = ttk.Frame(notebook)\n        tab_semi = ttk.Frame(notebook)\n        tab_bom = ttk.Frame(notebook)\n        notebook.add(tab_cal, text="KALENDARZ")\n        notebook.add(tab_ord, text="ZLECENIA")\n        notebook.add(tab_prod, text="PRODUKTY")\n        notebook.add(tab_semi, text="PÓŁPRODUKTY")\n        notebook.add(tab_bom, text="BOM")\n        self._build_calendar_tab(tab_cal)\n        self._build_orders_tab(tab_ord)\n        self._build_products_tab(tab_prod)\n        self.semi_products_panel = SemiProductsPanel(\n            tab_semi, product_catalog=self.product_catalog, can_manage=self.can_manage_products\n        )\n        self.semi_products_panel.pack(fill="both", expand=True)\n        self.bom_panel = BomEditorPanel(\n            tab_bom,\n            product_catalog=self.product_catalog,\n            semi_catalog=self.semi_products_panel.catalog,\n            can_manage=self.can_manage_products,\n        )\n        self.bom_panel.pack(fill="both", expand=True)\n'''
s = replace_once(s, old_tabs, new_tabs, 'planning tabs')
PLAN.write_text(s, encoding='utf-8')

print('U2A-2 patch prepared')
