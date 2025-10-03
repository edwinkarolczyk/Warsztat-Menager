#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Porównanie plików maszyn – raport różnic R-03B."""

from __future__ import annotations

import json
import sys
from typing import Any


def _load(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data: Any = json.load(handle)
    if isinstance(data, dict) and isinstance(data.get("maszyny"), list):
        return [row for row in data["maszyny"] if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _key(record: dict) -> tuple[int, str]:
    identifier = (record.get("id") or "").strip()
    if identifier:
        return (1, identifier)
    code = (record.get("kod") or "").strip()
    if code:
        return (2, code)
    return (9, "")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("Użycie: audit_machines_diff.py <A.json> <B.json>")
        return 1

    left_path, right_path = args
    try:
        left_records = _load(left_path)
    except Exception as exc:
        print(f"[ERR] Nie można wczytać {left_path}: {exc}")
        return 2
    try:
        right_records = _load(right_path)
    except Exception as exc:
        print(f"[ERR] Nie można wczytać {right_path}: {exc}")
        return 3

    left_map = {_key(record): record for record in left_records}
    right_map = {_key(record): record for record in right_records}

    only_left = sorted(set(left_map) - set(right_map))
    only_right = sorted(set(right_map) - set(left_map))
    both = sorted(set(left_map) & set(right_map))

    print("=== DIFF ===")
    print(f"A only: {len(only_left)}")
    print(f"B only: {len(only_right)}")
    print(f"both  : {len(both)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
