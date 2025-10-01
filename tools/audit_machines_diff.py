#!/usr/bin/env python3
# tools/audit_machines_diff.py
# Porównuje dwa pliki JSON z maszynami i raportuje:
#  - ile rekordów wspólnych,
#  - ile nowych,
#  - ile zniknęło (powinno być 0 przy SAFE-merge),
#  - konflikty wartości (po kluczu id/kod/nazwa).

import os, json, sys, hashlib

def _load_list(p):
    try:
        with open(p,"r",encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "items" in d: d = d["items"]
        return d if isinstance(d, list) else []
    except Exception:
        return []

def _norm(v): return str(v).strip().lower()

def _key(o):
    for k in ("id","ID","kod","code","nazwa","name"):
        if o.get(k): return f"{k}:{_norm(o[k])}"
    return "hash:"+hashlib.sha1(json.dumps(o,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()

def diff(a_path, b_path):
    A = _load_list(a_path); B = _load_list(b_path)
    Amap = {_key(o):o for o in A}; Bmap = {_key(o):o for o in B}
    common = set(Amap) & set(Bmap)
    added  = [k for k in Bmap if k not in Amap]
    gone   = [k for k in Amap if k not in Bmap]
    changed= [k for k in common if Amap[k]!=Bmap[k]]
    print(f"[DIFF] A={len(A)}  B={len(B)}  wspólne={len(common)}  +nowe={len(added)}  -znikniete={len(gone)}  zmienione={len(changed)}")
    if gone:
        print("[DIFF][ALERT] Zniknięte klucze (powinno być 0 w SAFE-merge):")
        for k in gone[:20]: print(" -",k)
    if changed:
        print("[DIFF] Zmienione wpisy (do 20):")
        for k in changed[:20]: print(" -",k)

if __name__ == "__main__":
    if len(sys.argv)!=3:
        print("Użycie: audit_machines_diff.py <stary.json> <nowy.json>")
        sys.exit(2)
    diff(sys.argv[1], sys.argv[2])
