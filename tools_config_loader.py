from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time
from typing import Any, Dict, List


DEFAULT_CONFIG: Dict[str, Any] = {
    "collections": {"NN": {"types": []}, "SN": {"types": []}}
}


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write_atomic(path: str, text: str) -> None:
    tmp = f"{path}.tmp_{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _sanitize_json(text: str) -> str:
    text = text.lstrip("\ufeff")
    text = re.sub(r"//[^\n\r]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r"([\[{]\s*),", r"\1", text)
    return text


def _try_load(text: str) -> Dict[str, Any]:
    return json.loads(text) if text.strip() else {}


def _restore_latest_backup(path: str) -> Dict[str, Any] | None:
    pattern = f"{path}.bak.*.json"
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    for candidate in files:
        try:
            data = _try_load(_read_text(candidate))
            candidate_name = os.path.basename(candidate)
            print(
                "[WARNING] Przywrócono definicje z backupu: "
                f"{candidate_name}"
            )
            _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
            return data
        except Exception:
            continue
    return None


def load_config(definitions_path: str | None = None) -> Dict[str, Any]:
    path = definitions_path or "data/zadania_narzedzia.json"
    if not os.path.exists(path):
        return DEFAULT_CONFIG
    try:
        return _try_load(_read_text(path)) or {}
    except Exception:
        try:
            raw = _read_text(path)
            fixed = _sanitize_json(raw)
            data = _try_load(fixed)
            path_name = os.path.basename(path)
            print(
                "[WARNING] Auto-heal definicji: "
                f"{path_name} (naprawiono format JSON)."
            )
            corrupt = f"{path}.corrupt.{int(time.time())}.json"
            try:
                shutil.copy2(path, corrupt)
            except Exception:
                pass
            _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))
            return data
        except Exception as exc:
            print("[ERROR] Nie można wczytać definicji (strict ani sanitize):", exc)
            backup = _restore_latest_backup(path)
            if backup is not None:
                return backup
            return {}


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
