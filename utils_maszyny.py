"""Narzędzia wspólne dla modułu maszyn."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

PRIMARY_DATA = os.path.join("data", "maszyny.json")
LEGACY_DATA = os.path.join("data", "maszyny", "maszyny.json")
PLACEHOLDER_PATH = os.path.join("grafiki", "machine_placeholder.png")

SOURCE_MODES = ("auto", "primary", "legacy")


def _normalize_machine_id(value: object) -> str:
    return str(value or "").strip()


def load_json_file(path: str) -> List[dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def index_by_id(rows: Iterable[dict]) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    for row in rows or []:
        machine_id = _normalize_machine_id(
            row.get("id") or row.get("nr_ewid") or row.get("nr")
        )
        if not machine_id:
            continue
        result[machine_id] = row
    return result


def sort_machines(rows: Iterable[dict]) -> List[dict]:
    indexed = index_by_id(rows)
    keys = sorted(indexed, key=lambda value: (len(value), value))
    return [indexed[key] for key in keys]


def merge_unique(primary_rows: Iterable[dict], legacy_rows: Iterable[dict]) -> List[dict]:
    primary_index = index_by_id(primary_rows)
    legacy_index = index_by_id(legacy_rows)
    for machine_id, row in legacy_index.items():
        if machine_id not in primary_index:
            primary_index[machine_id] = row
    return sort_machines(primary_index.values())


def load_machines(mode: str = "auto") -> Tuple[List[dict], str, int, int]:
    mode = mode if mode in SOURCE_MODES else "auto"
    primary = load_json_file(PRIMARY_DATA)
    legacy = load_json_file(LEGACY_DATA)

    count_primary, count_legacy = len(primary), len(legacy)

    if mode == "primary":
        chosen = sort_machines(primary)
        active_mode = "primary"
    elif mode == "legacy":
        chosen = sort_machines(legacy)
        active_mode = "legacy"
    else:
        active_mode = "auto"
        if primary and legacy:
            chosen = merge_unique(primary, legacy)
        elif primary:
            chosen = sort_machines(primary)
            active_mode = "primary"
        elif legacy:
            chosen = sort_machines(legacy)
            active_mode = "legacy"
        else:
            chosen = []
            active_mode = "primary"

    return chosen, active_mode, count_primary, count_legacy


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def apply_machine_updates(machine: dict, updates: dict) -> bool:
    if not isinstance(machine, dict):
        raise ValueError("Oczekiwano słownika z danymi maszyny.")

    changed = False

    if "nazwa" in updates:
        new_name = str(updates.get("nazwa") or "").strip()
        if new_name:
            if machine.get("nazwa") != new_name:
                machine["nazwa"] = new_name
                changed = True
        elif "nazwa" in machine:
            if machine.pop("nazwa") is not None:
                changed = True

    if "opis" in updates:
        new_desc = str(updates.get("opis") or "").strip()
        if new_desc:
            if machine.get("opis") != new_desc:
                machine["opis"] = new_desc
                changed = True
        elif "opis" in machine:
            if machine.pop("opis") is not None:
                changed = True

    if "hala" in updates:
        hall_value = updates.get("hala")
        try:
            hall_int = int(hall_value)
        except Exception as exc:  # noqa: BLE001 - walidacja danych wejściowych
            raise ValueError("Numer hali musi być liczbą całkowitą.") from exc
        if machine.get("hala") != hall_int:
            machine["hala"] = hall_int
            changed = True
        if machine.get("nr_hali") != str(hall_int):
            machine["nr_hali"] = str(hall_int)
            changed = True

    if "status" in updates:
        new_status = str(updates.get("status") or "").strip().lower()
        if not new_status:
            raise ValueError("Status nie może być pusty.")
        current_status = str(machine.get("status") or "").strip().lower()
        if current_status != new_status:
            machine["status"] = new_status
            changed = True
            czas = machine.setdefault("czas", {})
            now_ts = _timestamp()
            czas["status_since"] = now_ts
            if new_status == "awaria":
                czas["awaria_start"] = now_ts
            else:
                czas.pop("awaria_start", None)

    if "miniatura" in updates:
        new_preview = str(updates.get("miniatura") or "").strip()
        current_preview = (
            machine.get("media", {}).get("preview_url")
            if isinstance(machine.get("media"), dict)
            else None
        )
        if new_preview:
            if new_preview != current_preview:
                media = machine.setdefault("media", {})
                media["preview_url"] = new_preview
                changed = True
        else:
            if current_preview:
                media = machine.get("media")
                if isinstance(media, dict):
                    media.pop("preview_url", None)
                    if not media:
                        machine.pop("media", None)
                    changed = True

    return changed


def save_machines(rows: Iterable[dict]) -> None:
    data = sort_machines(rows)
    os.makedirs(os.path.dirname(PRIMARY_DATA), exist_ok=True)
    with open(PRIMARY_DATA, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
