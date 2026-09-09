# version: 1.1
# Zmiany 1.1:
# - find_type() ustawia jawny visit_base logicznie jako pierwszy status w pamięci,
#   bez zmiany kolejności zapisanej w pliku JSON.
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

from config.paths import p_tools_defs


DEFAULT_CONFIG: Dict[str, Any] = {
    "collections": {"NN": {"types": []}, "SN": {"types": []}}
}


def _candidate_paths(definitions_path: str | None = None) -> List[str]:
    """Return ordered list of candidate paths for the tools definitions file."""

    candidates: List[str] = []

    def _add(path: str | None) -> None:
        if not path:
            return
        norm = os.path.normpath(path)
        if norm not in candidates:
            candidates.append(norm)

    _add(definitions_path)

    cfg_mgr = None
    try:
        from config_manager import ConfigManager

        cfg_mgr = ConfigManager()
    except Exception:
        cfg_mgr = None

    if cfg_mgr is not None:
        try:
            _add(str(cfg_mgr.path_data("narzedzia", "szablony_zadan.json")))
        except Exception:
            pass
        try:
            _add(str(p_tools_defs(cfg_mgr)))
        except Exception:
            pass
        for key in (
            "tools.task_templates_file",
            "tools.definitions_path",
            "tools.task_templates",
        ):
            try:
                value = cfg_mgr.get(key, None)
            except Exception:
                value = None
            if isinstance(value, str):
                _add(value)
        try:
            data = cfg_mgr.load() or {}
        except Exception:
            data = {}
        if isinstance(data, dict):
            paths = data.get("paths") or {}
            tools = data.get("tools") or {}
            if isinstance(paths, dict):
                _add(paths.get("tools.task_templates_file"))
            if isinstance(tools, dict):
                _add(tools.get("task_templates_file"))
                _add(tools.get("definitions_path"))

    if not candidates:
        _add(str(Path("zadania_narzedzia.json").resolve()))
    return candidates


