"""Helpers for determining if a tool should be automatically checked."""

from __future__ import annotations

from typing import Dict, Any, Set

# Global set of tool identifiers that require auto checking when
# no explicit flag is provided.
AUTOCHECK_IDS: Set[str] = set()

def should_autocheck(tool: Dict[str, Any]) -> bool:
    """Return ``True`` when ``tool`` should be auto checked.

    Precedence rules:
    1. ``tool`` may contain an explicit ``autocheck`` boolean flag. When
       present it takes precedence over global settings.
    2. Otherwise, if the tool's ``id`` is present in :data:`AUTOCHECK_IDS`
       the function returns ``True``.
    3. If none of the above apply the function returns ``False``.
    """
    flag = tool.get("autocheck")
    if flag is not None:
        return bool(flag)
    tool_id = tool.get("id")
    return tool_id in AUTOCHECK_IDS
