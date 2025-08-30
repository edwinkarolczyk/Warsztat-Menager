"""Obsługa zapisu i odczytu danych hal, ścian oraz awarii."""

from __future__ import annotations

import json
import logging
import os
from typing import List

from .const import HALLS_FILE
from .models import Hala

WALLS_FILE = os.path.join("data", "sciany.json")
AWARIE_FILE = os.path.join("data", "awarie.json")


def load_hale() -> List[Hala]:
    """Wczytaj listę hal z pliku JSON."""
    if not os.path.exists(HALLS_FILE):
        with open(HALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    try:
        with open(HALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Hala(**item) for item in data]
    except Exception:
        return []


def save_hale(hale: List[Hala]) -> None:
    """Zapisz listę hal do pliku JSON."""
    with open(HALLS_FILE, "w", encoding="utf-8") as fh:
        json.dump([h.__dict__ for h in hale], fh, indent=2, ensure_ascii=False)


def load_walls() -> List[dict]:
    """Wczytaj segmenty ścian z pliku JSON."""
    if not os.path.exists(WALLS_FILE):
        os.makedirs(os.path.dirname(WALLS_FILE), exist_ok=True)
        with open(WALLS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    try:
        with open(WALLS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        valid: List[dict] = []
        for item in data:
            if not isinstance(item, dict):
                logging.error("Niepoprawny format segmentu ściany: %r", item)
                continue
            required = {"hala", "x1", "y1", "x2", "y2"}
            if not required.issubset(item):
                logging.error("Brakujące pola segmentu ściany: %r", item)
                continue
            try:
                valid.append(
                    {
                        "hala": item["hala"],
                        "x1": int(item["x1"]),
                        "y1": int(item["y1"]),
                        "x2": int(item["x2"]),
                        "y2": int(item["y2"]),
                    }
                )
            except Exception as exc:  # pragma: no cover - defensywnie
                logging.error("Błąd walidacji segmentu ściany %r: %s", item, exc)
        return valid
    except Exception as exc:  # pragma: no cover - defensywnie
        logging.error("Błąd wczytywania %s: %s", WALLS_FILE, exc)
        return []


def load_awarie() -> List[dict]:
    """Wczytaj listę awarii z pliku JSON."""
    if not os.path.exists(AWARIE_FILE):
        os.makedirs(os.path.dirname(AWARIE_FILE), exist_ok=True)
        with open(AWARIE_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh, indent=2, ensure_ascii=False)
        return []
    try:
        with open(AWARIE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        valid: List[dict] = []
        for item in data:
            if not isinstance(item, dict):
                logging.error("Niepoprawny format awarii: %r", item)
                continue
            required = {"id_maszyny", "status", "timestamp"}
            if not required.issubset(item):
                logging.error("Brakujące pola awarii: %r", item)
                continue
            if not isinstance(item.get("id_maszyny"), (str, int)):
                logging.error("Niepoprawny typ id_maszyny: %r", item)
                continue
            if not isinstance(item.get("status"), str):
                logging.error("Niepoprawny typ status: %r", item)
                continue
            if not isinstance(item.get("timestamp"), str):
                logging.error("Niepoprawny typ timestamp: %r", item)
                continue
            valid.append(
                {
                    "id_maszyny": str(item["id_maszyny"]),
                    "status": item["status"],
                    "timestamp": item["timestamp"],
                }
            )
        return valid
    except Exception as exc:  # pragma: no cover - defensywnie
        logging.error("Błąd wczytywania %s: %s", AWARIE_FILE, exc)
        return []


def save_awarie(awarie: List[dict]) -> None:
    """Zapisz listę awarii do pliku JSON."""
    try:
        os.makedirs(os.path.dirname(AWARIE_FILE), exist_ok=True)
        with open(AWARIE_FILE, "w", encoding="utf-8") as fh:
            json.dump(awarie, fh, indent=2, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - defensywnie
        logging.error("Błąd zapisu %s: %s", AWARIE_FILE, exc)
