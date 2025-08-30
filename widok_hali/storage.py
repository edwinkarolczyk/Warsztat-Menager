"""Obsługa konfiguracji widoku hali."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import logger

CONFIG_PATH = Path("config.json")

DEFAULT_CFG_HALA = {
    "show_grid": True,
    "grid_step_px": 4,
    "backgrounds": {"1": "grafiki/hala_1.jpg", "2": "grafiki/hala_2.jpg"},
    "workshop_start": {"x": 20, "y": 20},
    "anim_interval_ms": 100,
    "drag_snap_px": 4,
    "triple_confirm_delete": True,
}


def load_config_hala(config_path: Path | str = CONFIG_PATH) -> dict:
    """Wczytaj sekcję "hala" z pliku konfiguracyjnego.

    ``config_path`` może być ścieżką w postaci ``Path`` lub ``str``. Zwraca
    słownik z ustawieniami. Braki wypełnia wartościami domyślnymi i loguje
    ostrzeżenia do ``logger.log_akcja``.
    """
    cfg = copy.deepcopy(DEFAULT_CFG_HALA)
    path = Path(config_path)

    if not path.exists():
        logger.log_akcja(
            f"WARN: Brak pliku {config_path}, użyto wartości domyślnych dla 'hala'"
        )
        return cfg

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        logger.log_akcja(
            f"WARN: Błąd wczytywania {config_path}: {exc}; użyto wartości domyślnych dla 'hala'"
        )
        return cfg

    section = data.get("hala")
    if not isinstance(section, dict):
        logger.log_akcja(
            "WARN: Brak sekcji 'hala' w config.json, użyto wartości domyślnych"
        )
        return cfg

    for key in [
        "show_grid",
        "grid_step_px",
        "anim_interval_ms",
        "drag_snap_px",
        "triple_confirm_delete",
    ]:
        if key in section:
            cfg[key] = section[key]
        else:
            logger.log_akcja(f"WARN: Brak klucza hala.{key} – użyto wartości domyślnej")

    # backgrounds
    bgs = section.get("backgrounds")
    if not isinstance(bgs, dict):
        logger.log_akcja(
            "WARN: hala.backgrounds nie jest obiektem – użyto wartości domyślnych"
        )
        bgs = {}
    for hall_id, default_path in DEFAULT_CFG_HALA["backgrounds"].items():
        if hall_id in bgs:
            cfg["backgrounds"][hall_id] = bgs[hall_id]
        else:
            logger.log_akcja(
                f"WARN: Brak tła hali {hall_id} – użyto wartości domyślnej"
            )

    # workshop_start
    ws = section.get("workshop_start")
    if not isinstance(ws, dict):
        logger.log_akcja(
            "WARN: hala.workshop_start nie jest obiektem – użyto wartości domyślnych"
        )
        ws = {}
    for key, default_val in DEFAULT_CFG_HALA["workshop_start"].items():
        if key in ws:
            cfg["workshop_start"][key] = ws[key]
        else:
            logger.log_akcja(
                f"WARN: Brak klucza hala.workshop_start.{key} – użyto wartości domyślnej"
            )

    return cfg
