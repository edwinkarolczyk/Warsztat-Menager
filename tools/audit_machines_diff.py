#!/usr/bin/env python3
"""Porównanie dwóch plików maszyn na podstawie identyfikatorów."""

from __future__ import annotations

import json
import sys
from typing import Any


def load_any(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [row for row in data["items"] if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    raise ValueError(f"Nieobsługiwany format: {path}")


def ids(items: list[dict[str, Any]], key: str = "id") -> set[str]:
    return {str(item.get(key)) for item in items if item.get(key) is not None}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Użycie: py -3.13 tools\\audit_machines_diff.py <srcA.json> <srcB.json>")
        return 2

    path_a, path_b = args
    items_a = load_any(path_a)
    items_b = load_any(path_b)

    ids_a = ids(items_a)
    ids_b = ids(items_b)

    missing = sorted(ids_a - ids_b)
    new = sorted(ids_b - ids_a)

    print(f"[DIFF] A={path_a}({len(items_a)})  B={path_b}({len(items_b)})")
    print(f"[DIFF] -zniknięte={len(missing)}  +nowe={len(new)}")
    if missing:
        preview = missing[:10]
        print(f"  - {preview}{' ...' if len(missing) > 10 else ''}")
    if new:
        preview = new[:10]
        print(f"  + {preview}{' ...' if len(new) > 10 else ''}")
    return 0


if __name__ == "__main__":  # pragma: no cover - narzędzie CLI
    sys.exit(main())
