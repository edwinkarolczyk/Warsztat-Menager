# version: 1.2
# Moduł: planowanie_zapotrzebowanie
# U2A-3: wyliczanie zapotrzebowania bez ruchów magazynowych i bez Dyspozycji.
# Zmiany 1.1:
# - Zapotrzebowanie może uwzględniać wolne stany istniejącego Magazynu.
# - Naddatek półproduktu jest wykorzystywany przed rozwinięciem go do niższych poziomów i surowców.
# - Obsługa wielopoziomowego składu półproduktu oraz agregacji surowców.
# Zmiany 1.2:
# - Kalkulator może dostać kontrolowany snapshot Magazynu do rozliczenia własnych rezerwacji Dyspozycji.

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

    def calculate_with_stock(
        self, product_code: str, product_qty: int | float, *, stock_snapshot: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        return self._calculate_product(product_code, product_qty, use_stock=True, stock_snapshot=stock_snapshot)

    def calculate_semi_with_stock(
        self, semi_code: str, qty: int | float, *, ignore_root_stock: bool = True,
        stock_snapshot: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
            stock_snapshot=stock_snapshot,
        )

    def _calculate_product(
        self, product_code: str, product_qty: int | float, *, use_stock: bool,
        stock_snapshot: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
            stock_snapshot=stock_snapshot,
        )

    def _calculate_from_roots(
        self, *, roots, product_code, product_name, product_qty, revision, semi_map, use_stock, root_ignore_stock,
        stock_snapshot: dict[str, dict[str, Any]] | None = None,
    ):
        try:
            if use_stock and stock_snapshot is not None:
                stock = {str(key): dict(value) for key, value in stock_snapshot.items() if isinstance(value, dict)}
            else:
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
