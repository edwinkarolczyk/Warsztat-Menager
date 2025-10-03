"""Bootstrap routines ensuring WM root data exists and legacy files migrate."""

from __future__ import annotations

import logging
import os

from config_manager import ConfigManager, resolve_rel, try_migrate_if_missing
from utils_json import ensure_dir_json, safe_read_json

log = logging.getLogger(__name__)


def _ensure_all(cfg: dict) -> None:
    """Create minimal directory / file structure for root storage."""

    ensure_dir_json(
        resolve_rel(cfg, "profiles"),
        {
            "users": [
                {"login": "brygadzista", "role": "brygadzista", "pass_hash": ""}
            ]
        },
    )
    ensure_dir_json(resolve_rel(cfg, "machines"), {"maszyny": []})
    ensure_dir_json(resolve_rel(cfg, "warehouse"), {"pozycje": []})
    ensure_dir_json(resolve_rel(cfg, "bom"), {"pozycje": []})
    os.makedirs(resolve_rel(cfg, "tools_dir"), exist_ok=True)
    os.makedirs(resolve_rel(cfg, "orders_dir"), exist_ok=True)
    os.makedirs(resolve_rel(cfg, "tools_defs"), exist_ok=True)


def _migrate_legacy(cfg: dict) -> None:
    """Attempt one-way migrations from legacy locations if destination missing."""

    root = (cfg.get("paths") or {}).get("data_root") or ""
    legacy = {
        os.path.join(root, "layout", "maszyny.json"): resolve_rel(cfg, "machines"),
        os.path.join(root, "magazyn", "magazyn.json"): resolve_rel(cfg, "warehouse"),
        os.path.join(root, "produkty", "bom.json"): resolve_rel(cfg, "bom"),
        os.path.join(root, "profiles.json"): resolve_rel(cfg, "profiles"),
    }

    moved: list[tuple[str, str]] = []
    for src, dst in legacy.items():
        try:
            if try_migrate_if_missing(src, dst):
                moved.append((src, dst))
        except Exception as exc:  # pragma: no cover - log only
            log.warning("Migracja %s -> %s nieudana: %s", src, dst, exc)

    for src, dst in moved:
        log.info("[MIGRACJA] %s -> %s", src, dst)


def ensure_root_min_files(cfg: dict) -> None:
    """Ensure minimal JSON files exist under configured root."""

    safe_read_json(resolve_rel(cfg, "machines"), default=[])
    safe_read_json(resolve_rel(cfg, "tools"), default=[])
    safe_read_json(resolve_rel(cfg, "orders"), default=[])
    safe_read_json(resolve_rel(cfg, "warehouse_stock"), default={"pozycje": []})
    safe_read_json(resolve_rel(cfg, "bom"), default={"pozycje": []})


def ensure_root_ready(config_path: str = "config.json") -> bool:
    """Run ensure + migration steps for root data directory."""

    cm = ConfigManager(config_path)
    cfg = cm.load()
    _ensure_all(cfg)
    _migrate_legacy(cfg)
    return True

