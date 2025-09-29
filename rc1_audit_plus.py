# -*- coding: utf-8 -*-
"""RC1 Audit+ — rozszerzenie audytu o dodatkowe, konfigurowalne testy."""

from __future__ import annotations

import datetime
import json
import os


ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")


def _norm(path):
    if not path:
        return None
    return os.path.normpath(str(path).strip().strip('"').strip("'"))


def _load_cfg() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:  # pragma: no cover - config optional
        return {}


def _dget(data: dict, dotted: str):
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _data_root(cfg: dict) -> str:
    paths = cfg.get("paths") or {}
    return (
        _norm(paths.get("data_root"))
        or _norm(cfg.get("data_root"))
        or os.path.join(ROOT, "data")
    )


def _logs_dir(cfg: dict) -> str:
    base = _data_root(cfg)
    path = os.path.join(base, "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)


def _ensure_rules_file(path: str):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    default_rules = {
        "version": 1,
        "checks": [
            {
                "id": "warehouse.stock_source.exists",
                "type": "config_path_exists",
                "config_key": "warehouse.stock_source",
                "label": "Magazyn: plik magazyn.json istnieje",
                "required": True,
            },
            {
                "id": "bom.file.exists",
                "type": "config_path_exists",
                "config_key": "bom.file",
                "label": "BOM: plik bom.json istnieje",
                "required": True,
            },
            {
                "id": "tools.types_file.json",
                "type": "json_file_readable",
                "config_key": "tools.types_file",
                "label": "Narzędzia: typy_narzedzi.json OK",
                "required": True,
                "allow_empty": True,
            },
            {
                "id": "tools.statuses_file.json",
                "type": "json_file_readable",
                "config_key": "tools.statuses_file",
                "label": "Narzędzia: statusy_narzedzi.json OK",
                "required": True,
                "allow_empty": True,
            },
            {
                "id": "tools.task_templates_file.json",
                "type": "json_file_readable",
                "config_key": "tools.task_templates_file",
                "label": "Narzędzia: szablony_zadan.json OK",
                "required": True,
                "allow_empty": True,
            },
            {
                "id": "profiles.file.exists",
                "type": "config_path_exists",
                "config_key": "profiles.file",
                "label": "Użytkownicy: profiles.json istnieje",
                "required": True,
            },
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(default_rules, handle, ensure_ascii=False, indent=2)


def _get_config_path(cfg: dict, dotted_key: str) -> str | None:
    if dotted_key == "bom.file":
        bom_cfg = _dget(cfg, "bom")
        bom_path = None
        if isinstance(bom_cfg, dict):
            bom_path = bom_cfg.get("file")
        return _norm(_dget(cfg, "bom.file") or cfg.get("bom.file") or bom_path)
    return _norm(_dget(cfg, dotted_key))


def _run_one_check(cfg: dict, check: dict) -> tuple[bool, str]:
    check_type = check.get("type")
    label = check.get("label") or check.get("id", "check")
    required = bool(check.get("required", True))
    config_key = check.get("config_key")
    allow_empty = bool(check.get("allow_empty", False))

    try:
        if check_type == "config_path_exists":
            path = _get_config_path(cfg, config_key)
            exists = _exists(path)
            status = "OK" if exists else "FAIL"
            return exists, f"[{status}] {label}: {path or '(brak)'}"

        if check_type == "json_file_readable":
            path = _get_config_path(cfg, config_key)
            if not _exists(path):
                return False, f"[FAIL] {label}: brak pliku ({path})"
            try:
                data = _read_json(path)
                if not allow_empty:
                    if isinstance(data, list) and not data:
                        return False, f"[FAIL] {label}: plik pusty ({path})"
                    if isinstance(data, dict) and not data:
                        return False, f"[FAIL] {label}: plik pusty ({path})"
                return True, f"[OK] {label}: {path}"
            except Exception as exc:  # pragma: no cover - file errors
                return False, f"[FAIL] {label}: błąd JSON ({exc})"

        return True, f"[OK] {label}: (pominięto nieznany typ)"
    except Exception as exc:  # pragma: no cover - defensive
        status = "WARN" if not required else "FAIL"
        return not required, f"[{status}] {label}: wyjątek {exc}"


def run(rules_path: str | None = None) -> dict:
    cfg = _load_cfg()
    logs_dir = _logs_dir(cfg)
    rules_path = rules_path or os.path.join(ROOT, "data", "audyt_plus.json")
    _ensure_rules_file(rules_path)

    base_ok = True
    base_ok_cnt = 0
    base_total = 0
    base_path = None
    try:
        import audit  # type: ignore

        run_base = getattr(audit, "run", None)
        if callable(run_base):
            base_result = run_base() or {}
            base_msg = str(base_result.get("msg", ""))
            base_path = base_result.get("path")
            if base_msg.startswith("OK:"):
                try:
                    part = base_msg.split(";")[0].replace("OK:", "").strip()
                    ok_str, total_str = [value.strip() for value in part.split("/")]
                    base_ok_cnt = int(ok_str)
                    base_total = int(total_str)
                    base_ok = base_ok_cnt == base_total
                except Exception:  # pragma: no cover - heuristic fallback
                    pass
    except Exception:  # pragma: no cover - audit optional
        pass

    plus_cfg = _read_json(rules_path)
    checks = plus_cfg.get("checks", []) if isinstance(plus_cfg, dict) else []
    plus_ok_cnt = 0
    plus_total = 0
    plus_lines: list[str] = []
    plus_fail = 0

    for check in checks:
        ok, line = _run_one_check(cfg, check)
        plus_total += 1
        if ok:
            plus_ok_cnt += 1
        else:
            plus_fail += 1
        plus_lines.append(line)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(logs_dir, f"audyt_wm-{timestamp}_plus.txt")

    lines = [
        f"Audyt WM+ — {timestamp}",
        "=" * 40,
        f"[base]  OK: {base_ok_cnt} / {base_total}   ({'OK' if base_ok else 'PROBLEMY'})",
        f"[plus]  OK: {plus_ok_cnt} / {plus_total}   ({'OK' if plus_fail == 0 else f'FAIL:{plus_fail}'})",
        "-" * 40,
    ]
    if plus_lines:
        lines.append("[PLUS] Wyniki dodatkowe:")
        lines.extend(plus_lines)
    if base_path:
        lines.append("-" * 40)
        lines.append(f"[base] Raport bazowy: {base_path}")

    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    total_ok = base_ok and (plus_fail == 0)
    total_ok_cnt = base_ok_cnt + plus_ok_cnt
    total_total = (base_total or 0) + plus_total
    msg = f"OK: {total_ok_cnt} / {total_total}; FAIL: {total_total - total_ok_cnt}"
    return {"ok": bool(total_ok), "msg": msg, "path": out_path}

