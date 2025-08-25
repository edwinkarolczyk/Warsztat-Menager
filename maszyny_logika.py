# Plik: maszyny_logika.py
# Wersja: 1.0.0
# Zmiany:
# - Nowy moduł z funkcjami next_task oraz complete_task dla zarządzania zadaniami maszyn.

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, date
from typing import Tuple, Optional

try:  # logger optional
    import logger
    _log = getattr(logger, "log_akcja", lambda m: None)
except Exception:  # pragma: no cover - fallback gdy brak loggera
    def _log(msg):
        pass

MASZYNY_PATH = Path("maszyny.json")


def _read() -> list[dict]:
    if not MASZYNY_PATH.exists():
        return []
    with open(MASZYNY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data: list[dict]) -> None:
    with open(MASZYNY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_machines() -> list[dict]:
    """Publiczne wczytanie listy maszyn."""
    return _read()


def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def next_task(machine: dict) -> Tuple[Optional[int], Optional[dict]]:
    """Zwraca krotkę (index, zadanie) najbliższego zadania dla maszyny."""
    tasks = machine.get("zadania", [])
    if not tasks:
        return None, None
    best_i = None
    best_d = None
    for i, t in enumerate(tasks):
        try:
            d = _parse_date(t.get("data"))
        except Exception:
            continue
        if best_d is None or d < best_d:
            best_i = i
            best_d = d
    if best_i is None:
        return None, None
    return best_i, tasks[best_i]


def _months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def _add_months(d: date, months: int) -> date:
    # prosta implementacja bez zależności zewnętrznych
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # zachowaj dzień, ogranicz do ostatniego dnia miesiąca
    day = min(d.day, [31,
                      29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m-1])
    return date(y, m, day)


def complete_task(machine_id: str, task_index: int, user: str | None = None) -> dict:
    """Oznacza zadanie jako wykonane i wylicza kolejną datę wg interwału.

    machine_id – nr_ewid maszyny.
    task_index – indeks zadania w tablicy zadania.
    user – kto wykonał zadanie.
    Zwraca zaktualizowaną maszynę.
    """
    machines = _read()
    machine = next((m for m in machines if str(m.get("nr_ewid")) == str(machine_id)), None)
    if machine is None:
        raise KeyError(f"Brak maszyny {machine_id}")
    tasks = machine.get("zadania", [])
    if task_index < 0 or task_index >= len(tasks):
        raise IndexError("Nieprawidłowy indeks zadania")

    task = tasks.pop(task_index)
    today = date.today()
    # prosty zapis historii na poziomie maszyny
    machine.setdefault("historia", []).append({
        "zadanie": task.get("typ_zadania"),
        "kiedy": _format_date(today),
        "kto": user or "system",
    })

    current_date = _parse_date(task.get("data"))
    # oblicz interwał
    interwal_m = 6  # domyślnie 6 miesięcy
    dates_sorted = sorted(_parse_date(t["data"]) for t in tasks + [task])
    if len(dates_sorted) > 1:
        # zakładamy stały interwał między pierwszymi dwoma zadaniami
        interwal_m = _months_between(dates_sorted[0], dates_sorted[1]) or interwal_m

    # nowa data = ostatnia znana + interwał
    max_date = max(dates_sorted)
    next_date = _add_months(max_date, interwal_m)
    new_task = {
        "data": _format_date(next_date),
        "typ_zadania": task.get("typ_zadania"),
        "uwagi": task.get("uwagi", ""),
    }
    tasks.append(new_task)
    tasks.sort(key=lambda t: t.get("data", ""))
    machine["zadania"] = tasks
    _write(machines)
    _log(f"Maszyna {machine_id}: zadanie {task_index} wykonane przez {user}")
    return machine

