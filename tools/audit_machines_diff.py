#!/usr/bin/env python3
# tools/audit_machines_diff.py
# Porównuje dwa pliki JSON z maszynami i raportuje:
#  - ile rekordów wspólnych,
#  - ile nowych,
#  - ile zniknęło (powinno być 0 przy SAFE-merge),
#  - konflikty wartości (po kluczu id/kod/nazwa).

import hashlib
import json
import sys
from itertools import islice
from typing import Dict, Iterable, List


def _load_list(path: str) -> List[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        return data if isinstance(data, list) else []
    except Exception:  # pragma: no cover - defensywne logowanie
        return []


def _norm(value) -> str:
    return str(value).strip().lower()


def _key(obj: Dict) -> str:
    for key in ("id", "ID", "kod", "code", "nazwa", "name"):
        if obj.get(key):
            return f"{key}:{_norm(obj[key])}"
    digest = hashlib.sha1(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"hash:{digest}"


def _first_n(values: Iterable[str], limit: int = 20) -> List[str]:
    return list(islice(values, limit))


def diff(old_path: str, new_path: str) -> None:
    old_items = _load_list(old_path)
    new_items = _load_list(new_path)

    old_map = {_key(obj): obj for obj in old_items}
    new_map = {_key(obj): obj for obj in new_items}

    common = set(old_map) & set(new_map)
    added = [key for key in new_map if key not in old_map]
    gone = [key for key in old_map if key not in new_map]
    changed = [key for key in common if old_map[key] != new_map[key]]

    print(
        "[DIFF] A={}  B={}  wspólne={}  +nowe={}  -znikniete={}  zmienione={}".format(
            len(old_items),
            len(new_items),
            len(common),
            len(added),
            len(gone),
            len(changed),
        )
    )

    if gone:
        print("[DIFF][ALERT] Zniknięte klucze (powinno być 0 w SAFE-merge):")
        for key in _first_n(gone):
            print(" -", key)

    if changed:
        print("[DIFF] Zmienione wpisy (do 20):")
        for key in _first_n(changed):
            print(" -", key)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Użycie: audit_machines_diff.py <stary.json> <nowy.json>")
        sys.exit(2)
    diff(sys.argv[1], sys.argv[2])
