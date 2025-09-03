from __future__ import annotations

import os

CONFIG_FILE = os.environ.get("WM_CONFIG_FILE", "config.json")


def cfg_path(filename: str) -> str:
    """Return absolute path for *filename* relative to the config file location.

    If ``filename`` is already absolute, it is returned unchanged.
    """

    if os.path.isabs(filename):
        return filename
    base = os.path.dirname(os.path.abspath(CONFIG_FILE))
    return os.path.join(base, filename)


__all__ = ["cfg_path"]
