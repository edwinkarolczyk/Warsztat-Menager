from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------
# planowanie_zapotrzebowanie.py - allow caller-owned stock snapshot
# ---------------------------------------------------------------------
req_path = Path('planowanie_zapotrzebowanie.py')
req = req_path.read_text(encoding='utf-8')
req = replace_once(req, '# version: 1.1\n', '# version: 1.2\n', 'requirements version')
req = replace_once(
    req,
    '# - Obsługa wielopoziomowego składu półproduktu oraz agregacji surowców.\n',
    '# - Obsługa wielopoziomowego składu półproduktu oraz agregacji surowców.\n'
    '# Zmiany 1.2:\n'
    '# - Kalkulator może dostać kontrolowany snapshot Magazynu do rozliczenia własnych rezerwacji Dyspozycji.\n',
    'requirements changelog',
)
req = replace_once(
    req,
    "    def calculate_with_stock(self, product_code: str, product_qty: int | float) -> dict[str, Any]:\n        return self._calculate_product(product_code, product_qty, use_stock=True)\n",
    "    def calculate_with_stock(\n"
    "        self, product_code: str, product_qty: int | float, *, stock_snapshot: dict[str, dict[str, Any]] | None = None\n"
    "    ) -> dict[str, Any]:\n"
    "        return self._calculate_product(product_code, product_qty, use_stock=True, stock_snapshot=stock_snapshot)\n",
    'requirements calculate_with_stock',
)
req = replace_once(
    req,
    "    def calculate_semi_with_stock(self, semi_code: str, qty: int | float, *, ignore_root_stock: bool = True) -> dict[str, Any]:\n",
    "    def calculate_semi_with_stock(\n"
    "        self, semi_code: str, qty: int | float, *, ignore_root_stock: bool = True,\n"
    "        stock_snapshot: dict[str, dict[str, Any]] | None = None,\n"
    "    ) -> dict[str, Any]:\n",
    'requirements semi signature',
)
req = replace_once(
    req,
    "            use_stock=True,\n            root_ignore_stock={code.casefold()} if ignore_root_stock else set(),\n        )\n\n    def _calculate_product(self, product_code: str, product_qty: int | float, *, use_stock: bool) -> dict[str, Any]:\n",
    "            use_stock=True,\n"
    "            root_ignore_stock={code.casefold()} if ignore_root_stock else set(),\n"
    "            stock_snapshot=stock_snapshot,\n"
    "        )\n\n"
    "    def _calculate_product(\n"
    "        self, product_code: str, product_qty: int | float, *, use_stock: bool,\n"
    "        stock_snapshot: dict[str, dict[str, Any]] | None = None,\n"
    "    ) -> dict[str, Any]:\n",
    'requirements product signature',
)
req = replace_once(
    req,
    "            use_stock=use_stock,\n            root_ignore_stock=set(),\n        )\n\n    def _calculate_from_roots(self, *, roots, product_code, product_name, product_qty, revision, semi_map, use_stock, root_ignore_stock):\n        try:\n            stock = load_stock_snapshot() if use_stock else {}\n",
    "            use_stock=use_stock,\n"
    "            root_ignore_stock=set(),\n"
    "            stock_snapshot=stock_snapshot,\n"
    "        )\n\n"
    "    def _calculate_from_roots(\n"
    "        self, *, roots, product_code, product_name, product_qty, revision, semi_map, use_stock, root_ignore_stock,\n"
    "        stock_snapshot: dict[str, dict[str, Any]] | None = None,\n"
    "    ):\n"
    "        try:\n"
    "            if use_stock and stock_snapshot is not None:\n"
    "                stock = {str(key): dict(value) for key, value in stock_snapshot.items() if isinstance(value, dict)}\n"
    "            else:\n"
    "                stock = load_stock_snapshot() if use_stock else {}\n",
    'requirements stock override',
)
req_path.write_text(req, encoding='utf-8')


