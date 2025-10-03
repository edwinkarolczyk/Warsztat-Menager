#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply roadmap updates to data/audyt.json."""

from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Any, Dict, Iterable, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RM_PATH = os.path.join(REPO, "data", "audyt.json")

# Aktualizacje do naniesienia (dopasowanie po substrings w 'title' albo po 'key')
UPDATES: List[Dict[str, Any]] = [
    # --- CORE / SETTINGS ---
    {
        "match": {
            "section": "Core",
            "key": "core_one_root",
            "title_contains": "ONE-ROOT",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": (
                "Konsolidacja ścieżek do jednego Folder WM (root) + "
                "resolve_rel()."
            ),
        },
    },
    {
        "match": {
            "section": "Ustawienia",
            "key": "settings_root_status",
            "title_contains": "status",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": (
                "Panel statusu (zielone/czerwone) wg PATH_MAP w zakładce System."
            ),
        },
    },
    {
        "match": {
            "section": "Ustawienia",
            "key": "settings_root_init",
            "title_contains": "Utwórz brakujące",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": "Przycisk tworzący minimalne pliki/katalogi pod <root>.",
        },
    },
    # --- TOOLS ---
    {
        "match": {
            "section": "Narzędzia",
            "key": "tools_save_root_dir",
            "title_contains": "zapisy narzędzi",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": "Zapisy 001.json/002.json… pod <root>/narzedzia.",
        },
    },
    # --- ORDERS / ZLECENIA (R-05) ---
    {
        "match": {
            "section": "Zlecenia",
            "key": "orders_validate",
            "title_contains": "walidac",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": "Walidacje pól (puste → showerror + log).",
        },
    },
    {
        "match": {
            "section": "Zlecenia",
            "key": "orders_safe_after",
            "title_contains": "after()",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": "Odwołanie after() przy zamknięciu okna; brak wiszących callbacków.",
        },
    },
    {
        "match": {
            "section": "Zlecenia",
            "key": "orders_error_ui",
            "title_contains": "okno + log",
        },
        "set": {
            "status": "DONE",
            "progress": 100,
            "note": "Każdy wyjątek → messagebox + logger.exception.",
        },
    },
    # --- MASZYNY (R-03) ---
    {
        "match": {
            "section": "Maszyny",
            "key": "machines_sot",
            "title_contains": "Source of Truth",
        },
        "set": {
            "status": "IN_PROGRESS",
            "progress": 70,
            "note": (
                "<root>/maszyny.json ustawione; jeszcze bez finalnego scalenia danych "
                "z layout/."
            ),
        },
    },
    {
        "match": {
            "section": "Maszyny",
            "key": "machines_merge",
            "title_contains": "SAFE merge",
        },
        "set": {
            "status": "TODO",
            "progress": 0,
            "note": (
                "R-03B: Scalenie duplikatów UNION bez utraty danych "
                "(narzędzie merge)."
            ),
        },
    },
    {
        "match": {
            "section": "Maszyny",
            "key": "machines_renderer_guard",
            "title_contains": "renderer guard",
        },
        "set": {
            "status": "TODO",
            "progress": 0,
            "note": (
                "Gdy brak renderera hali → czytelny komunikat + log (bez crasha)."
            ),
        },
    },
]

