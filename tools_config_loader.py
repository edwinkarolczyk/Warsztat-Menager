from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def load_config(definitions_path: str | None = None) -> Dict[str, Any]:
    path = definitions_path or "data/zadania_narzedzia.json"
    if not os.path.exists(path):
        return {"collections": {"NN": {"types": []}, "SN": {"types": []}}}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh) or {}


def get_types(cfg: Dict[str, Any], collection: str) -> List[Dict[str, Any]]:
    try:
        types = cfg["collections"][collection]["types"]
    except (KeyError, TypeError):
        return []
    return list(types or [])


def find_type(cfg: Dict[str, Any], collection: str, type_name: str) -> Dict[str, Any] | None:
    target = (type_name or "").strip().lower()
    for tool_type in get_types(cfg, collection):
        if (tool_type.get("name") or "").strip().lower() == target:
            return tool_type
    return None


def get_status_names_for_type(cfg: Dict[str, Any], collection: str, type_name: str) -> List[str]:
    tool_type = find_type(cfg, collection, type_name)
    if not tool_type:
        return []
    statuses = tool_type.get("statuses") or []
    result = []
    for status in statuses:
        result.append(status.get("name") or "")
    return result


def get_tasks_for_status(
    cfg: Dict[str, Any],
    collection: str,
    type_name: str,
    status_name: str,
) -> List[str]:
    tool_type = find_type(cfg, collection, type_name)
    if not tool_type:
        return []
    target = (status_name or "").strip().lower()
    for status in tool_type.get("statuses") or []:
        if (status.get("name") or "").strip().lower() == target:
            return [str(task) for task in (status.get("tasks") or [])]
    return []