# ---------------------------------------------------------------------
# planowanie_magazyn.py - production reservation/consumption bridge
# ---------------------------------------------------------------------
bridge = r'''# version: 1.2
# Moduł: planowanie_magazyn
# Most Planowanie <-> istniejący Magazyn. Nie tworzy równoległej bazy stanów.
# Zmiany 1.1: naddatek półproduktu może być księgowany idempotentnie po ID Dyspozycji.
# Zmiany 1.2:
# - Dyspozycja wykonania rezerwuje istniejące stany przy rozpoczęciu.
# - Przy zamknięciu rezerwacje są dopasowane do faktycznej ilości i zużywane.
# - Operacje są chronione identyfikatorem Dyspozycji przed podwójnym rozliczeniem.

from __future__ import annotations

import json
import os
from pathlib import Path
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


def _settlement_path() -> Path:
    try:
        from config_manager import ConfigManager
        return Path(ConfigManager().path_data('magazyn', 'produkcja_rozliczenia.json'))
    except Exception:
        return Path('data') / 'magazyn' / 'produkcja_rozliczenia.json'


def _load_settlements() -> dict[str, Any]:
    path = _settlement_path()
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_settlements(data: dict[str, Any]) -> None:
    path = _settlement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_operation_settlement(operation_id: str) -> dict[str, Any]:
    operation_id = str(operation_id or '').strip()
    if not operation_id:
        return {}
    row = _load_settlements().get(operation_id)
    return dict(row) if isinstance(row, dict) else {}


def _targets_from_rows(rows: list[dict[str, Any]], snapshot: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        qty = _num(row.get('z_magazynu'))
        if qty <= 1e-9:
            continue
        code = str(row.get('kod') or '').strip()
        if not code:
            continue
        stock = snapshot.get(code.casefold())
        if not stock:
            raise WarehouseIntegrationError(f"Pozycja '{code}' nie istnieje już w Magazynie.")
        requested_unit = str(row.get('jednostka') or '').strip()
        stock_unit = str(stock.get('jednostka') or '').strip()
        if requested_unit and stock_unit and requested_unit.casefold() != stock_unit.casefold():
            raise WarehouseIntegrationError(
                f"Jednostka '{code}' zmieniła się: wymagane {requested_unit}, Magazyn {stock_unit}."
            )
        item_id = str(stock.get('id') or code)
        target = grouped.setdefault(item_id, {
            'item_id': item_id,
            'kod': str(stock.get('kod') or code),
            'jednostka': requested_unit or stock_unit,
            'ilosc': 0.0,
        })
        target['ilosc'] += qty
    return list(grouped.values())


def reserve_execution_requirements(
    operation_id: str,
    rows: list[dict[str, Any]],
    *,
    user: str = '',
    context: str = '',
) -> list[dict[str, Any]]:
    operation_id = str(operation_id or '').strip()
    if not operation_id:
        raise WarehouseIntegrationError('Brak ID Dyspozycji do rezerwacji.')
    settlements = _load_settlements()
    previous = settlements.get(operation_id)
    if isinstance(previous, dict):
        status = str(previous.get('status') or '')
        if status in {'reserved', 'consuming'} and isinstance(previous.get('reservations'), list):
            return [dict(x) for x in previous.get('reservations') if isinstance(x, dict)]
        if status in {'consumed', 'done'}:
            return []

    snapshot = load_stock_snapshot()
    targets = _targets_from_rows(rows, snapshot)
    if not targets:
        entry = dict(previous or {}) if isinstance(previous, dict) else {}
        entry.update({'status': 'reserved', 'reservations': [], 'reserved_by': str(user or ''), 'context': str(context or '')})
        settlements[operation_id] = entry
        _save_settlements(settlements)
        return []

    try:
        import logika_magazyn as LM
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się uruchomić rezerwacji Magazynu: {exc}') from exc

    created: list[dict[str, Any]] = []
    try:
        for target in targets:
            want = float(target['ilosc'])
            got = float(LM.rezerwuj(target['item_id'], want, str(user or 'system'), kontekst=context or f'Dyspozycja {operation_id}'))
            if got + 1e-9 < want:
                raise WarehouseIntegrationError(
                    f"Nie udało się zarezerwować '{target['kod']}': {got:g} z {want:g}. Odśwież zapotrzebowanie."
                )
            row = dict(target)
            row['ilosc'] = got
            created.append(row)
    except Exception as exc:
        for row in reversed(created):
            try:
                LM.zwolnij_rezerwacje(row['item_id'], row['ilosc'], str(user or 'system'), kontekst=f'Rollback {operation_id}')
            except Exception:
                pass
        if isinstance(exc, WarehouseIntegrationError):
            raise
        raise WarehouseIntegrationError(f'Nie udało się zarezerwować Magazynu: {exc}') from exc

    entry = dict(previous or {}) if isinstance(previous, dict) else {}
    entry.update({
        'status': 'reserved',
        'reservations': created,
        'reserved_by': str(user or ''),
        'context': str(context or ''),
    })
    settlements[operation_id] = entry
    _save_settlements(settlements)
    return created


def stock_snapshot_for_operation(operation_id: str) -> dict[str, dict[str, Any]]:
    snapshot = load_stock_snapshot()
    entry = get_operation_settlement(operation_id)
    for reservation in entry.get('reservations') or []:
        if not isinstance(reservation, dict):
            continue
        code = str(reservation.get('kod') or '').strip().casefold()
        qty = max(0.0, _num(reservation.get('ilosc')))
        row = snapshot.get(code)
        if not row or qty <= 0:
            continue
        row['wolne'] = min(float(row.get('stan', 0) or 0), float(row.get('wolne', 0) or 0) + qty)
    return snapshot


def release_execution_reservations(operation_id: str, *, user: str = '', context: str = '') -> list[dict[str, Any]]:
    operation_id = str(operation_id or '').strip()
    if not operation_id:
        return []
    settlements = _load_settlements()
    entry = settlements.get(operation_id)
    if not isinstance(entry, dict):
        return []
    if str(entry.get('status') or '') in {'consumed', 'done', 'released'}:
        return []
    reservations = [dict(x) for x in (entry.get('reservations') or []) if isinstance(x, dict)]
    if not reservations:
        entry['status'] = 'released'
        settlements[operation_id] = entry
        _save_settlements(settlements)
        return []
    try:
        import logika_magazyn as LM
        for row in reservations:
            LM.zwolnij_rezerwacje(row['item_id'], float(row['ilosc']), str(user or 'system'), kontekst=context or f'Anulowanie {operation_id}')
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się zwolnić rezerwacji Magazynu: {exc}') from exc
    entry['status'] = 'released'
    entry['reservations'] = []
    entry['released_by'] = str(user or '')
    settlements[operation_id] = entry
    _save_settlements(settlements)
    return reservations


def reconcile_and_consume_execution(
    operation_id: str,
    desired_rows: list[dict[str, Any]],
    *,
    user: str = '',
    context: str = '',
) -> list[dict[str, Any]]:
    operation_id = str(operation_id or '').strip()
    if not operation_id:
        raise WarehouseIntegrationError('Brak ID Dyspozycji do rozliczenia.')
    settlements = _load_settlements()
    entry = settlements.get(operation_id)
    if not isinstance(entry, dict):
        entry = {}
    if str(entry.get('status') or '') in {'consumed', 'done'} and isinstance(entry.get('consumption'), list):
        return [dict(x) for x in entry.get('consumption') if isinstance(x, dict)]

    snapshot = load_stock_snapshot()
    desired = _targets_from_rows(desired_rows, stock_snapshot_for_operation(operation_id))
    desired_by_id = {str(x['item_id']): dict(x) for x in desired}
    current = [dict(x) for x in (entry.get('reservations') or []) if isinstance(x, dict)]
    current_by_id = {str(x.get('item_id') or ''): dict(x) for x in current if str(x.get('item_id') or '')}

    try:
        import logika_magazyn as LM
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się uruchomić rozliczenia Magazynu: {exc}') from exc

    newly_reserved: list[dict[str, Any]] = []
    try:
        for item_id, target in desired_by_id.items():
            want = float(target.get('ilosc') or 0)
            have = float((current_by_id.get(item_id) or {}).get('ilosc') or 0)
            extra = max(0.0, want - have)
            if extra <= 1e-9:
                continue
            got = float(LM.rezerwuj(item_id, extra, str(user or 'system'), kontekst=context or f'Rozliczenie {operation_id}'))
            if got + 1e-9 < extra:
                raise WarehouseIntegrationError(
                    f"Brakuje stanu '{target.get('kod') or item_id}' do rozliczenia wykonanej ilości."
                )
            newly_reserved.append({'item_id': item_id, 'ilosc': got})
    except Exception as exc:
        for row in reversed(newly_reserved):
            try:
                LM.zwolnij_rezerwacje(row['item_id'], row['ilosc'], str(user or 'system'), kontekst=f'Rollback {operation_id}')
            except Exception:
                pass
        if isinstance(exc, WarehouseIntegrationError):
            raise
        raise WarehouseIntegrationError(f'Nie udało się uzupełnić rezerwacji: {exc}') from exc

    try:
        for item_id, old in current_by_id.items():
            have = float(old.get('ilosc') or 0)
            want = float((desired_by_id.get(item_id) or {}).get('ilosc') or 0)
            release = max(0.0, have - want)
            if release > 1e-9:
                LM.zwolnij_rezerwacje(item_id, release, str(user or 'system'), kontekst=f'Korekta {operation_id}')
    except Exception as exc:
        raise WarehouseIntegrationError(f'Nie udało się skorygować rezerwacji: {exc}') from exc

    final_reservations = [dict(x) for x in desired_by_id.values() if float(x.get('ilosc') or 0) > 1e-9]
    entry.update({
        'status': 'consuming',
        'reservations': final_reservations,
        'actual_requirements': desired_rows,
    })
    settlements[operation_id] = entry
    _save_settlements(settlements)

    # Walidacja przed pierwszym zużyciem.
    fresh = LM.load_magazyn(include_external=True)
    items = fresh.get('items') or {}
    for row in final_reservations:
        item_id = str(row['item_id'])
        item = items.get(item_id)
        if not isinstance(item, dict):
            raise WarehouseIntegrationError(f"Brak pozycji '{row.get('kod') or item_id}' przed zużyciem.")
        qty = float(row['ilosc'])
        if float(item.get('stan', 0) or 0) + 1e-9 < qty:
            raise WarehouseIntegrationError(f"Stan '{row.get('kod') or item_id}' jest za mały do rozliczenia.")
        if float(item.get('rezerwacje', 0) or 0) + 1e-9 < qty:
            raise WarehouseIntegrationError(f"Rezerwacja '{row.get('kod') or item_id}' jest za mała do rozliczenia.")

    consumption: list[dict[str, Any]] = []
    try:
        for row in final_reservations:
            item_id = str(row['item_id'])
            qty = float(row['ilosc'])
            LM.zuzyj(item_id, qty, str(user or 'system'), kontekst=context or f'Dyspozycja {operation_id}')
            LM.zwolnij_rezerwacje(item_id, qty, str(user or 'system'), kontekst=f'Rozliczenie {operation_id}')
            consumption.append(dict(row))
    except Exception as exc:
        raise WarehouseIntegrationError(
            f'Rozliczenie Magazynu zatrzymało się podczas zużycia. Sprawdź historię Magazynu: {exc}'
        ) from exc

    entry['status'] = 'consumed'
    entry['reservations'] = []
    entry['consumption'] = consumption
    entry['consumed_by'] = str(user or '')
    settlements[operation_id] = entry
    _save_settlements(settlements)
    return consumption


def add_semiproduct_surplus(
    code: str,
    qty: float,
    *,
    name: str = '',
    user: str = '',
    context: str = '',
    operation_id: str = '',
) -> dict[str, Any]:
    code = str(code or '').strip()
    qty = _num(qty)
    if not code:
        raise WarehouseIntegrationError('Brak kodu półproduktu dla naddatku.')
    if qty <= 0:
        return {'kod': code, 'dodano': 0.0}
    operation_id = str(operation_id or '').strip()
    previous = {}
    if operation_id:
        settlements = _load_settlements()
        row = settlements.get(operation_id)
        previous = dict(row) if isinstance(row, dict) else {}
        if previous.get('surplus_done') is True:
            return {'kod': code, 'dodano': 0.0, 'already_settled': True, 'previous': previous}
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
    result = {'kod': code, 'dodano': qty, 'stan': _num((saved or {}).get('stan'))}
    if operation_id:
        settlements = _load_settlements()
        entry = dict(settlements.get(operation_id) or {}) if isinstance(settlements.get(operation_id), dict) else {}
        entry.update({
            'status': 'done',
            'surplus_done': True,
            'surplus': {'kod': code, 'ilosc': qty},
            'user': str(user or ''),
            'context': str(context or ''),
        })
        settlements[operation_id] = entry
        _save_settlements(settlements)
    return result
'''
Path('planowanie_magazyn.py').write_text(bridge, encoding='utf-8')


