"""Operacje domenowe dla modułu zleceń."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, MutableMapping, Optional

from config.paths import get_path, join_path

ORDERS_DIR_KEY = "paths.orders_dir"
_SEQ_FILENAME = "_seq.json"
_DEFAULT_SEQ: Dict[str, int] = {"ZW": 0, "ZN": 0, "ZM": 0, "ZZ": 0}
_ORDER_EXTENSION = ".json"


def _orders_dir() -> str:
    """Zwraca katalog zleceń bazując na konfiguracji."""

    directory = get_path(ORDERS_DIR_KEY)
    if not directory:
        raise RuntimeError("[ORDERS] Brak skonfigurowanej ścieżki zleceń")
    return directory


def ensure_orders_dir() -> str:
    """Zapewnia istnienie katalogu ze zleceniami."""

    directory = _orders_dir()
    os.makedirs(directory, exist_ok=True)
    return directory


def _normalise_filename(order_id: str) -> str:
    if not isinstance(order_id, str):
        order_id = str(order_id)
    name = order_id.strip()
    if not name:
        raise ValueError("[ORDERS] Wymagany niepusty identyfikator zlecenia")
    if name.endswith(_ORDER_EXTENSION):
        return name
    return f"{name}{_ORDER_EXTENSION}"


def order_path(order_id: str) -> str:
    """Buduje pełną ścieżkę do pliku zlecenia."""

    filename = _normalise_filename(order_id)
    return join_path(ORDERS_DIR_KEY, filename)


def load_order(order_id: str) -> Optional[Dict[str, Any]]:
    """Wczytuje pojedyncze zlecenie. Zwraca ``None`` gdy plik nie istnieje."""

    path = order_path(order_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - błędy I/O
        raise RuntimeError(f"[ORDERS] Nie można odczytać {path!r}: {exc}") from exc
    return data if isinstance(data, dict) else None


def _iter_order_filenames() -> Iterable[str]:
    directory = ensure_orders_dir()
    try:
        for name in sorted(os.listdir(directory)):
            if not name.endswith(_ORDER_EXTENSION) or name.startswith("_"):
                continue
            yield name
    except FileNotFoundError:
        return


def load_orders() -> List[Dict[str, Any]]:
    """Zwraca listę wszystkich zleceń zapisanych w katalogu."""

    items: List[Dict[str, Any]] = []
    for filename in _iter_order_filenames():
        path = join_path(ORDERS_DIR_KEY, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if isinstance(data, dict):
            items.append(data)
    return items


def save_order(order: MutableMapping[str, Any]) -> str:
    """Zapisuje zlecenie na dysk i zwraca ścieżkę do pliku."""

    order_id = order.get("id") if isinstance(order, MutableMapping) else None
    if not order_id:
        raise ValueError("[ORDERS] Brak klucza 'id' podczas zapisu zlecenia")
    path = order_path(str(order_id))
    ensure_orders_dir()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(order, handle, ensure_ascii=False, indent=2)
    return path


def delete_order(order_id: str) -> None:
    """Usuwa zlecenie jeśli istnieje."""

    path = order_path(order_id)
    try:
        os.remove(path)
    except FileNotFoundError:
        return


def _seq_path() -> str:
    return join_path(ORDERS_DIR_KEY, _SEQ_FILENAME)


def load_sequences(defaults: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """Wczytuje licznik zleceń. Zwraca kopię danych."""

    defaults = defaults or _DEFAULT_SEQ
    path = _seq_path()
    if not os.path.exists(path):
        return dict(defaults)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
    except Exception:
        return dict(defaults)
    result: Dict[str, int] = {}
    for key, fallback in defaults.items():
        try:
            result[key] = int(data.get(key, fallback))
        except Exception:
            result[key] = fallback
    for key, value in data.items():
        if key not in result:
            try:
                result[key] = int(value)
            except Exception:
                continue
    return result


def save_sequences(seq: Dict[str, int]) -> str:
    """Zapisuje licznik zleceń. Zwraca ścieżkę pliku."""

    ensure_orders_dir()
    path = _seq_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(seq, handle, ensure_ascii=False, indent=2)
    return path


def next_sequence(kind: str, *, defaults: Optional[Dict[str, int]] = None) -> int:
    """Zwiększa i zwraca kolejny numer sekwencji dla danego rodzaju."""

    kind_key = str(kind).strip()
    if not kind_key:
        raise ValueError("[ORDERS] Rodzaj sekwencji nie może być pusty")
    seq = load_sequences(defaults)
    current = int(seq.get(kind_key, 0)) + 1
    seq[kind_key] = current
    save_sequences(seq)
    return current


def generate_order_id(
    kind: str,
    *,
    prefix: Optional[str] = None,
    width: int = 4,
    defaults: Optional[Dict[str, int]] = None,
) -> str:
    """Zwraca kolejny identyfikator w formacie ``PREFIX + liczba``."""

    number = next_sequence(kind, defaults=defaults)
    use_prefix = prefix if prefix is not None else f"{kind}-"
    if width <= 0:
        return f"{use_prefix}{number}"
    return f"{use_prefix}{str(number).zfill(width)}"
