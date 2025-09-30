"""Prosta warstwa logiki dla operacji na maszynach.
Czyta dane z pliku JSON i pozwala wyciągnąć kolejne zadania."""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

from io_utils import read_json, write_json
from logger import log_akcja

DATA_FILE: Path = Path("data") / "maszyny" / "maszyny.json"


def load_machines() -> List[Dict[str, Any]]:
    """Wczytuje listę maszyn z pliku JSON z walidacją kluczy."""
    raw = read_json(str(DATA_FILE)) or []
    if isinstance(raw, dict):
        candidates = raw.get("maszyny") or raw.get("items") or []
        data = candidates if isinstance(candidates, list) else []
        if not data:
            values = [v for v in raw.values() if isinstance(v, dict)]
            data = values
    elif isinstance(raw, list):
        data = raw
    else:
        log_akcja("[MASZYNY] Nieprawidłowy format danych maszyn")
        return []

    valid: List[Dict[str, Any]] = []
    for m in data:
        if not isinstance(m, dict):
            log_akcja("[MASZYNY] Pominięto rekord – nie jest dict")
            continue
        position = m.get("pozycja") if isinstance(m.get("pozycja"), dict) else {}
        x_val = m.get("x")
        y_val = m.get("y")
        if not isinstance(x_val, (int, float)):
            x_val = position.get("x") if isinstance(position, dict) else None
        if not isinstance(y_val, (int, float)):
            y_val = position.get("y") if isinstance(position, dict) else None

        hala = m.get("hala")
        status = m.get("status")
        missing = [
            key
            for key, present in (
                ("hala", hala is not None),
                ("x", isinstance(x_val, (int, float))),
                ("y", isinstance(y_val, (int, float))),
                ("status", status is not None),
            )
            if not present
        ]
        if missing:
            log_akcja(
                f"[MASZYNY] Maszyna {m.get('nr_ewid') or m.get('id')} brak pól {missing}"
            )
            continue

        record = dict(m)
        record.setdefault("pozycja", {})
        record["pozycja"] = dict(record["pozycja"] or {})
        record["pozycja"]["x"] = float(x_val)
        record["pozycja"]["y"] = float(y_val)
        record.setdefault("x", float(x_val))
        record.setdefault("y", float(y_val))
        valid.append(record)
    return valid


def _save_machines(data: List[Dict[str, Any]]) -> bool:
    """Zapisuje listę maszyn do pliku JSON."""
    valid: List[Dict[str, Any]] = []
    for m in data:
        if not isinstance(m, dict):
            log_akcja("[MASZYNY] Nieprawidłowy rekord przy zapisie")
            continue
        missing = [k for k in ("hala", "x", "y", "status") if k not in m]
        if missing:
            log_akcja(
                f"[MASZYNY] Maszyna {m.get('nr_ewid')} brak pól {missing}"
            )
            continue
        valid.append(m)
    return write_json(str(DATA_FILE), valid)


def next_task(machine: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Zwraca najbliższe zadanie dla maszyny (najwcześniejsza data).
    Jeżeli brak zadań, zwraca None.
    """
    tasks = machine.get("zadania") or []
    if not tasks:
        return None
    return sorted(tasks, key=lambda z: z.get("data"))[0]


def machines_with_next_task() -> List[Dict[str, Any]]:
    """Zwraca listę maszyn z informacją o najbliższym zadaniu."""
    machines = load_machines()
    wynik = []
    for m in machines:
        m2 = dict(m)
        m2["next_task"] = next_task(m)
        wynik.append(m2)
    return wynik