# ---------------------------------------------------------------------
# gui_zlecenia.py
# ---------------------------------------------------------------------
ui_path = Path('gui_zlecenia.py')
ui = ui_path.read_text(encoding='utf-8')
ui = replace_once(ui, '# version: 1.5\n', '# version: 1.6\n', 'dysp ui version')
ui = replace_once(
    ui,
    '# Zmiany 1.5:\n',
    '# Zmiany 1.6:\n'
    '# - Rozpoczęcie Dyspozycji wykonania rezerwuje potrzebne dostępne stany Magazynu.\n'
    '# - Zamknięcie rozlicza faktyczną ilość, zużywa rezerwacje i dopiero potem księguje naddatek półproduktu.\n'
    '# - Usunięcie aktywnej Dyspozycji wykonania zwalnia jej rezerwacje; edycja po rozpoczęciu jest blokowana.\n'
    '# Zmiany 1.5:\n',
    'dysp ui changelog',
)
ui = replace_once(
    ui,
    'from planowanie_magazyn import WarehouseIntegrationError, add_semiproduct_surplus\n',
    'from planowanie_magazyn import (\n'
    '    WarehouseIntegrationError,\n'
    '    add_semiproduct_surplus,\n'
    '    get_operation_settlement,\n'
    '    reconcile_and_consume_execution,\n'
    '    release_execution_reservations,\n'
    '    reserve_execution_requirements,\n'
    '    stock_snapshot_for_operation,\n'
    ')\n',
    'dysp warehouse imports',
)
# _change_status becomes boolean so reservation can be rolled back on failed start.
ui = replace_once(
    ui,
    '    def _change_status(self, target: str) -> None:\n',
    '    def _change_status(self, target: str) -> bool:\n',
    'dysp change status signature',
)
ui = replace_once(ui, '            return\n        dysp_id = str(mapped.get("id") or "").strip()\n', '            return False\n        dysp_id = str(mapped.get("id") or "").strip()\n', 'change status missing mapped return')
ui = replace_once(ui, '        if not dysp_id:\n            return\n        who = self._login_user or str(mapped.get("autor") or "").strip()\n        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)\n', '        if not dysp_id:\n            return False\n        who = self._login_user or str(mapped.get("autor") or "").strip()\n        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)\n', 'change status missing id return')
ui = replace_once(
    ui,
    '            return\n        try:\n            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n        except Exception:\n            self._reload_orders()\n\n    def _on_start(self) -> None:\n',
    '            return False\n'
    '        try:\n'
    '            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n'
    '        except Exception:\n'
    '            self._reload_orders()\n'
    '        return True\n\n'
    '    def _calculate_execution_requirements(self, mapped: dict[str, Any], qty: float, *, stock_snapshot=None) -> dict[str, Any]:\n'
    '        meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}\n'
    '        level = str(meta.get("poziom_wykonania") or "").strip().lower()\n'
    '        from produkty_store import ProductCatalog\n'
    '        from polprodukty_store import SemiProductCatalog\n'
    '        from planowanie_zapotrzebowanie import RequirementCalculator, RequirementError\n'
    '        products = ProductCatalog()\n'
    '        calc = RequirementCalculator(products, SemiProductCatalog(products.cfg))\n'
    '        if level in {"zlecenie", "produkt"}:\n'
    '            code = str(meta.get("product_code") or "").strip()\n'
    '            if not code:\n'
    '                raise RequirementError("Brak produktu w Dyspozycji wykonania.")\n'
    '            return calc.calculate_with_stock(code, qty, stock_snapshot=stock_snapshot)\n'
    '        if level == "polprodukt":\n'
    '            code = str(meta.get("polprodukt_code") or "").strip()\n'
    '            if not code:\n'
    '                raise RequirementError("Brak półproduktu w Dyspozycji wykonania.")\n'
    '            return calc.calculate_semi_with_stock(code, qty, ignore_root_stock=True, stock_snapshot=stock_snapshot)\n'
    '        raise RequirementError("Nieznany poziom wykonania Dyspozycji.")\n\n'
    '    def _on_start(self) -> None:\n',
    'dysp requirements helper',
)
# Block production edit after start.
ui = replace_once(
    ui,
    '        if not mapped:\n            return\n        mapped["edit_mode"] = True\n',
    '        if not mapped:\n'
    '            return\n'
    '        if (\n'
    '            str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania"\n'
    '            and _dysp_status(mapped) != "nowa"\n'
    '        ):\n'
    '            messagebox.showinfo(\n'
    '                "Dyspozycje",\n'
    '                "Dyspozycji wykonania nie można edytować po rozpoczęciu, ponieważ ma już powiązane rezerwacje Magazynu.",\n'
    '                parent=self,\n'
    '            )\n'
    '            return\n'
    '        mapped["edit_mode"] = True\n',
    'dysp production edit guard',
)
# Replace final start call with reservation flow.
ui = replace_once(
    ui,
    '        self._change_status("w_toku")\n\n    def _on_pause(self) -> None:\n',
    '        dysp_id = str(mapped.get("id") or "").strip()\n'
    '        is_execution = str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania"\n'
    '        if is_execution:\n'
    '            meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}\n'
    '            try:\n'
    '                planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))\n'
    '                requirements = self._calculate_execution_requirements(mapped, planned)\n'
    '                reservations = reserve_execution_requirements(\n'
    '                    dysp_id,\n'
    '                    list(requirements.get("rows") or []),\n'
    '                    user=who,\n'
    '                    context=f"Rozpoczęcie Dyspozycji {dysp_id}",\n'
    '                )\n'
    '            except Exception as exc:\n'
    '                messagebox.showerror(\n'
    '                    "Rezerwacja Magazynu",\n'
    '                    f"Nie udało się przygotować Dyspozycji wykonania:\\n{exc}",\n'
    '                    parent=self,\n'
    '                )\n'
    '                return\n'
    '            meta["zapotrzebowanie_start"] = list(requirements.get("rows") or [])\n'
    '            meta["magazyn_rezerwacje"] = reservations\n'
    '            updated = update_dyspozycja(dysp_id, {"meta": meta})\n'
    '            if not updated:\n'
    '                try:\n'
    '                    release_execution_reservations(dysp_id, user=who, context="Błąd zapisu Dyspozycji")\n'
    '                except Exception:\n'
    '                    pass\n'
    '                messagebox.showerror("Dyspozycje", "Nie udało się zapisać rezerwacji w Dyspozycji.", parent=self)\n'
    '                return\n'
    '        if not self._change_status("w_toku") and is_execution:\n'
    '            try:\n'
    '                release_execution_reservations(dysp_id, user=who, context="Nieudane rozpoczęcie Dyspozycji")\n'
    '            except Exception:\n'
    '                pass\n\n'
    '    def _on_pause(self) -> None:\n',
    'dysp start reservation',
)
# Replace production close block.
start_marker = '        if typ == "zlecenie_wykonania":\n'
close_start = ui.index(start_marker, ui.index('    def _on_close(self)'))
close_end_marker = '\n        changed = set_dyspozycja_status(\n'
close_end = ui.index(close_end_marker, close_start)
new_close = r'''        if typ == "zlecenie_wykonania":
            meta = dict(mapped.get("meta") or {}) if isinstance(mapped.get("meta"), dict) else {}
            try:
                planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
            except (TypeError, ValueError):
                planned = 0.0
            actual = simpledialog.askfloat(
                "Rozlicz wykonanie",
                "Ile faktycznie wykonano?",
                initialvalue=planned if planned > 0 else 1,
                minvalue=0.0,
                parent=self,
            )
            if actual is None:
                return
            meta["ilosc_wykonana"] = actual
            meta["brak_wykonania"] = max(0.0, planned - actual)
            level = str(meta.get("poziom_wykonania") or "").strip().lower()

            try:
                if actual <= 0:
                    release_execution_reservations(
                        dysp_id,
                        user=who,
                        context=f"Zamknięcie bez wykonania {dysp_id}",
                    )
                    requirements_actual = {"rows": [], "warnings": []}
                    consumption = []
                else:
                    own_snapshot = stock_snapshot_for_operation(dysp_id)
                    requirements_actual = self._calculate_execution_requirements(
                        mapped,
                        actual,
                        stock_snapshot=own_snapshot,
                    )
                    raw_shortages = []
                    for row in requirements_actual.get("rows") or []:
                        if str(row.get("typ") or "").strip().lower() != "surowiec":
                            continue
                        try:
                            missing = float(row.get("brak") or 0)
                        except (TypeError, ValueError):
                            missing = 0.0
                        if missing > 1e-9:
                            raw_shortages.append(
                                f"{row.get('kod','')}: {missing:g} {row.get('jednostka','')}"
                            )
                    critical_warnings = [
                        str(x) for x in (requirements_actual.get("warnings") or [])
                        if str(x).startswith("Brak definicji półproduktu")
                        or "nie ma surowca ani własnego składu" in str(x)
                    ]
                    if raw_shortages or critical_warnings:
                        details = []
                        if raw_shortages:
                            details.append("Braki surowców:\n" + "\n".join(raw_shortages[:15]))
                        if critical_warnings:
                            details.append("Braki definicji:\n" + "\n".join(critical_warnings[:10]))
                        messagebox.showerror(
                            "Rozliczenie produkcji",
                            "Nie można zamknąć wykonania, bo Magazyn/Skład nie pozwala rozliczyć podanej ilości.\n\n"
                            + "\n\n".join(details),
                            parent=self,
                        )
                        return
                    consumption = reconcile_and_consume_execution(
                        dysp_id,
                        list(requirements_actual.get("rows") or []),
                        user=who,
                        context=f"Dyspozycja {dysp_id}",
                    )
            except WarehouseIntegrationError as exc:
                messagebox.showerror(
                    "Rozliczenie produkcji",
                    f"Nie udało się rozliczyć Magazynu:\n{exc}\n\nDyspozycja nie została zamknięta.",
                    parent=self,
                )
                return
            except Exception as exc:
                messagebox.showerror(
                    "Rozliczenie produkcji",
                    f"Nie udało się przeliczyć wykonanej ilości:\n{exc}\n\nDyspozycja nie została zamknięta.",
                    parent=self,
                )
                return

            meta["zapotrzebowanie_wykonane"] = list(requirements_actual.get("rows") or [])
            meta["magazyn_zuzycie"] = consumption
            if level == "polprodukt":
                surplus = max(0.0, actual - planned)
                meta["naddatek"] = surplus
                if surplus > 0:
                    code = str(meta.get("polprodukt_code") or "").strip()
                    name = str(meta.get("polprodukt_name") or code)
                    try:
                        result = add_semiproduct_surplus(
                            code,
                            surplus,
                            name=name,
                            user=who,
                            context=f"Dyspozycja {dysp_id}",
                            operation_id=dysp_id,
                        )
                    except WarehouseIntegrationError as exc:
                        messagebox.showerror(
                            "Rozliczenie produkcji",
                            f"Zużycie zostało rozliczone, ale nie udało się zaksięgować naddatku:\n{exc}\n\n"
                            "Dyspozycja nie została zamknięta. Ponowna próba nie zużyje materiału drugi raz.",
                            parent=self,
                        )
                        return
                    meta["naddatek_zaksiegowany"] = bool(result.get("dodano") or result.get("already_settled"))
            updated = update_dyspozycja(dysp_id, {"meta": meta})
            if updated:
                mapped = updated
'''
ui = ui[:close_start] + new_close + ui[close_end:]
# Production delete: release active reservation, and block delete after consumption until closed.
old_delete = '''        if not dysp_id:
            return
        ok = messagebox.askyesno(
'''
new_delete = '''        if not dysp_id:
            return
        if str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania":
            settlement = get_operation_settlement(dysp_id)
            settlement_status = str(settlement.get("status") or "")
            if settlement_status in {"consumed", "done"} and not _dysp_is_closed(mapped):
                messagebox.showerror(
                    "Dyspozycje",
                    "Ta Dyspozycja ma już rozliczone zużycie Magazynu. Najpierw dokończ jej zamknięcie.",
                    parent=self,
                )
                return
        ok = messagebox.askyesno(
'''
ui = replace_once(ui, old_delete, new_delete, 'dysp delete settlement guard')
ui = replace_once(
    ui,
    '        if not ok:\n            return\n        deleted = delete_dyspozycja(dysp_id)\n',
    '        if not ok:\n'
    '            return\n'
    '        if str(mapped.get("typ_dyspozycji") or "").strip().lower() == "zlecenie_wykonania":\n'
    '            try:\n'
    '                release_execution_reservations(\n'
    '                    dysp_id,\n'
    '                    user=self._login_user or str(mapped.get("autor") or ""),\n'
    '                    context=f"Usunięcie Dyspozycji {dysp_id}",\n'
    '                )\n'
    '            except WarehouseIntegrationError as exc:\n'
    '                messagebox.showerror(\n'
    '                    "Dyspozycje",\n'
    '                    f"Nie można usunąć Dyspozycji, bo nie udało się zwolnić jej rezerwacji:\\n{exc}",\n'
    '                    parent=self,\n'
    '                )\n'
    '                return\n'
    '        deleted = delete_dyspozycja(dysp_id)\n',
    'dysp delete release',
)
ui_path.write_text(ui, encoding='utf-8')

print('U2A-6 reservation patch prepared')