def _count_definitions(payload: Dict[str, Any]) -> tuple[int, int, int]:
    collections = payload.get("collections") or payload.get("kolekcje") or {}
    if not isinstance(collections, dict):
        return (0, 0, 0)
    total_types = 0
    total_statuses = 0
    total_tasks = 0
    for collection in collections.values():
        if not isinstance(collection, dict):
            continue
        types = collection.get("types") or collection.get("typy") or []
        if isinstance(types, dict):
            types_iter = types.values()
        elif isinstance(types, list):
            types_iter = types
        else:
            types_iter = []
        for tool_type in types_iter:
            if not isinstance(tool_type, dict):
                continue
            total_types += 1
            statuses = tool_type.get("statuses") or tool_type.get("statusy") or []
            if isinstance(statuses, dict):
                statuses_iter = statuses.values()
            elif isinstance(statuses, list):
                statuses_iter = statuses
            else:
                statuses_iter = []
            for status in statuses_iter:
                if not isinstance(status, dict):
                    continue
                total_statuses += 1
                tasks = status.get("tasks") or status.get("zadania") or []
                if isinstance(tasks, list):
                    total_tasks += len(tasks)
    return (total_types, total_statuses, total_tasks)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write_atomic(path: str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp_{int(time.time() * 1000)}")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, target)


def _sanitize_json(text: str) -> str:
    text = text.lstrip("\ufeff")
    text = re.sub(r"//[^\n\r]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r"([\[{]\s*),", r"\1", text)
    return text


def _try_load(text: str) -> Dict[str, Any]:
    return json.loads(text) if text.strip() else {}


def _normalize_payload(data: Any) -> Dict[str, Any] | None:
    if isinstance(data, dict):
        return data
    print(
        "[WARNING] Nieprawidłowy format definicji zadań narzędzi "
        f"(oczekiwano obiektu, otrzymano {type(data).__name__})."
    )
    return None


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
    candidates = _candidate_paths(definitions_path)
    if not candidates and definitions_path:
        candidates.append(definitions_path)
    root_path = candidates[1] if len(candidates) > 1 else (candidates[0] if candidates else "")
    resolved_root = os.path.abspath(root_path) if root_path else root_path
    if not root_path or not os.path.exists(root_path):
        path = next((c for c in candidates if c and os.path.exists(c)), "")
    else:
        path = root_path
    if not path or not os.path.exists(path):
        resolved = os.path.abspath(path) if path else path
        print(f"[WM-DBG][TOOLS] definicje z pliku: {resolved}")
        print(f"[WARNING] Brak pliku definicji – ścieżka: {resolved}")
        return DEFAULT_CONFIG
    analyzed: list[tuple[str, Dict[str, Any], tuple[int, int, int]]] = []
    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        try:
            payload = _normalize_payload(_try_load(_read_text(candidate)))
            if payload is None:
                continue
            analyzed.append((candidate, payload, _count_definitions(payload)))
        except Exception:
            continue
    chosen = next((item for item in analyzed if os.path.abspath(item[0]) == os.path.abspath(root_path)), None)
    legacy_best = max(analyzed, key=lambda item: item[2][2]) if analyzed else None
    if chosen is not None and chosen[2][2] == 0 and legacy_best is not None and legacy_best[2][2] > 0 and os.path.abspath(legacy_best[0]) != os.path.abspath(root_path):
        if os.path.exists(root_path):
            backup = f"{root_path}.bak.{int(time.time())}.json"
            shutil.copy2(root_path, backup)
        _write_atomic(root_path, json.dumps(legacy_best[1], ensure_ascii=False, indent=2))
        print(
            "[WM-DBG][TOOLS] zmigrowano pełniejsze definicje: "
            f"{os.path.abspath(legacy_best[0])} -> {resolved_root}"
        )
        chosen = (root_path, legacy_best[1], legacy_best[2])
    if chosen is None and legacy_best is not None:
        chosen = legacy_best
    if chosen is not None:
        path, payload, counts = chosen
        print(
            "[WM-DBG][TOOLS] wybrano definicje: "
            f"{os.path.abspath(path)} typy={counts[0]} statusy={counts[1]} zadania={counts[2]}"
        )
        if counts[2] == 0:
            print(
                "[WARNING] Brak zadań w pliku ROOT i legacy. "
                "Uzupełnij szablony w Ustawienia → Narzędzia."
            )
        return payload
    path = next((c for c in candidates if c and os.path.exists(c)), "")
    try:
        raw = _read_text(path)
        fixed = _sanitize_json(raw)
        data = _normalize_payload(_try_load(fixed))
        path_name = os.path.basename(path)
        if data is None:
            return DEFAULT_CONFIG
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
        if isinstance(backup, dict):
            return backup
        return DEFAULT_CONFIG


def _normalize_type_key(value: str) -> str:
    """Return normalized key for comparing tool type identifiers."""

    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def get_types(cfg: Dict[str, Any], collection: str) -> List[Dict[str, Any]]:
    try:
        types = cfg["collections"][collection]["types"]
    except (KeyError, TypeError):
        return []
    return list(types or [])


def _put_visit_base_first(tool_type: Dict[str, Any]) -> None:
    """Ustaw visit_base jako pierwszy status tylko w bieżącym obiekcie w pamięci."""

    statuses = tool_type.get("statuses")
    if not isinstance(statuses, list) or len(statuses) < 2:
        return
    base_idx = None
    for idx, status in enumerate(statuses):
        if isinstance(status, dict) and bool(status.get("visit_base")):
            base_idx = idx
            break
    if base_idx is None or base_idx == 0:
        return
    base = statuses[base_idx]
    tool_type["statuses"] = [base] + statuses[:base_idx] + statuses[base_idx + 1 :]


def find_type(cfg: Dict[str, Any], collection: str, type_name: str) -> Dict[str, Any] | None:
    target = _normalize_type_key(type_name)
    for tool_type in get_types(cfg, collection):
        name_norm = _normalize_type_key(tool_type.get("name") or "")
        id_norm = _normalize_type_key(tool_type.get("id") or "")
        id_base_norm = _normalize_type_key(str(tool_type.get("id") or "").rstrip("0123456789"))
        aliases = tool_type.get("aliases") or []
        alias_norm = {_normalize_type_key(alias) for alias in aliases if isinstance(alias, str)}

        if target in {name_norm, id_norm, id_base_norm} | alias_norm:
            _put_visit_base_first(tool_type)
            return tool_type
    return None


def get_status_names_for_type(cfg: Dict[str, Any], collection: str, type_name: str) -> List[str]:
    tool_type = find_type(cfg, collection, type_name)
    if not tool_type:
        return []
    statuses = tool_type.get("statuses") or []
    result = []
    for status in statuses:
        if isinstance(status, dict):
            value = status.get("name") or status.get("id") or str(status)
        else:
            value = str(status)
        value = value.strip()
        if value:
            result.append(value)
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
