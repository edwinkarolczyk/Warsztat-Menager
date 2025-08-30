"""
Prosta warstwa logiki dla operacji na maszynach.
Czyta dane z pliku JSON i pozwala wyciągnąć kolejne zadania.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from io_utils import read_json

DATA_FILE: Path = Path("maszyny.json")


def load_machines() -> List[Dict[str, Any]]:
    """Wczytuje listę maszyn z pliku JSON."""
    return read_json(DATA_FILE) or []


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


def delete_machine_with_triple_confirm(
    machines: List[Dict[str, Any]],
    machine_id: str,
    confirm: Callable[[], bool],
    cfg: Any,
) -> bool:
    """Usuwa maszynę po trzykrotnym potwierdzeniu.

    Funkcja respektuje ustawienie ``triple_confirm_delete`` w konfiguracji.
    Jeśli opcja jest włączona, użytkownik (za pomocą przekazanej funkcji
    ``confirm``) musi potwierdzić operację trzy razy.  W przeciwnym razie
    wystarcza pojedyncze potwierdzenie.

    Parametry
    ---------
    machines:
        Lista słowników reprezentujących maszyny.  Lista jest modyfikowana w
        miejscu przy udanym usunięciu.
    machine_id:
        Identyfikator maszyny do usunięcia.
    confirm:
        Funkcja wywoływana w celu uzyskania potwierdzenia.  Powinna zwrócić
        ``True`` aby kontynuować operację.
    cfg:
        Obiekt konfiguracyjny bądź słownik udostępniający metodę ``get``.

    Zwraca ``True`` gdy maszyna została usunięta, ``False`` w przeciwnym
    przypadku.
    """

    require_triple = False
    if cfg is not None:
        getter = getattr(cfg, "get", None)
        if callable(getter):
            require_triple = getter("triple_confirm_delete", False)
    confirmations = 3 if require_triple else 1
    for _ in range(confirmations):
        if not confirm():
            return False
    for i, m in enumerate(machines):
        if m.get("id") == machine_id:
            del machines[i]
            return True
    return False

