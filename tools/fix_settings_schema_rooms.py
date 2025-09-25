from __future__ import annotations
import json
import os
import re
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, ".."))
SCHEMA_PATH = os.path.join(ROOT, "settings_schema.json")

ROOMS_GROUP = {
    "title": "Pomieszczenia i ściany (ustawienia)",
    "fields": [
        {
            "type": "boolean",
            "key": "hall.rooms_enabled",
            "label": "Włącz warstwę pomieszczeń",
            "default": True
        },
        {
            "type": "number",
            "key": "hall.rooms_limit",
            "label": "Maks. liczba pomieszczeń",
            "default": 10,
            "min": 1,
            "max": 50
        },
        {
            "type": "array",
            "key": "hall.room_types",
            "label": "Typy pomieszczeń",
            "default": [
                "Biuro",
                "Magazyn",
                "Produkcja",
                "Kontrola",
                "Komunikacja"
            ]
        },
        {
            "type": "number",
            "key": "hall.default_wall_thickness_mm",
            "label": "Domyślna grubość ściany (mm)",
            "default": 120,
            "min": 50,
            "max": 500
        }
    ]
}


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def write_text(path: str, txt: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(txt)


def _fix_missing_commas_in_array(text: str, key: str) -> str:
    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*\[', re.DOTALL)
    match = pattern.search(text)
    if not match:
        return text

    start_index = match.end()
    depth = 1
    i = start_index
    while i < len(text) and depth > 0:
        char = text[i]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end_index = i
                break
        i += 1
    else:
        return text

    inner = text[start_index:end_index]
    inner_fixed = re.sub(r"}\s*{", "}, {", inner)
    return text[:start_index] + inner_fixed + text[end_index:]


def strip_comments_and_fix_trailing_commas(text: str) -> str:
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    text = re.sub(r",\s*([}\]])", r"\1", text)

    text = _fix_missing_commas_in_array(text, "tabs")

    return text.strip()


def load_schema_resilient(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = strip_comments_and_fix_trailing_commas(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as error:
            start = max(error.pos - 80, 0)
            end = min(error.pos + 80, len(cleaned))
            context = cleaned[start:end].replace("\n", "\\n")
            print(
                f"[ERR] Nie mogę sparsować settings_schema.json (pos={error.pos}): {error}"
            )
            print(f"[CTX] ...{context}...")
            sys.exit(1)


def ensure_maszyny_group(schema: Dict[str, Any]) -> bool:
    holder_key = None
    for key in ("tabs", "groups", "pages", "sections"):
        if isinstance(schema.get(key), list):
            holder_key = key
            break
    if not holder_key:
        print("[WARN] Nie znaleziono listy zakładek (tabs/groups/pages/sections).")
        return False

    tabs = schema[holder_key]
    target = None
    for tab in tabs:
        if isinstance(tab, dict) and (
            tab.get("id") == "maszyny"
            or tab.get("title", "").lower() == "maszyny"
        ):
            target = tab
            break
    if not target:
        print("[WARN] Brak zakładki 'maszyny' — nic nie dodaję.")
        return False

    groups = target.get("groups")
    if not isinstance(groups, list):
        groups = []
        target["groups"] = groups

    for group in groups:
        if not isinstance(group, dict):
            continue
        if group.get("title") == ROOMS_GROUP["title"]:
            print("[OK] Grupa 'Pomieszczenia i ściany (ustawienia)' już istnieje — pomijam.")
            return False
        if any(
            isinstance(field, dict) and field.get("key") == "hall.rooms_enabled"
            for field in group.get("fields", [])
        ):
            print("[OK] Wykryto pola 'hall.*' w innej grupie — pomijam.")
            return False

    groups.append(ROOMS_GROUP)
    print("[OK] Dodano grupę 'Pomieszczenia i ściany (ustawienia)' do zakładki 'maszyny'.")
    return True


def main() -> None:
    if not os.path.exists(SCHEMA_PATH):
        print(f"[ERR] Brak pliku: {SCHEMA_PATH}")
        sys.exit(1)

    raw = read_text(SCHEMA_PATH)
    schema = load_schema_resilient(raw)

    modified = ensure_maszyny_group(schema)

    output = json.dumps(schema, ensure_ascii=False, indent=2)
    write_text(SCHEMA_PATH, output)

    try:
        json.loads(output)
    except json.JSONDecodeError as error:
        print(f"[ERR] Walidacja po zapisie nieudana: {error}")
        sys.exit(1)

    print("[DONE] settings_schema.json zapisany.", "(+grupa)" if modified else "(bez zmian)")


if __name__ == "__main__":
    main()
