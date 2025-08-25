"""
Prosta warstwa logiki dla operacji na maszynach.
Czyta dane z pliku JSON i pozwala wyciągnąć kolejne zadania.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_FILE: Path = Path("maszyny.json")


def load_machines() -> List[Dict[str, Any]]:
    """Wczytuje listę maszyn z pliku JSON."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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
