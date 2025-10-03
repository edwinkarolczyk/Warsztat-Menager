#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R-03B SAFE MERGE narzędzie scalające pliki maszyn w SoT."""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import sys
from typing import Any


def _load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False


def _count_nonempty(record: dict) -> int:
    count = 0
    for value in record.values():
        if _is_empty(value):
            continue
        count += 1
    return count


def _merge_record(first: dict, second: dict) -> dict:
    """Scala dwa rekordy maszyn zgodnie z zasadą bogatszego wpisu."""

    first_score = _count_nonempty(first)
    second_score = _count_nonempty(second)
    base_source = first if first_score >= second_score else second
    other_source = second if base_source is first else first
    base = copy.deepcopy(base_source)
    other = other_source

    for key, value in other.items():
        if key not in base:
            base[key] = copy.deepcopy(value)
            continue

        base_value = base[key]

        if isinstance(base_value, list) and isinstance(value, list):
            seen: set[str] = set()
            merged: list[Any] = []
            for item in list(base_value) + list(value):
                signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if signature in seen:
                    continue
                seen.add(signature)
                merged.append(item)
            base[key] = merged
            continue

        if isinstance(base_value, dict) and isinstance(value, dict):
            merged_dict = copy.deepcopy(base_value)
            for sub_key, sub_value in value.items():
                if sub_key not in merged_dict or (
                    _is_empty(merged_dict[sub_key]) and not _is_empty(sub_value)
                ):
                    merged_dict[sub_key] = copy.deepcopy(sub_value)
            base[key] = merged_dict
            continue

        if _is_empty(base_value) and not _is_empty(value):
            base[key] = copy.deepcopy(value)

    return base


def _key(record: dict) -> tuple[int, str]:
    identifier = (record.get("id") or "").strip()
    if identifier:
        return (1, identifier)
    code = (record.get("kod") or "").strip()
    if code:
        return (2, code)
    return (9, "")


def _load_machines(path: str) -> list[dict]:
    data = _load(path)
    if isinstance(data, dict) and isinstance(data.get("maszyny"), list):
        return [row for row in data["maszyny"] if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _wrap(records: list[dict]) -> dict:
    return {"maszyny": records}


def _write_report(lines: list[str], target: str) -> None:
    root_dir = os.path.dirname(os.path.abspath(target))
    logs_dir = os.path.join(root_dir, "logs")
    if not os.path.isdir(logs_dir):
        return
    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(logs_dir, f"merge_machines_json_{timestamp}.log")
    try:
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    except Exception as exc:  # pragma: no cover - log opcjonalny
        print(f"[WARN] Nie można zapisać raportu {log_path}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SAFE MERGE machines JSON → SoT",
    )
    parser.add_argument(
        "target",
        help="Ścieżka docelowa SoT (np. C:/wm/data/maszyny.json)",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Pliki źródłowe (legacy) do scalenia",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko raport — bez zapisu",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Zrób backup targetu przed zapisem",
    )
    args = parser.parse_args(argv)

    current: list[dict] = []
    if os.path.exists(args.target):
        try:
            current = _load_machines(args.target)
        except Exception as exc:  # pragma: no cover - log przez stdout
            print(f"[WARN] Nie można wczytać targetu {args.target}: {exc}")

    merged_by_key: dict[tuple[int, str], dict] = {}

    def _add_all(items: list[dict], source_tag: str) -> None:
        for record in items:
            key_type, key_value = _key(record)
            if not key_value:
                key_value = f"__noid__::{source_tag}::{id(record)}"
                key_type = 8
            key = (key_type, key_value)
            if key not in merged_by_key:
                merged_by_key[key] = copy.deepcopy(record)
            else:
                merged_by_key[key] = _merge_record(merged_by_key[key], record)

    _add_all(current, "TARGET")

    for source in args.sources:
        try:
            records = _load_machines(source)
        except Exception as exc:
            print(f"[ERR] Nie można wczytać {source}: {exc}")
            continue
        _add_all(records, os.path.basename(source))

    final_records = [merged_by_key[key] for key in sorted(merged_by_key.keys())]

    def _signature(record: dict) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True)

    current_signatures = {
        _key(record): _signature(record) for record in current
    }

    added = [
        key for key in merged_by_key.keys() if key not in current_signatures
    ]
    changed = [
        key
        for key, record in merged_by_key.items()
        if key in current_signatures
        and current_signatures[key] != _signature(record)
    ]

    report_lines = [
        "=== R-03B SAFE MERGE REPORT ===",
        f"target     : {args.target}",
        f"sources    : {', '.join(args.sources)}",
        f"current    : {len(current)} rec",
        f"final      : {len(final_records)} rec",
        f"added      : {len(added)} rec",
        f"changed    : {len(changed)} rec",
    ]

    for line in report_lines:
        print(line)

    if args.dry_run:
        print("[DRY-RUN] Brak zapisu.")
        _write_report(report_lines + ["[DRY-RUN] Brak zapisu."], args.target)
        return 0

    target_dir = os.path.dirname(os.path.abspath(args.target)) or "."
    os.makedirs(target_dir, exist_ok=True)

    if args.backup and os.path.exists(args.target):
        timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{args.target}.bak-{timestamp}"
        try:
            with open(args.target, "rb") as source_handle, open(
                backup_path, "wb"
            ) as backup_handle:
                backup_handle.write(source_handle.read())
            print(f"[BACKUP] {backup_path}")
        except Exception as exc:
            print(f"[WARN] backup failed: {exc}")

    with open(args.target, "w", encoding="utf-8") as handle:
        json.dump(_wrap(final_records), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("[OK] zapisano SoT.")
    _write_report(report_lines + ["[OK] zapisano SoT."], args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
