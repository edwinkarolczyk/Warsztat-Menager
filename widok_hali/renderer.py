"""Rendering utilities for the hall view."""

from __future__ import annotations

import os
from typing import Dict, Any

try:  # Optional dependency used only when available
    from PIL import Image, ImageDraw
except Exception:  # pylint: disable=broad-except
    Image = None
    ImageDraw = None


def _log(level: str, msg: str) -> None:
    print(f"[HALA][{level}] {msg}")


def checkerboard(width: int = 640, height: int = 480, tile: int = 32) -> Any:
    """Return a simple checkerboard image used as a fallback background."""
    try:
        if Image is None or ImageDraw is None:
            raise RuntimeError("Pillow is not available")
        img = Image.new("RGB", (width, height), color="#cccccc")
        draw = ImageDraw.Draw(img)
        for y in range(0, height, tile):
            for x in range(0, width, tile):
                fill = "#cccccc" if (x // tile + y // tile) % 2 == 0 else "#eeeeee"
                draw.rectangle([x, y, x + tile - 1, y + tile - 1], fill=fill)
        return img
    except Exception as e:  # pylint: disable=broad-except
        _log("ERROR", str(e))
        return None


def render(config: Dict[str, Any]) -> Any:
    """Render the hall view according to *config*.

    The function checks that required keys exist and referenced files are
    present. ``background`` may be either a filesystem path or a preloaded
    ``PIL.Image`` instance. Missing backgrounds result in a checkerboard image
    along with a warning log.
    """
    try:
        bg_obj = config.get("background") if isinstance(config, dict) else None
        if isinstance(bg_obj, str):
            if not os.path.isfile(bg_obj):
                _log("WARN", "brak tła lub plik nie istnieje – używam szachownicy")
                canvas = checkerboard()
            else:
                if Image is None:
                    raise RuntimeError("Pillow is not available")
                canvas = Image.open(bg_obj)
        elif Image is not None and isinstance(bg_obj, Image.Image):
            canvas = bg_obj
        else:
            _log("WARN", "brak tła lub plik nie istnieje – używam szachownicy")
            canvas = checkerboard()

        sprites = config.get("sprites", {}) if isinstance(config, dict) else {}
        if not isinstance(sprites, dict):
            raise ValueError("'sprites' must be a dict")
        for key, info in sprites.items():
            if not isinstance(info, (list, tuple)) or len(info) != 2:
                _log("WARN", f"niepoprawne dane sprite '{key}'")
                continue
            path, pos = info
            if not os.path.isfile(path):
                _log("WARN", f"brak pliku grafiki dla '{key}': {path}")
                continue
            if Image is None:
                _log("WARN", "Pillow is not available – pomijam rysowanie")
                continue
            try:
                sprite = Image.open(path)
                canvas.paste(sprite, pos, sprite if sprite.mode == "RGBA" else None)
            except Exception as e:  # pylint: disable=broad-except
                _log("ERROR", str(e))
        return canvas
    except Exception as e:  # pylint: disable=broad-except
        _log("ERROR", str(e))
        return checkerboard()


__all__ = ["render", "checkerboard"]
