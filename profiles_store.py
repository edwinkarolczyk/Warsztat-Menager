# version: 1.0
"""Helpers for loading and saving the canonical profiles.json file."""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Iterable

from config_manager import ConfigManager, get_profiles_path as cfg_get_profiles_path

logger = logging.getLogger(__name__)

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None


def _as_path(value: Path | str) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)


def _config_snapshot(cfg: ConfigManager | dict | None) -> dict | None:
    if isinstance(cfg, ConfigManager):
        return getattr(cfg, "global_cfg", None) or {}
    if isinstance(cfg, dict):
        return cfg
    return None


def resolve_profiles_path(
    cfg: ConfigManager | dict | None = None,
    *,
    path: Path | str | None = None,
) -> Path:
    target: Path
    snapshot = _config_snapshot(cfg)
    if path is not None:
        target = _as_path(path)
    else:
        env_data_root = os.environ.get("WM_DATA_ROOT", "").strip()
        if env_data_root:
            target = Path(env_data_root) / "profiles.json"
        elif root_paths is not None:
            target = root_paths.path_profiles()
        else:
            try:
                raw = cfg_get_profiles_path(snapshot)
            except Exception:
                raw = ""
            if raw:
                target = Path(raw)
            else:
                target = Path("data") / "profiles.json"
    try:
        resolved = target.expanduser().resolve()
    except Exception:
        resolved = target.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    _maybe_migrate_legacy_root_profiles(resolved)
    logger.info("[WM-ROOT][PROFILES] profiles_path=%s", resolved)
    return resolved


def _maybe_migrate_legacy_root_profiles(active_path: Path) -> None:
    """One-shot copy from <ROOT>/profiles.json to <ROOT>/data/profiles.json."""

    try:
        root_dir = active_path.parent.parent
        legacy_path = root_dir / "profiles.json"
        if os.path.normcase(str(legacy_path.resolve())) == os.path.normcase(
            str(active_path.resolve())
        ):
            return
        active_exists = active_path.exists()
        legacy_exists = legacy_path.exists()
        if legacy_exists and not active_exists:
            shutil.copy2(legacy_path, active_path)
            print(f"[WM-ROOT][PROFILES][MIGRATE] {legacy_path} -> {active_path}")
        elif legacy_exists and active_exists:
            print(
                "[WM-ROOT][PROFILES][WARN] legacy root profiles exists but active is "
                f"data profiles: {legacy_path}"
            )
    except Exception:
        logger.exception("[WM-ERR][PROFILES] legacy migration check failed")


def _extract_users(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("users", "profiles", "uzytkownicy"):
            seq = payload.get(key)
            if isinstance(seq, list):
                return [dict(item) for item in seq if isinstance(item, dict)]
        nested = [value for value in payload.values() if isinstance(value, dict)]
        if nested:
            return [dict(item) for item in nested]
    raise ValueError("Invalid profiles file structure")


def load_profiles_payload(
    cfg: ConfigManager | dict | None = None,
    *,
    path: Path | str | None = None,
) -> dict:
    target = resolve_profiles_path(cfg, path=path)
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    users = _extract_users(payload)
    return {"users": users}


def load_profiles_users(
    cfg: ConfigManager | dict | None = None,
    *,
    path: Path | str | None = None,
) -> list[dict]:
    return load_profiles_payload(cfg, path=path)["users"]


def save_profiles_users(
    users: Iterable[dict],
    cfg: ConfigManager | dict | None = None,
    *,
    path: Path | str | None = None,
) -> None:
    target = resolve_profiles_path(cfg, path=path)
    serialized = [dict(user) for user in users if isinstance(user, dict)]
    with target.open("w", encoding="utf-8") as handle:
        json.dump(serialized, handle, ensure_ascii=False, indent=2)
    logger.debug("[WM-DBG][PROFILES] saved %s profiles to %s", len(serialized), target)
