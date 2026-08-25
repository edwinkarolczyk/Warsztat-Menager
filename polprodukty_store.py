# version: 1.1
# Moduł: polprodukty_store
# U2A-2: jedno źródło półproduktów w aktywnym WM_DATA_ROOT/polprodukty.
# Zmiany 1.1:
# - Półprodukt może mieć własny wielopoziomowy skład z innych półproduktów.
# - Dodano bezpieczny zapis składu z kopią pliku i bez migracji pozostałych danych.

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
    def _normalise_sklad(raw: dict[str, Any]) -> list[dict[str, Any]]:
        value = raw.get('sklad')
        if not isinstance(value, list):
            value = raw.get('polprodukty')
        if not isinstance(value, list):
            value = raw.get('BOM')
        if not isinstance(value, list):
            return []
        out: list[dict[str, Any]] = []
        for row in value:
            if not isinstance(row, dict):
                continue
            code = str(row.get('kod') or row.get('id') or row.get('symbol') or '').strip()
            if not code:
                continue
            qty = row.get('ilosc_na_szt', row.get('ilosc_na_sztuke', row.get('ilosc', 1)))
            out.append({'kod': code, 'ilosc_na_szt': qty})
        return out

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
            'sklad': SemiProductCatalog._normalise_sklad(raw),
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

    def save_sklad(self, item: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
        raw_path = item.get('_path')
        if not raw_path:
            raise SemiProductCatalogError('Nie można ustalić pliku półproduktu.')
        path = Path(str(raw_path))
        if not path.exists():
            raise SemiProductCatalogError('Plik półproduktu już nie istnieje.')
        raw = self._read_json(path)
        if raw is None:
            raise SemiProductCatalogError('Nie można odczytać pliku półproduktu.')
        own_code = str(item.get('kod') or raw.get('kod') or raw.get('id') or '').strip()
        clean: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get('kod') or entry.get('id') or entry.get('symbol') or '').strip()
            if not code:
                raise SemiProductCatalogError('Każda pozycja składu musi mieć kod półproduktu.')
            if own_code and code.casefold() == own_code.casefold():
                raise SemiProductCatalogError('Półprodukt nie może zawierać samego siebie.')
            qty_raw = entry.get('ilosc_na_szt', entry.get('ilosc_na_sztuke', entry.get('ilosc', 1)))
            try:
                qty = float(str(qty_raw).replace(',', '.'))
            except (TypeError, ValueError):
                raise SemiProductCatalogError(f"Nieprawidłowa ilość składnika '{code}'.") from None
            if qty <= 0:
                raise SemiProductCatalogError(f"Ilość składnika '{code}' musi być większa od zera.")
            if qty.is_integer():
                qty = int(qty)
            clean.append({'kod': code, 'ilosc_na_szt': qty})
        payload = dict(raw)
        payload['sklad'] = clean
        if isinstance(payload.get('polprodukty'), list):
            payload['polprodukty'] = [dict(row) for row in clean]
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

    def delete(self, item: dict[str, Any]) -> None:
        raw_path = item.get('_path')
        if not raw_path:
            raise SemiProductCatalogError('Nie można ustalić pliku półproduktu.')
        path = Path(str(raw_path))
        if not path.exists():
            raise SemiProductCatalogError('Plik półproduktu już nie istnieje.')
        self._backup(path)
        path.unlink()
