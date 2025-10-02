#!/usr/bin/env python3
# tools/merge_machines_json.py
# SAFE MERGE: łączy listy maszyn z wielu plików do docelowego, deduplikuje po
# kluczach (id→kod→nazwa), NIE usuwa nic unikalnego. Obsługuje --dry-run,
# backup docelowego i raport.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from typing import Any, Dict, Iterable, List, Tuple


def _load_list(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # dopuszczamy format { "items": [...] }
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
        print(f"[WARN] {path}: nieobsługiwany format – pomijam (nie lista)")
        return []
    except Exception as exc:  # pragma: no cover - tylko logging
        print(f"[WARN] {path}: nie da się wczytać: {exc}")
        return []


def _norm(value: Any) -> str:
    return str(value).strip().lower()


def _make_key(obj: Dict[str, Any]) -> Tuple[str, str]:
    # priorytet: id → kod → nazwa
    for key in ("id", "ID"):
        if obj.get(key) not in (None, ""):
            return "id", _norm(obj[key])
    for key in ("kod", "code"):
        if obj.get(key) not in (None, ""):
            return "kod", _norm(obj[key])
    for key in ("nazwa", "name"):
        if obj.get(key) not in (None, ""):
            return "nazwa", _norm(obj[key])
    # ostateczność: hash całego obiektu
    digest = hashlib.sha1(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return "hash", digest


def _richness(obj: Dict[str, Any]) -> int:
    return sum(1 for value in obj.values() if value not in (None, "", " "))


def _union_merge(
    inputs: Iterable[str],
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Dict[str, Any], Dict[str, Any], str]]]:
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    conflicts: List[Tuple[str, Dict[str, Any], Dict[str, Any], str]] = []

    for src in inputs:
        items = _load_list(src)
        for obj in items:
            key = _make_key(obj)
            if key in merged:
                if merged[key] != obj:
                    conflicts.append((f"{key[0]}:{key[1]}", merged[key], obj, src))
                    if _richness(obj) > _richness(merged[key]):
                        merged[key] = obj
            else:
                merged[key] = obj

    return list(merged.values()), conflicts


def _backup(path: str) -> str | None:
    base, ext = os.path.splitext(path)
    idx = 1
    while True:
        candidate = f"{base}.bak{idx}{ext or '.json'}"
        if not os.path.exists(candidate):
            if os.path.exists(path):
                shutil.copy2(path, candidate)
            return candidate
        idx += 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SAFE merge machines JSON (UNION; no deletion of uniques)"
    )
    parser.add_argument("output", help="Docelowy plik JSON (ze źródła prawdy)")
    parser.add_argument(
        "inputs", nargs="+", help="Pliki wejściowe do scalenia (co najmniej 1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Tylko raport – nie zapisuje output"
    )
    parser.add_argument(
        "--sort-by",
        choices=["id", "kod", "nazwa", "none"],
        default="id",
        help="Sortowanie wyniku",
    )
    args = parser.parse_args()

    output_path = os.path.normpath(args.output)
    input_paths = [
        os.path.normpath(path)
        for path in args.inputs
        if os.path.exists(path)
    ]

    if not input_paths:
        print("[ERR] Brak istniejących plików wejściowych.")
        sys.exit(2)

    if os.path.exists(output_path):
        union_sources = [output_path, *input_paths]
        target_existing = _load_list(output_path)
    else:
        union_sources = input_paths
        target_existing = []

    merged, conflicts = _union_merge(union_sources)

    # Sortowanie wyniku:
    if args.sort_by in ("id", "kod", "nazwa"):
        def sort_key(obj: Dict[str, Any]) -> str:
            for key in ("id", "ID", "kod", "code", "nazwa", "name"):
                if obj.get(key) not in (None, "", " "):
                    return _norm(obj[key])
            return ""

        merged = sorted(merged, key=sort_key)

    # Raport
    total_inputs = sum(len(_load_list(path)) for path in input_paths)
    print(
        f"[MERGE][SAFE] wejście: {len(input_paths)} plików, "
        f"rekordów={total_inputs}"
    )
    print(f"[MERGE][SAFE] target pre-exist: {len(target_existing)}")
    print(f"[MERGE][SAFE] wynik (po UNION): {len(merged)}")
    if conflicts:
        print(f"[MERGE][SAFE] konflikty: {len(conflicts)} (pokazuję do 20):")
        for idx, (key, a_obj, b_obj, src) in enumerate(conflicts[:20], 1):
            print(f"  {idx:02d}. KEY={key} ← konflikt z {src}")

    if args.dry_run:
        print("[MERGE][SAFE] DRY-RUN – nic nie zapisano.")
        return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    backup_path = _backup(output_path)
    if backup_path:
        print(f"[MERGE][SAFE] backup targetu → {backup_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[MERGE][SAFE] zapisano → {output_path}")


if __name__ == "__main__":
    main()
