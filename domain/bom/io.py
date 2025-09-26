"""Obsługa wejścia/wyjścia danych BOM przy użyciu konfiguracji ścieżek."""

from __future__ import annotations

import json
from typing import Any

from config.paths import get_path
from wm_log import dbg as wm_dbg, err as wm_err


def _bom_path() -> str:
    """Pobierz ścieżkę do pliku BOM z konfiguracji."""

    return get_path("bom.file")


def bom_load() -> list[dict] | dict | list:
    """Wczytaj dane BOM z pliku wskazanego w ustawieniach."""

    path = _bom_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        wm_dbg("bom.io", "loaded", path=path)
        return data
    except FileNotFoundError:
        wm_err("bom.io", "load failed", "file not found", path=path)
        return []
    except Exception as exc:  # pragma: no cover - logowanie błędów
        wm_err("bom.io", "load failed", exc, path=path)
        return []


def bom_save(data: Any) -> bool:
    """Zapisz dane BOM do pliku wskazanego w ustawieniach."""

    path = _bom_path()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        wm_dbg("bom.io", "saved", path=path)
        return True
    except Exception as exc:  # pragma: no cover - logowanie błędów
        wm_err("bom.io", "save failed", exc, path=path)
        return False
