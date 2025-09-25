"""Helpers for reading and writing tool files and dictionaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping

from config.paths import get_path, join_path

JSON_INDENT = 2
JSON_ENCODING = "utf-8"

TOOL_DICTIONARY_KEYS: Mapping[str, str] = {
    "types": "tools.types_file",
    "statuses": "tools.statuses_file",
    "tasks": "tools.task_templates_file",
}

TOOL_DICTIONARY_ALIASES: Mapping[str, str] = {
    "typy": "types",
    "statusy": "statuses",
    "szablony": "tasks",
    "templates": "tasks",
}


def tools_directory() -> Path:
    base = get_path("paths.tools_dir") or "narzedzia"
    return Path(base)


def ensure_tools_dir() -> Path:
    path = tools_directory()
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_tool_id(tool_id: str | int) -> str:
    text = str(tool_id).strip()
    if not text:
        raise ValueError("tool_id cannot be empty")
    return text.zfill(3)


def tool_path(tool_id: str | int) -> Path:
    tid = normalize_tool_id(tool_id)
    return Path(join_path("paths.tools_dir", f"{tid}.json"))


def iter_tool_files(pattern: str = "*.json") -> Iterator[Path]:
    directory = tools_directory()
    if not directory.exists():
        return iter(())
    return iter(sorted(directory.glob(pattern)))


def load_tool(tool_id: str | int) -> Dict[str, Any] | None:
    path = tool_path(tool_id)
    try:
        with path.open("r", encoding=JSON_ENCODING) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def save_tool(tool_id: str | int, tool_data: Mapping[str, Any]) -> Path:
    path = tool_path(tool_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(tool_data)
    payload.setdefault("numer", normalize_tool_id(tool_id))
    with path.open("w", encoding=JSON_ENCODING) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=JSON_INDENT)
    return path


def delete_tool(tool_id: str | int) -> bool:
    path = tool_path(tool_id)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _dictionary_key(name: str) -> str:
    key = name.strip().lower()
    alias = TOOL_DICTIONARY_ALIASES.get(key, key)
    if alias not in TOOL_DICTIONARY_KEYS:
        raise KeyError(f"Unknown dictionary name: {name}")
    return TOOL_DICTIONARY_KEYS[alias]


def dictionary_path(name: str) -> Path:
    cfg_key = _dictionary_key(name)
    return Path(get_path(cfg_key))


def list_dictionary_files() -> Dict[str, Path]:
    return {alias: Path(get_path(cfg_key)) for alias, cfg_key in TOOL_DICTIONARY_KEYS.items()}


def load_dictionary(name: str, default: Any = None) -> Any:
    path = dictionary_path(name)
    try:
        with path.open("r", encoding=JSON_ENCODING) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {} if default is None else default
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default
    return data


def save_dictionary(name: str, data: Any) -> Path:
    path = dictionary_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=JSON_ENCODING) as fh:
        json.dump(data, fh, ensure_ascii=False, indent=JSON_INDENT)
    return path
