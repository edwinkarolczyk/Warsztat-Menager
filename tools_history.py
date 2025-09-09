"""Utilities for tracking tool history in JSON Lines format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def append_tool_history(path: Path, entry: Dict[str, Any]) -> None:
    """Append ``entry`` as a JSON line to ``path``.

    Parameters
    ----------
    path:
        Destination file. Parents are created automatically.
    entry:
        Mapping that will be serialised to JSON. ``ensure_ascii`` is disabled
        to preserve any non ASCII characters.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        json.dump(entry, fh, ensure_ascii=False)
        fh.write("\n")
