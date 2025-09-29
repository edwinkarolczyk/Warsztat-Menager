# -*- coding: utf-8 -*-
"""RC1 Audit+: rozszerzenie audytu o dodatkowe reguły z pliku JSON."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Tuple

from backend.audit import wm_audit_runtime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT_DIR, "data", "audyt_plus.json")

Check = Dict[str, Any]
Result = Dict[str, Any]


def _load_rules() -> Tuple[str, List[Dict[str, Any]], str | None]:
    """Odczytuje konfigurację reguł z pliku JSON."""

    title = "Audit+ RC1"
    if not os.path.exists(DATA_PATH):
        return title, [], "Plik data/audyt_plus.json nie istnieje."
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - sytuacja awaryjna
        return title, [], f"Błąd JSON: {exc}"
    except OSError as exc:  # pragma: no cover - sytuacja awaryjna
        return title, [], f"Błąd odczytu: {exc}"

    if isinstance(data, dict):
        title = str(data.get("title") or title)
        rules = data.get("rules")
        if isinstance(rules, list):
            parsed: List[Dict[str, Any]] = []
            for item in rules:
                if isinstance(item, dict):
                    parsed.append(item)
            return title, parsed, None
    return title, [], "Nieprawidłowa struktura pliku audyt_plus.json."  # pragma: no cover


def _resolve_path(root: str, value: str) -> str:
    if os.path.isabs(value):
        return value
    return os.path.normpath(os.path.join(root, value))


def _check_rule(root: str, rule: Dict[str, Any]) -> Check:
    rtype = str(rule.get("type") or "path").lower()
    label = str(
        rule.get("label")
        or rule.get("name")
        or rule.get("path")
        or rule.get("key")
        or "rule"
    )
    detail = ""
    ok = True

    if rtype == "path":
        path_value = rule.get("path")
        if not isinstance(path_value, str):
            ok = False
            detail = "Brak ścieżki dla reguły typu 'path'."
        else:
            resolved = _resolve_path(root, path_value)
            ok = os.path.exists(resolved)
            detail = resolved
    elif rtype == "config_path":
        key = rule.get("key") or rule.get("path")
        from config.paths import get_path  # lokalny import (lazy)

        if not isinstance(key, str):
            ok = False
            detail = "Brak klucza konfiguracji dla reguły 'config_path'."
        else:
            configured = get_path(key, "")
            if configured:
                resolved = configured
                if not os.path.isabs(resolved):
                    resolved = _resolve_path(root, resolved)
                ok = os.path.exists(resolved)
                detail = resolved
            else:
                ok = False
                detail = "Brak wartości w konfiguracji."
    else:
        ok = False
        detail = f"Nieobsługiwany typ reguły: {rtype}."

    return {"name": label, "ok": ok, "detail": detail}


def _run_plus_checks(root: str) -> Result:
    title, rules, error = _load_rules()

    checks: List[Check] = []
    if error:
        checks.append({"name": title, "ok": False, "detail": error})
    for rule in rules:
        checks.append(_check_rule(root, rule))

    failed = [c for c in checks if not c.get("ok")]
    summary = (
        f"{title}: OK {len(checks) - len(failed)}/{len(checks)}; FAIL {len(failed)}"
        if checks
        else f"{title}: Brak zdefiniowanych reguł."
    )
    return {"title": title, "checks": checks, "failed": failed, "ok": not failed, "summary": summary}


def _append_section(report_path: str, lines: Iterable[str]) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _write_fresh_report(report_path: str, base_summary: str, plus: Result) -> None:
    lines = [
        f"Audyt WM — {time.strftime('%Y%m%d-%H%M%S')}",
        "=" * 40,
        base_summary or "Bazowy audyt nie zwrócił podsumowania.",
        "-" * 40,
    ]
    lines.extend(_format_checks(plus))
    _append_section(report_path, lines)


def _format_checks(result: Result) -> List[str]:
    lines = [result.get("title", "Audit+")] + ["-" * 40]
    checks = result.get("checks") or []
    if not checks:
        lines.append("Brak reguł do oceny.")
    for check in checks:
        name = check.get("name", "rule")
        ok = check.get("ok")
        detail = check.get("detail", "")
        prefix = "OK" if ok else "FAIL"
        lines.append(f"[{prefix}] {name}: {detail}")
    lines.append("-" * 40)
    lines.append(result.get("summary", ""))
    return lines


def _combine_summaries(base_summary: str, plus_summary: str) -> str:
    base_summary = base_summary or "Bazowy audyt nie zwrócił podsumowania."
    plus_summary = plus_summary or "Audit+: brak podsumowania."
    return f"{base_summary} | {plus_summary}"


def run() -> Dict[str, Any]:
    """Uruchamia audyt rozszerzony i zwraca wynik w formacie dict."""

    root = ROOT_DIR
    base_result: Dict[str, Any] = {}
    try:
        result = wm_audit_runtime.run()
        if isinstance(result, dict):
            base_result = result
        else:
            base_result = {"ok": True, "msg": str(result), "path": None}
    except Exception as exc:  # pragma: no cover - zabezpieczenie
        base_result = {"ok": False, "msg": f"Błąd audytu bazowego: {exc}", "path": None}

    plus_result = _run_plus_checks(root)

    report_path = base_result.get("path") if isinstance(base_result, dict) else None
    if report_path and isinstance(report_path, str):
        lines = ["", "Audit+ — dodatkowe kontrole", "-" * 40]
        lines.extend(_format_checks(plus_result)[2:])  # pomiń tytuł i separator
        _append_section(report_path, lines)
    else:
        report_path = os.path.join(root, "logs", f"audyt_plus-{time.strftime('%Y%m%d-%H%M%S')}.txt")
        _write_fresh_report(report_path, base_result.get("msg", ""), plus_result)

    combined_ok = bool(base_result.get("ok")) and plus_result.get("ok", False)
    combined_summary = _combine_summaries(base_result.get("msg", ""), plus_result.get("summary", ""))

    return {
        "ok": combined_ok,
        "msg": combined_summary,
        "path": report_path,
        "base": base_result,
        "plus": plus_result,
    }


def main() -> None:
    result = run()
    print(result.get("msg", "Brak podsumowania"))
    print(f"Raport: {result.get('path')}")


if __name__ == "__main__":  # pragma: no cover - uruchomienie bezpośrednie
    main()
