#!/usr/bin/env python3
"""Narządzie do bezpiecznego łączenia plików maszyn (operacja UNION)."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any


def load_any(path: str) -> list[dict[str, Any]]:
    """Załaduj dane z JSON-a (lista lub słownik z kluczem ``items``)."""

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [copy.deepcopy(row) for row in data["items"] if isinstance(row, dict)]
    if isinstance(data, list):
        return [copy.deepcopy(row) for row in data if isinstance(row, dict)]
    raise ValueError(f"Nieobsługiwany format: {path}")


def dump_list(path: str, items: list[dict[str, Any]]) -> None:
    """Zapisz listę słowników jako JSON z wcięciem 2 spacji."""

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=False, indent=2)


def _key_of(item: dict[str, Any], key: str, index: int, prefix: str) -> str:
    value = item.get(key)
    if value is None or value == "":
        return f"{prefix}{index}"
    return str(value)


def merge_union(
    dst_items: list[dict[str, Any]],
    src_items: list[dict[str, Any]],
    *,
    key: str = "id",
) -> tuple[list[dict[str, Any]], int, int]:
    """Połącz listy bez utraty danych (UNION)."""

    by_key: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(dst_items):
        by_key[_key_of(item, key, index, "__idx_")] = copy.deepcopy(item)

    added = 0
    updated = 0
    for index, src in enumerate(src_items):
        src_key = src.get(key)
        normalized_key = str(src_key) if src_key not in (None, "") else None
        if normalized_key and normalized_key in by_key:
            dst = by_key[normalized_key]
            for field, value in src.items():
                if field not in dst or (dst[field] in ("", None) and value not in ("", None)):
                    dst[field] = copy.deepcopy(value)
                    updated += 1
            continue
        generated_key = normalized_key or _key_of(src, key, len(by_key), "__new_")
        by_key[generated_key] = copy.deepcopy(src)
        added += 1

    return list(by_key.values()), added, updated


def backup_path(path: str) -> str:
    base, ext = os.path.splitext(path)
    counter = 1
    while True:
        candidate = f"{base}.bak{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SAFE MERGE maszyn: UNION bez utraty danych",
    )
    parser.add_argument("target", help="Plik docelowy (źródło prawdy)")
    parser.add_argument("sources", nargs="+", help="Pliki do dołączenia")
    parser.add_argument("--key", default="id", help="Klucz identyfikujący rekord (domyślnie id)")
    parser.add_argument("--dry-run", action="store_true", help="Tylko raportuj wynik")
    args = parser.parse_args(argv)

    target_path = args.target
    target_items = load_any(target_path) if os.path.exists(target_path) else []

    merged = target_items
    total_added = 0
    total_updated = 0
    for source in args.sources:
        source_items = load_any(source)
        merged, added, updated = merge_union(merged, source_items, key=args.key)
        total_added += added
        total_updated += updated

    if args.dry_run:
        print(
            f"[DRY] target={target_path} out={len(merged)} "
            f"(added={total_added}, updated={total_updated})",
        )
        return 0

    if os.path.exists(target_path):
        backup = backup_path(target_path)
        os.replace(target_path, backup)
        print(f"[BACKUP] {backup}")

    dump_list(target_path, merged)
    print(
        f"[WRITE] {target_path} out={len(merged)} "
        f"(added={total_added}, updated={total_updated})",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - narzędzie CLI
    sys.exit(main())