# Jeśli w audyt.json nie ma pozycji (np. 3 wpisów dla ONE-ROOT), dodamy je poniżej:
FALLBACK_INSERTS: List[Dict[str, Any]] = [
    # CORE/SETTINGS (ONE-ROOT + status + init button)
    {
        "section": "Core",
        "key": "core_one_root",
        "title": "ONE-ROOT konsolidacja ścieżek",
        "status": "DONE",
        "progress": 100,
        "note": "Wszystko względem Folder WM (root).",
    },
    {
        "section": "Ustawienia",
        "key": "settings_root_status",
        "title": "Status zasobów pod root (✅/❌)",
        "status": "DONE",
        "progress": 100,
        "note": "Tabela w System pokazuje istnienie plików/katalogów.",
    },
    {
        "section": "Ustawienia",
        "key": "settings_root_init",
        "title": "Przycisk 'Utwórz brakujące pliki teraz'",
        "status": "DONE",
        "progress": 100,
        "note": "Tworzy minimalne JSON-y i katalogi wg PATH_MAP.",
    },
    # TOOLS
    {
        "section": "Narzędzia",
        "key": "tools_save_root_dir",
        "title": "Zapisy narzędzi pod <root>/narzedzia",
        "status": "DONE",
        "progress": 100,
        "note": "Pliki 001.json, 002.json… w katalogu narzedzia/ pod root.",
    },
    # ORDERS (R-05)
    {
        "section": "Zlecenia",
        "key": "orders_validate",
        "title": "Walidacje formularza (R-05)",
        "status": "DONE",
        "progress": 100,
        "note": "Puste pola → showerror + log.",
    },
    {
        "section": "Zlecenia",
        "key": "orders_safe_after",
        "title": "Bezpieczne after() przy zamknięciu (R-05)",
        "status": "DONE",
        "progress": 100,
        "note": "Brak callbacków po destroy.",
    },
    {
        "section": "Zlecenia",
        "key": "orders_error_ui",
        "title": "Wyjątki → okno + log (R-05)",
        "status": "DONE",
        "progress": 100,
        "note": "messagebox + logger.exception.",
    },
    # MASZYNY (R-03)
    {
        "section": "Maszyny",
        "key": "machines_sot",
        "title": "Source of Truth <root>/maszyny.json (R-03)",
        "status": "IN_PROGRESS",
        "progress": 70,
        "note": "Ścieżka i SoT gotowe; merge danych w kolejnym kroku.",
    },
    {
        "section": "Maszyny",
        "key": "machines_merge",
        "title": "SAFE merge duplikatów (R-03B)",
        "status": "TODO",
        "progress": 0,
        "note": "Scalenie bez utraty danych.",
    },
    {
        "section": "Maszyny",
        "key": "machines_renderer_guard",
        "title": "Renderer guard (brak crasha)",
        "status": "TODO",
        "progress": 0,
        "note": "Komunikat + log, gdy brak rendera.",
    },
]


Entry = Dict[str, Any]


def _load() -> List[Entry]:
    try:
        with open(RM_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("entries"), list):
            return list(data["entries"])
        # stare struktury roadmapy ignorujemy — rozpoczynamy nową listę
    return []


def _save(data: Iterable[Entry]) -> None:
    os.makedirs(os.path.dirname(RM_PATH), exist_ok=True)
    with open(RM_PATH, "w", encoding="utf-8") as f:
        json.dump(list(data), f, ensure_ascii=False, indent=2)


def _match(item: Entry, match_data: Dict[str, Any]) -> bool:
    section = match_data.get("section")
    if section and item.get("section") != section:
        return False
    title_sub = match_data.get("title_contains")
    if title_sub and title_sub.lower() not in (
        item.get("title", "").lower()
    ):
        return False
    key = match_data.get("key")
    if key and item.get("key") != key:
        return False
    return True


def _apply_updates(data: List[Entry]) -> int:
    touched = 0
    for upd in UPDATES:
        match_data = upd["match"]
        update_values = upd["set"]
        found = False
        for entry in data:
            if _match(entry, match_data):
                entry.update(update_values)
                found = True
                touched += 1
        if not found:
            for ins in FALLBACK_INSERTS:
                if _match(ins, match_data):
                    data.append(dict(ins))
                    touched += 1
                    break
    return touched


def _ensure_meta(data: List[Entry]) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta = {
        "section": "_meta",
        "key": "roadmap_last_update",
        "title": "Ostatnia aktualizacja Roadmapy",
        "status": "INFO",
        "progress": 0,
        "note": timestamp,
    }
    filtered = [
        entry
        for entry in data
        if not (
            entry.get("section") == "_meta"
            and entry.get("key") == "roadmap_last_update"
        )
    ]
    filtered.append(meta)
    data[:] = filtered


def main() -> int:
    data = _load()
    if not isinstance(data, list):
        print("Niepoprawny format danych roadmapy.")
        return 1

    touched = _apply_updates(data)
    _ensure_meta(data)
    _save(data)
    print(f"Roadmap updated. Entries touched/added: {touched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
