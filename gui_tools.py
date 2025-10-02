"""Helpery I/O dla modułu narzędzi (NN/SN)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from config_manager import get_root, resolve_rel
from utils_json import ensure_json

logger = logging.getLogger(__name__)


def _load_cfg(cfg_manager: Any) -> dict:
    """Bezpiecznie wczytaj konfigurację z ``cfg_manager``."""

    cfg: dict[str, Any] | None = None
    if cfg_manager is None:
        return {}
    try:
        if hasattr(cfg_manager, "load") and callable(getattr(cfg_manager, "load")):
            cfg = cfg_manager.load()
        elif hasattr(cfg_manager, "merged"):
            cfg = getattr(cfg_manager, "merged", None)
    except Exception:
        cfg = None
    return cfg if isinstance(cfg, dict) else {}


def _tools_dir_abs(cfg: dict) -> str:
    """Zwraca absolutną ścieżkę do katalogu ``<root>/narzedzia``."""

    abs_dir = resolve_rel(cfg, "tools.dir")
    if not abs_dir:
        abs_dir = os.path.join(get_root(cfg) or "", "narzedzia")
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir


def save_tool_entry(cfg_manager: Any, nr: int, data: dict) -> bool:
    """Zapisz definicję narzędzia ``nr`` pod ``<root>/narzedzia``."""

    cfg = _load_cfg(cfg_manager)
    base = _tools_dir_abs(cfg)
    path = os.path.join(base, f"{nr:03d}.json")
    ensure_json(path, default=data if data else {})
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        logger.info("[TOOLS] Zapisano %s", path)
        return True
    except Exception as exc:  # pragma: no cover - log + False
        logger.exception("[TOOLS] Błąd zapisu %s: %s", path, exc)
        return False


__all__ = ["save_tool_entry"]
