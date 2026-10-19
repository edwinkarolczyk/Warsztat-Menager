# WM-VERSION: 0.1
# Plik: planista_print_history.py
# version: 1.0
"""Historia poleceń drukowania kart Planisty w aktywnych danych WM.

Stan 'Wysłano' nie potwierdza fizycznego wyjścia papieru z drukarki.
Dla zleceń starszych niż rejestr zachowujemy 'Brak informacji'.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

from config_manager import ConfigManager
from machine_file_guard import file_write_lock


PRINT_UNKNOWN = "Brak informacji"
PRINT_NEW = "Nie drukowano"
PRINT_PENDING = "W kolejce"
PRINT_SENT = "Wysłano"
PRINT_CHANGED = "Zmieniono"
PRINT_ERROR = "Błąd"

PRINT_STATES = (
    PRINT_UNKNOWN, PRINT_NEW, PRINT_PENDING,
    PRINT_SENT, PRINT_CHANGED, PRINT_ERROR,
)
_FINGERPRINT_FIELDS = (
    "id", "zlec_wew", "produkt", "ilosc", "wykonano", "termin",
    "version", "rzaz_mm", "uwagi", "zezwol_nadprodukcja",
    "plan_polprodukty", "zapotrzebowanie_surowce",
    "rezerwacje_surowce", "braki",
)


def print_history_path() -> Path:
    return Path(ConfigManager().path_data()) / "planista" / "zlecenia_wydruki.json"


def order_print_fingerprint(order: dict) -> str:
    """Odcisk danych widocznych na karcie, niezależny od historii wydruków."""
    view = {field: order.get(field) for field in _FINGERPRINT_FIELDS}
    payload = json.dumps(view, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict:
    if not path.is_file():
        return {"schema": 1, "legacy_ids": [], "orders": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Nie można odczytać historii wydruków: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema") != 1
        or not isinstance(value.get("legacy_ids"), list)
        or not isinstance(value.get("orders"), dict)
    ):
        raise RuntimeError("Nieprawidłowy format historii wydruków.")
    return value


def load_print_history() -> dict:
    return _load(print_history_path())


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def ensure_print_registry(orders: list[dict]) -> dict:
    """Pierwsze uruchomienie: oznacz wcześniejsze zlecenia jako historyczne."""
    path = print_history_path()
    if path.exists():
        return _load(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_write_lock(path, label="historii wydruków zleceń"):
        if path.exists():
            return _load(path)
        data = _load(path)
        data["legacy_ids"] = sorted({
            str(order.get("id") or "").strip()
            for order in orders if isinstance(order, dict) and order.get("id")
        })
        _save(path, data)
        return data


def record_print_event(
    order: dict, state: str, *, user: str = "system",
    source: str = "Planista", details: str = "",
) -> dict:
    """Zapisz jedno zdarzenie pod blokadą, bez nadpisywania starej historii."""
    if state not in {PRINT_PENDING, PRINT_SENT, PRINT_ERROR}:
        raise ValueError(f"Nieprawidłowy status wydruku: {state}")
    order_id = str(order.get("id") or "").strip()
    if not order_id:
        raise ValueError("Brak numeru zlecenia do rejestracji wydruku.")

    path = print_history_path()
    if not path.exists():
        # Automat może drukować zanim brygadzista otworzy widok zleceń.
        import zlecenia_logika as ZL
        ensure_print_registry(ZL.list_zlecenia())

    with file_write_lock(path, label="historii wydruków zleceń"):
        data = _load(path)
        # Przed zaakceptowaniem Excela numer zewnętrzny nie jest numerem
        # warsztatowym. Nie może oznaczyć przypadkowego zlecenia jako wysłane.
        record_id = (
            f"excel:{order_id}" if source == "Excel przed akceptacją"
            else order_id
        )
        events = data["orders"].setdefault(record_id, [])
        if not isinstance(events, list):
            raise RuntimeError(f"Historia wydruków zlecenia {order_id} jest uszkodzona.")
        event = {
            "czas": datetime.now().astimezone().isoformat(timespec="seconds"),
            "stan": state,
            "uzytkownik": str(user or "system"),
            "zrodlo": str(source or "Planista"),
            "wersja": order_print_fingerprint(order),
            "szczegoly": str(details or ""),
        }
        events.append(event)
        _save(path, data)
        return event


def print_status(order: dict, registry: dict | None = None) -> str:
    data = registry if registry is not None else load_print_history()
    oid = str(order.get("id") or "").strip()
    events = data.get("orders", {}).get(oid) or []
    if not events:
        return PRINT_UNKNOWN if oid in data.get("legacy_ids", []) else PRINT_NEW
    last = events[-1]
    state = last.get("stan")
    if state == PRINT_SENT and last.get("wersja") != order_print_fingerprint(order):
        return PRINT_CHANGED
    if state in {PRINT_SENT, PRINT_PENDING, PRINT_ERROR}:
        return state
    return PRINT_UNKNOWN


def print_events(order_id: str, registry: dict | None = None) -> list[dict]:
    data = registry if registry is not None else load_print_history()
    return list(data.get("orders", {}).get(str(order_id or ""), []) or [])
