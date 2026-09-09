# version: 1.0
"""Wymusza centralny ROOT dla wydruków kart maszyn."""
from __future__ import annotations

import ntpath
import os

from config_manager import ConfigManager


def _looks_like_windows_path(value: str) -> bool:
    text = str(value or "")
    return text.startswith("\\\\") or (len(text) > 1 and text[1] == ":")


def _join_root(root: str, *parts: str) -> str:
    """Połącz ścieżkę poprawnie także w testach uruchamianych poza Windows."""
    if _looks_like_windows_path(root):
        return ntpath.normpath(ntpath.join(root, *parts))
    return os.path.normpath(os.path.join(root, *parts))


def _is_machine_cards_path(parts) -> bool:
    normalized = tuple(
        str(part or "").strip().strip("/\\").casefold() for part in parts
    )
    return normalized == ("wydruki", "karty")


def _active_wm_root() -> str:
    root = str(os.environ.get("WM_ROOT") or "").strip()
    if root:
        return root
    try:
        from core import root_paths as wm_root_paths

        return str(wm_root_paths.get_root_anchor() or "").strip()
    except Exception:
        return ""


def machine_cards_output_path(*parts: str) -> str:
    root = _active_wm_root()
    if not root:
        return ""
    return _join_root(root, *parts)


def install_machine_cards_root_path() -> None:
    """Dla dokładnie <ROOT>/wydruki/karty omija lokalny ConfigManager._root."""
    original = ConfigManager.path_root
    if getattr(original, "_wm_machine_cards_root", False):
        return

    def path_root_with_machine_cards(self, *parts: str) -> str:
        if _is_machine_cards_path(parts):
            target = machine_cards_output_path(*parts)
            if target:
                return target
        return original(self, *parts)

    path_root_with_machine_cards._wm_machine_cards_root = True
    path_root_with_machine_cards._wm_original = original
    ConfigManager.path_root = path_root_with_machine_cards


__all__ = [
    "install_machine_cards_root_path",
    "machine_cards_output_path",
]
