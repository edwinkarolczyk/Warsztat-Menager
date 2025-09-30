#!/usr/bin/env python3
# tools/merge_machines_json.py
# Jednorazowe scalenie wielu plików maszyn do docelowego (wg Ustawień), z logiem konfliktów.

import os, sys, json, hashlib


def _load_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[MERGE] Nie wczytano {p}: {e}")
        return []


def _key(obj):
    for k in ("id", "ID", "kod", "code", "nazwa", "name"):
        v = obj.get(k)
        if v:
            return f"{k}:{str(v).strip().lower()}"
    # fallback: hash całego obiektu (ostateczność)
    return "hash:" + hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def merge(inputs, output):
    merged = {}
    conflicts = []
    for src in inputs:
        data = _load_json(src)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if not isinstance(data, list):
            print(f"[MERGE] {src} nie zawiera listy – pomijam")
            continue
        for obj in data:
            k = _key(obj)
            if k in merged and merged[k] != obj:
                conflicts.append((k, merged[k], obj, src))
            merged[k] = obj
    items = list(merged.values())
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"[MERGE] Zapisano {len(items)} rekordów → {output}")
    if conflicts:
        print(f"[MERGE] KONFLIKTY: {len(conflicts)} (zobacz poniżej)")
        for k, a, b, src in conflicts[:20]:
            print(f" - {k} z {src}")
        if len(conflicts) > 20:
            print(" ... (ucięto listę)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Użycie: merge_machines_json.py <wyjście_docelowe.json> <wejście1.json> [wejście2.json ...]")
        sys.exit(2)
    output = sys.argv[1]
    inputs = sys.argv[2:]
    merge(inputs, output)
