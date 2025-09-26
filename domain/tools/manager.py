from __future__ import annotations

import json
import os
from typing import Any, Dict

from config.paths import join_path
from wm_log import dbg as wm_dbg
from wm_log import err as wm_err


def save_tool(tool_id: str, tool_data: Dict[str, Any]) -> bool:
    """Persist tool definition into the tools storage directory."""
    try:
        dst = join_path("paths.tools_dir", f"{tool_id}.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as file:
            json.dump(tool_data, file, ensure_ascii=False, indent=2)
        wm_dbg("tools.save", "written", path=dst)
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        wm_err("tools.save", "write failed", exc, tool_id=tool_id)
        return False
