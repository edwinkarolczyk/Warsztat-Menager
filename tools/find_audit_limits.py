#!/usr/bin/env python3
# tools/find_audit_limits.py
# Szuka miejsc w kodzie, gdzie audyt może być limitowany do 10 pozycji
# lub gdzie jest zdefiniowany stały rejestr testów.

import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATTERNS = [
    r"\[:10\]",                      # slicing do 10
    r"\bmax_items\s*=\s*10\b",       # domyślny parametr 10
    r"\bAUDIT_LIMIT\s*=\s*10\b",     # stała limitu
    r"\bAUDIT_LIMIT\s*=\s*\d+\b",    # inny limit liczbowy
    r"\bAUDIT_CASES\s*=\s*\[",       # tablica rejestru testów
    r"\baudit\s*\.\s*run\b",        # miejsca wywołania audytu
    r"\brun_audit\b",                # popularna nazwa wrappera
]

def scan():
    hits = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if not fn.endswith((".py", ".json", ".md")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                for pat in PATTERNS:
                    for m in re.finditer(pat, txt):
                        line = txt.count("\n", 0, m.start()) + 1
                        snippet = txt[m.start(): m.start()+120].replace("\n", "\\n")
                        hits.append((path, line, pat, snippet))
            except Exception:
                pass
    return hits

if __name__ == "__main__":
    rows = scan()
    if not rows:
        print("[AUDIT-SCAN] Brak ewidentnych limitów/registry – sprawdź gui_settings*.py / *audit*.py ręcznie.")
    else:
        print("[AUDIT-SCAN] Kandydaci (plik:linia :: dopasowanie → snippet):")
        for p, line, pat, sn in rows:
            print(f" - {p}:{line} :: {pat} → {sn}")
