from __future__ import annotations

from pathlib import Path
import os
from typing import Union

_BASE_DIR: Path | None = None


def get_base_dir() -> Path:
    """Return application root directory.

    The root is determined by searching for ``config.json`` starting from
    this file's location and moving upwards. If the configuration file
    cannot be located, the current working directory is used as a
    fallback. The result is cached for subsequent calls.
    """
    global _BASE_DIR
    if _BASE_DIR is not None:
        return _BASE_DIR

    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parent.parents):
        if (parent / "config.json").exists():
            _BASE_DIR = parent
            break
    else:
        _BASE_DIR = Path(os.getcwd()).resolve()
    return _BASE_DIR


def abs_path(*parts: Union[str, os.PathLike[str]]) -> str:
    """Return an absolute path inside the application directory."""
    return str(get_base_dir().joinpath(*map(str, parts)).resolve())
