"""Image loading helpers for the hall view.

The module validates expected keys and presence of graphic files. When the
background is missing it falls back to a checkerboard image and logs a
warning. All exceptions are caught and logged using the ``[HALA]`` prefix.
"""

from __future__ import annotations

import os
from typing import Dict, Any


def _log(level: str, msg: str) -> None:
    """Simple logger used by the module."""
    print(f"[HALA][{level}] {msg}")


def load_assets(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate *config* and load image paths.

    Parameters
    ----------
    config:
        Mapping describing graphics. Expected structure::

            {
                "background": "path/to/bg.png",
                "sprites": {"name": "path/to/img.png", ...}
            }

    Returns
    -------
    dict
        Sanitised mapping with missing files removed. ``background`` will be
        replaced by a checkerboard image if the file is absent.
    """
    assets: Dict[str, Any] = {"background": None, "sprites": {}}
    try:
        bg_path = config.get("background") if isinstance(config, dict) else None
        if not bg_path or not os.path.isfile(bg_path):
            from .renderer import checkerboard

            _log("WARN", "brak tła lub plik nie istnieje – używam szachownicy")
            assets["background"] = checkerboard()
        else:
            assets["background"] = bg_path

        sprites = config.get("sprites", {}) if isinstance(config, dict) else {}
        if not isinstance(sprites, dict):
            raise ValueError("'sprites' must be a dict")
        for key, path in sprites.items():
            if os.path.isfile(path):
                assets["sprites"][key] = path
            else:
                _log("WARN", f"brak pliku grafiki dla '{key}': {path}")
    except Exception as e:  # pylint: disable=broad-except
        _log("ERROR", str(e))
    return assets


__all__ = ["load_assets"]
