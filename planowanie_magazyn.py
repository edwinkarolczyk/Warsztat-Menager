# version: 1.1
# Moduł: planowanie_magazyn
# Most Planowanie <-> istniejący Magazyn. Nie tworzy równoległej bazy stanów.
# Zmiany 1.1: naddatek półproduktu może być księgowany idempotentnie po ID Dyspozycji.

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

def add_semiproduct_surplus(code: str, qty: float, *, name: str = '', user: str = '', context: str = '', operation_id: str = '') -> dict[str, Any]:
    code = str(code or '').strip()
    qty = _num(qty)
    if not code:
        raise WarehouseIntegrationError('Brak kodu półproduktu dla naddatku.')
    if qty <= 0:
        return {'kod': code, 'dodano': 0.0}
    operation_id = str(operation_id or '').strip()
    if operation_id:
        settlements = _load_settlements()
        previous = settlements.get(operation_id)
        if isinstance(previous, dict) and previous.get('status') == 'done':
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
        settlements[operation_id] = {
            'status': 'done', 'kod': code, 'ilosc': qty, 'user': str(user or ''), 'context': str(context or '')
        }
        _save_settlements(settlements)
    return result
