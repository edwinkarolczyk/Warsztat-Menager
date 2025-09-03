import json
import os
from typing import Any, Iterable

__all__ = ["_ensure_dirs", "_read_json", "_write_json"]


def _ensure_dirs(*dirs: Iterable[str]) -> None:
    """Ensure that each directory in *dirs exists."""
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def _read_json(path: str, default: Any | None = None) -> Any:
    """Read JSON file and return its content.

    Returns ``default`` (or ``{}`` if default is ``None``) when the file
    does not exist or reading fails.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except Exception:
        return default if default is not None else {}


def _write_json(path: str, data: Any) -> None:
    """Write *data* as JSON to *path* using UTF-8 and two spaces indent."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
