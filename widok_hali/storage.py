"""Helpers for storing and loading hall data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

WALLS_PATH = Path("data") / "sciany.json"
AWARIE_PATH = Path("awarie.json")


def _validate_wall(entry: Dict[str, Any]) -> None:
    required = ["hala", "x1", "y1", "x2", "y2"]
    for key in required:
        if key not in entry:
            raise ValueError(f"Brak klucza '{key}' w definicji ściany: {entry}")
    if not isinstance(entry["hala"], int):
        raise ValueError("Pole 'hala' musi być liczbą całkowitą")
    for key in ["x1", "y1", "x2", "y2"]:
        if not isinstance(entry[key], (int, float)):
            raise ValueError(f"Pole '{key}' musi być liczbą.")


def load_walls() -> List[Dict[str, Any]]:
    """Load wall segments from :mod:`data/sciany.json`.

    Returns an empty list when the file does not exist.
    Raises :class:`ValueError` if the JSON is invalid or has wrong structure.
    """
    if not WALLS_PATH.exists():
        return []
    try:
        with WALLS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Niepoprawny JSON w {WALLS_PATH}: {e}") from e
    if not isinstance(data, list):
        raise ValueError("Plik sciany.json musi zawierać listę obiektów.")
    for wall in data:
        if not isinstance(wall, dict):
            raise ValueError("Element listy ścian musi być obiektem.")
        _validate_wall(wall)
    return data


def _validate_awaria(entry: Dict[str, Any]) -> None:
    required = ["id_maszyny", "status", "timestamp"]
    for key in required:
        if key not in entry:
            raise ValueError(f"Brak klucza '{key}' w zgłoszeniu awarii: {entry}")
    if not isinstance(entry["status"], str):
        raise ValueError("'status' musi być tekstem")
    if not isinstance(entry["timestamp"], str):
        raise ValueError("'timestamp' musi być tekstem")


def load_awarie() -> List[Dict[str, Any]]:
    """Load machine failure reports from ``awarie.json``.

    Returns an empty list when the file does not exist.
    Raises :class:`ValueError` for invalid JSON or structure.
    """
    if not AWARIE_PATH.exists():
        return []
    try:
        with AWARIE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Niepoprawny JSON w {AWARIE_PATH}: {e}") from e
    if not isinstance(data, list):
        raise ValueError("Plik awarie.json musi zawierać listę zgłoszeń.")
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("Element listy awarii musi być obiektem.")
        _validate_awaria(entry)
    return data


def save_awarie(entries: List[Dict[str, Any]]) -> None:
    """Save machine failure reports to ``awarie.json``.

    The function validates entries before writing. On invalid data a
    :class:`ValueError` is raised.
    """
    if not isinstance(entries, list):
        raise ValueError("Oczekiwano listy zgłoszeń awarii.")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Każde zgłoszenie awarii musi być obiektem.")
        _validate_awaria(entry)
    with AWARIE_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
