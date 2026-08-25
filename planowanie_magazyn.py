# version: 1.2
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
