"""Utilities for reading tool templates.

This module provides :func:`load_templates` which reads JSON files
representing tool templates. Each template must contain a unique ``id``
field. The loader enforces a maximum of 64 templates (8×8 limit) and will
skip missing files gracefully. If duplicate ``id`` values are encountered
or the limit is exceeded a :class:`ValueError` is raised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Any

MAX_TEMPLATES = 64  # 8x8 limit


def load_templates(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    """Load templates from ``paths``.

    Parameters
    ----------
    paths:
        An iterable of file system paths pointing to JSON files. Missing
        files are ignored.

    Returns
    -------
    list of dict
        Parsed templates.

    Raises
    ------
    ValueError
        If more than :data:`MAX_TEMPLATES` templates are loaded or
        duplicate ``id`` values are encountered.
    """
    templates: Dict[str, Dict[str, Any]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            # Gracefully ignore missing files.
            continue
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        template_id = data.get("id")
        if template_id is None:
            raise ValueError("template missing 'id'")
        if template_id in templates:
            raise ValueError(f"duplicate template id: {template_id}")
        templates[template_id] = data
        if len(templates) > MAX_TEMPLATES:
            raise ValueError("too many templates (limit 64)")
    return list(templates.values())
