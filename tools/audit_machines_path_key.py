#!/usr/bin/env python3
# tools/audit_machines_path_key.py
# Raportuje użycia "maszyny.json"/"maszyny/maszyny.json" i kandydatów na klucz ustawień.

import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = [
    r"maszyny\.json",
    r"maszyny[/\\]maszyny\.json",
    r"PRIMARY_DATA",
    r"LEGACY_DATA",
]

def scan():
    hits = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if not fn.endswith((".py", ".json", ".md")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                for pat in PATTERNS:
                    for m in re.finditer(pat, txt):
                        line = txt.count("\n", 0, m.start()) + 1
                        hits.append((p, line, pat))
            except Exception:
                pass
    return hits

if __name__ == "__main__":
    rows = scan()
    if not rows:
        print("[AUDIT] Brak twardych odwołań do starych ścieżek – OK")
        sys.exit(0)
    print("[AUDIT] Znalezione odwołania do starych ścieżek:")
    for p, line, pat in rows:
        print(f" - {p}:{line} :: {pat}")
