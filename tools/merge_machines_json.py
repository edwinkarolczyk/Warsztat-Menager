#!/usr/bin/env python3
# tools/merge_machines_json.py
# SAFE MERGE: łączy listy maszyn z wielu plików do docelowego, deduplikuje po kluczach (id→kod→nazwa),
# NIE usuwa nic unikalnego. Obsługuje --dry-run, backup docelowego i raport.

from __future__ import annotations
import os, sys, json, hashlib, argparse, shutil
from typing import Any, Dict, List, Tuple

def _load_list(p: str) -> List[Dict[str, Any]]:
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # dopuszczamy format { "items": [...] }
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
        if isinstance(data, list):
            return data
        print(f"[WARN] {p}: nieobsługiwany format – pomijam (nie lista)")
        return []
    except Exception as e:
        print(f"[WARN] {p}: nie da się wczytać: {e}")
        return []

def _norm(v: Any) -> str:
    return str(v).strip().lower()

def _make_key(obj: Dict[str, Any]) -> Tuple[str, str]:
    # priorytet: id → kod → nazwa
    for k in ("id", "ID"):
        if obj.get(k) not in (None, ""):
            return ("id", _norm(obj[k]))
    for k in ("kod", "code"):
        if obj.get(k) not in (None, ""):
            return ("kod", _norm(obj[k]))
    for k in ("nazwa", "name"):
        if obj.get(k) not in (None, ""):
            return ("nazwa", _norm(obj[k]))
    # ostateczność: hash całego obiektu
    h = hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return ("hash", h)

def _union_merge(inputs: List[str]) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Dict[str, Any], Dict[str, Any], str]]]:
    merged: Dict[Tuple[str,str], Dict[str, Any]] = {}
    conflicts: List[Tuple[str, Dict[str, Any], Dict[str, Any], str]] = []
    for src in inputs:
        items = _load_list(src)
        for obj in items:
            k = _make_key(obj)
            if k in merged:
                # jeśli różne, konflikt – ale nie nadpisujemy w ciemno
                if merged[k] != obj:
                    conflicts.append((f"{k[0]}:{k[1]}", merged[k], obj, src))
                    # strategia: preferuj "bogatszy" obiekt (więcej niepustych pól)
                    def richness(o: Dict[str,Any]) -> int:
                        return sum(1 for vv in o.values() if vv not in (None,""," "))
                    if richness(obj) > richness(merged[k]):
                        merged[k] = obj
                # jeśli identyczne – nic nie robimy
            else:
                merged[k] = obj
    return list(merged.values()), conflicts

def _backup(path: str) -> str:
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = f"{base}.bak{i}{ext or '.json'}"
        if not os.path.exists(cand):
            shutil.copy2(path, cand) if os.path.exists(path) else None
            return cand
        i += 1

def main():
    ap = argparse.ArgumentParser(description="SAFE merge machines JSON (UNION; no deletion of uniques)")
    ap.add_argument("output", help="Docelowy plik JSON (ze źródła prawdy)")
    ap.add_argument("inputs", nargs="+", help="Pliki wejściowe do scalenia (co najmniej 1)")
    ap.add_argument("--dry-run", action="store_true", help="Tylko raport – nie zapisuje output")
    ap.add_argument("--sort-by", choices=["id","kod","nazwa","none"], default="id", help="Sortowanie wyniku")
    args = ap.parse_args()

    out = os.path.normpath(args.output)
    ins = [os.path.normpath(p) for p in args.inputs if os.path.exists(p)]
    if not ins:
        print("[ERR] Brak istniejących plików wejściowych.")
        sys.exit(2)

    merged, conflicts = _union_merge(ins)
    # Dołącz aktualną zawartość targetu (jeśli istnieje) – żeby nic nie zginęło:
    target_existing = _load_list(out) if os.path.exists(out) else []
    if target_existing:
        merged, extra_conflicts = _union_merge([out] + ins)  # union także z targetem
        conflicts.extend(extra_conflicts)

    # Sortowanie wyniku:
    if args.sort_by in ("id","kod","nazwa"):
        key_order = {"id":0,"kod":1,"nazwa":2}
        def sort_key(o: Dict[str,Any]):
            for k in ("id","ID","kod","code","nazwa","name"):
                if o.get(k) not in (None,""," "):
                    return _norm(o[k])
            return ""
        merged = sorted(merged, key=sort_key)

    # Raport
    total_inputs = sum(len(_load_list(p)) for p in ins)
    print(f"[MERGE][SAFE] wejście: {len(ins)} plików, rekordów={total_inputs}")
    print(f"[MERGE][SAFE] target pre-exist: {len(target_existing)}")
    print(f"[MERGE][SAFE] wynik (po UNION): {len(merged)}")
    if conflicts:
        print(f"[MERGE][SAFE] konflikty: {len(conflicts)} (pokazuję do 20):")
        for i,(k,a,b,src) in enumerate(conflicts[:20],1):
            print(f"  {i:02d}. KEY={k} ← konflikt z {src}")

    if args.dry_run:
        print("[MERGE][SAFE] DRY-RUN – nic nie zapisano.")
        return

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    backup = _backup(out)
    if backup:
        print(f"[MERGE][SAFE] backup targetu → {backup}")

    with open(out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[MERGE][SAFE] zapisano → {out}")

if __name__ == "__main__":
    main()
