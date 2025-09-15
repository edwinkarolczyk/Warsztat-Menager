# ===============================================
# PLIK 1/2 (NOWY): magazyn_slowniki.py
# ===============================================
# Wersja: 1.0.0
# - Odczyt/zapis data/magazyn/slowniki.json (jednostki, typy)
# - Fallbacki i deduplikacja (case-insensitive)

import json
import os

SLOWNIKI_PATH = os.path.join("data", "magazyn", "slowniki.json")
DEFAULT = {
    "jednostki": ["szt", "mb"],
    "typy": ["surowiec", "półprodukt", "komponent"]
}


def _dedup_norm(seq):
    out, seen = [], set()
    for x in seq or []:
        if not isinstance(x, str):
            continue
        s = x.strip()
        k = s.lower()
        if s and k not in seen:
            seen.add(k)
            out.append(s)
    return out


def load():
    try:
        with open(SLOWNIKI_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return DEFAULT.copy()
    except Exception:
        return DEFAULT.copy()
    return {
        "jednostki": _dedup_norm(data.get("jednostki") or DEFAULT["jednostki"]),
        "typy": _dedup_norm(data.get("typy") or DEFAULT["typy"]),
    }


def save(data: dict):
    os.makedirs(os.path.dirname(SLOWNIKI_PATH), exist_ok=True)
    cur = load()
    cur["jednostki"] = _dedup_norm(data.get("jednostki", cur["jednostki"]))
    cur["typy"] = _dedup_norm(data.get("typy", cur["typy"]))
    with open(SLOWNIKI_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return cur


def get_jednostki():
    return load().get("jednostki", DEFAULT["jednostki"])


def get_typy():
    return load().get("typy", DEFAULT["typy"])

