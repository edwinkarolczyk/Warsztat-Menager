# version: 1.2
# Zmiany 1.2:
# - Dane maszyn są zawsze rozwiązywane względem aktywnego DATA_ROOT, a nie CWD programu.
# Zmiany 1.1:
# - Domyślny rok harmonogramu jest pobierany z bieżącej daty zamiast stałego 2025.
"""Narzędzia wspólne dla modułu maszyn."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import unicodedata
from typing import Any, Dict, Iterable, List, Tuple

from core.path_utils import resolve_root_path

from utils_json import (
    normalize_rows as _normalize_rows,
    safe_read_json as _safe_read_json,
    safe_write_json as _safe_write_json,
)

_r = _safe_read_json
_w = _safe_write_json

# Zachowane dla kompatybilności z kodem, który może importować te nazwy.
# Aktywne operacje I/O używają _machine_data_paths(), aby nie wiązać ścieżek
# z katalogiem roboczym ani z momentem importu modułu.
PRIMARY_DATA = os.path.join("data", "maszyny", "maszyny.json")
LEGACY_DATA = os.path.join("data", "maszyny.json")
PLACEHOLDER_PATH = os.path.join("grafiki", "machine_placeholder.png")

SOURCE_MODES = ("auto", "primary", "legacy")
DEFAULT_SOURCE = os.environ.get("WM_MACHINES_SOURCE", "auto").strip().lower()


def _machine_data_paths() -> tuple[str, str]:
    """Zwróć kanoniczne ścieżki maszyn dla aktualnego DATA_ROOT."""

    try:
        from core import root_paths as wm_root_paths

        primary = wm_root_paths.path_machines()
        legacy = wm_root_paths.get_data_root() / "maszyny.json"
        return str(primary), str(legacy)
    except Exception:
        data_root = str(os.environ.get("WM_DATA_ROOT") or "").strip()
        if data_root:
            return (
                os.path.join(data_root, "maszyny", "maszyny.json"),
                os.path.join(data_root, "maszyny.json"),
            )
        return (
            resolve_root_path("<root>", PRIMARY_DATA),
            resolve_root_path("<root>", LEGACY_DATA),
        )


def _normalize_machine_id(value: object) -> str:
    return str(value or "").strip()


def _coerce_rows(data: Any) -> List[dict]:
    """Przekształć różne formy danych na listę słowników."""

    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("maszyny"), list):
            return [row for row in data["maszyny"] if isinstance(row, dict)]
        values = list(data.values())
        if values and all(isinstance(value, dict) for value in values):
            return values
    return []


def _explain_rows(rows: List[dict], label: str) -> None:
    count_all = len(rows)
    with_id = [
        row
        for row in rows
        if _normalize_machine_id(
            row.get("id") or row.get("nr_ewid") or row.get("nr")
        )
    ]
    count_with_id = len(with_id)
    if count_all == 0:
        print(f"[DIAG][Maszyny] {label}: 0 rekordów po parsowaniu.")
    else:
        print(
            "[DIAG][Maszyny] "
            f"{label}: {count_all} rekordów po parsowaniu, z ID/nr_ewid: {count_with_id}"
        )


def _load_json_file(path: str) -> List[dict]:
    """Wczytaj plik JSON tolerując drobne błędy formatu."""

    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        if not raw:
            _explain_rows([], os.path.abspath(path))
            return []
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except Exception:
            softened = re.sub(r",(\s*[]})", r"\1", text)
            data = json.loads(softened)
        rows = _coerce_rows(data)
        _explain_rows(rows, os.path.abspath(path))
        return rows
    except FileNotFoundError:
        print(f"[DIAG][Maszyny] Brak pliku: {os.path.abspath(path)}")
        return []
    except Exception as exc:  # pragma: no cover - defensywne logowanie
        print(f"[DIAG][Maszyny] Nie mogę wczytać {os.path.abspath(path)}: {exc}")
        return []


def load_json_file(path: str) -> List[dict]:
    """Zachowana dla kompatybilności publiczna wersja loadera."""

    return _load_json_file(path)


def _save_json_file(path: str, rows: List[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


def _index_by_id(rows: Iterable[dict]) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    for row in rows or []:
        machine_id = _normalize_machine_id(
            row.get("id") or row.get("nr_ewid") or row.get("nr")
        )
        if not machine_id:
            continue
        result[machine_id] = row
    return result


def index_by_id(rows: Iterable[dict]) -> Dict[str, dict]:
    return _index_by_id(rows)


def sort_machines(rows: Iterable[dict]) -> List[dict]:
    indexed = _index_by_id(rows)
    keys = sorted(indexed, key=lambda value: (len(value), value))
    return [indexed[key] for key in keys]


def resolve_schedule_path(year: int | None = None, cfg: Any | None = None) -> str:
    """Return absolute path to the maintenance schedule JSON for *year*."""

    if year is None:
        year = dt.date.today().year
    filename = f"harmonogram_{int(year)}.json"

    try:
        if hasattr(cfg, "path_data") and callable(cfg.path_data):  # type: ignore[union-attr]
            return cfg.path_data("maszyny", filename)
    except Exception:
        pass

    try:
        from config_manager import ConfigManager  # imported lazily to avoid cycles

        manager = ConfigManager()
        return manager.path_data("maszyny", filename)
    except Exception:
        return resolve_root_path("<root>", os.path.join("data", "maszyny", filename))


def merge_unique(primary_rows: Iterable[dict], legacy_rows: Iterable[dict]) -> List[dict]:
    return _merge_unique(primary_rows, legacy_rows)


def _merge_unique(primary_rows: Iterable[dict], legacy_rows: Iterable[dict]) -> List[dict]:
    primary_index = _index_by_id(primary_rows)
    legacy_index = _index_by_id(legacy_rows)
    duplicates = set(primary_index) & set(legacy_index)
    if duplicates:
        preview = sorted(list(duplicates))
        shown = ", ".join(preview[:10])
        suffix = " ..." if len(preview) > 10 else ""
        print(
            "[DIAG][Maszyny] Duplikaty ID między źródłami (zostaje PRIMARY): "
            f"{shown}{suffix}"
        )
    for machine_id, row in legacy_index.items():
        if machine_id not in primary_index:
            primary_index[machine_id] = row
    keys = sorted(primary_index, key=lambda value: (len(value), value))
    return [primary_index[key] for key in keys]


def _ids_preview(rows: Iterable[dict], limit: int = 5) -> str:
    preview: List[str] = []
    for row in rows or []:
        if len(preview) >= limit:
            break
        machine_id = _normalize_machine_id(
            row.get("id") or row.get("nr_ewid") or row.get("nr")
        )
        preview.append(machine_id or "?")
    return ", ".join(preview)


def _pick_source(
    ui_choice: str | None = None,
    primary_rows: List[dict] | None = None,
    legacy_rows: List[dict] | None = None,
) -> Tuple[List[dict], str, str]:
    choice = (ui_choice or DEFAULT_SOURCE or "auto").lower()
    if choice not in SOURCE_MODES:
        choice = "auto"

    primary_path, legacy_path = _machine_data_paths()
    primary_rows = primary_rows if primary_rows is not None else _load_json_file(primary_path)
    legacy_rows = legacy_rows if legacy_rows is not None else _load_json_file(legacy_path)
    count_primary, count_legacy = len(primary_rows), len(legacy_rows)

    if choice == "legacy":
        if count_legacy == 0:
            print(
                "[WM][Maszyny] Wybrano LEGACY, ale po parsowaniu 0 rekordów → "
                "fallback na PRIMARY."
            )
            choice = "primary"
        else:
            print(
                "[WM][Maszyny] source=LEGACY "
                f"file={os.path.abspath(legacy_path)} "
                f"cnt={count_legacy} ids[{_ids_preview(legacy_rows)}]"
            )
            return sort_machines(legacy_rows), "legacy", legacy_path

    if choice == "primary":
        print(
            "[WM][Maszyny] source=PRIMARY "
            f"file={os.path.abspath(primary_path)} "
            f"cnt={count_primary} ids[{_ids_preview(primary_rows)}]"
        )
        return sort_machines(primary_rows), "primary", primary_path

    if count_primary and count_legacy:
        merged = _merge_unique(primary_rows, legacy_rows)
        print(
            "[WM][Maszyny] source=AUTO→MERGE "
            f"primary={count_primary} legacy={count_legacy} "
            f"ids[{_ids_preview(merged)}]"
        )
        return merged, "auto", f"{primary_path}+{legacy_path}"

    if count_legacy:
        print(
            "[WM][Maszyny] source=AUTO→LEGACY "
            f"file={os.path.abspath(legacy_path)} "
            f"cnt={count_legacy} ids[{_ids_preview(legacy_rows)}]"
        )
        return sort_machines(legacy_rows), "legacy", legacy_path

    if count_primary:
        print(
            "[WM][Maszyny] source=AUTO→PRIMARY "
            f"file={os.path.abspath(primary_path)} "
            f"cnt={count_primary} ids[{_ids_preview(primary_rows)}]"
        )
        return sort_machines(primary_rows), "primary", primary_path

    print(
        "[WM][Maszyny] source=EMPTY (oba pliki puste lub błędne) "
        f"primary={primary_path} legacy={legacy_path}"
    )
    return [], "primary", primary_path


def load_machines(
    value: str | None = None,
    *,
    mode: str | None = None,
) -> Tuple[List[dict], str, int, int] | Tuple[List[Dict], str]:
    """Wczytuje dane maszyn.

    Funkcja obsługuje dwa tryby dla zachowania kompatybilności wstecznej:

    1. ``load_machines()`` lub ``load_machines(mode="auto")`` –
       zachowuje poprzednie API i zwraca krotkę
       ``(rows, active_mode, count_primary, count_legacy)``.
    2. ``load_machines(primary_path)`` – nowy wariant wymagany przez GUI,
       który zwraca ``(rows, primary_path)`` dla konkretnej ścieżki.
    """

    if value and value.lower() not in SOURCE_MODES and mode is None:
        data = _safe_read_json(value, default={"maszyny": []})
        rows = _normalize_rows(data, "maszyny") or _normalize_rows(data, None)
        return rows, value

    choice = (mode or value or DEFAULT_SOURCE or "auto").lower()
    if choice not in SOURCE_MODES:
        choice = "auto"

    primary_path, legacy_path = _machine_data_paths()
    primary_rows = _load_json_file(primary_path)
    legacy_rows = _load_json_file(legacy_path)
    count_primary, count_legacy = len(primary_rows), len(legacy_rows)

    selected, active_mode, _ = _pick_source(choice, primary_rows, legacy_rows)
    return selected, active_mode, count_primary, count_legacy


def _timestamp() -> str:
    return now_iso()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


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
    primary_path, _ = _machine_data_paths()
    _save_json_file(primary_path, data)


def _fix_if_dir(path: str, expected_rel: str) -> str:
    """Jeśli trafił katalog (root), dołącz domyślny relatywny plik."""

    if not path or os.path.isdir(path):
        return os.path.normpath(os.path.join(path or "", expected_rel))
    return path


def load_machines_rows_with_fallback(cfg: dict, resolve_rel):
    # primary
    primary = resolve_rel(cfg, r"maszyny\maszyny.json")
    primary = _fix_if_dir(primary, r"maszyny\maszyny.json")
    data = _safe_read_json(primary, default={"maszyny": []})
    rows = _normalize_rows(data, "maszyny") or _normalize_rows(data, None)
    if rows:
        return rows, primary

    # legacy fallback
    legacy = resolve_rel(cfg, r"maszyny.json")
    legacy = _fix_if_dir(legacy, r"maszyny\maszyny.json")
    data2 = _safe_read_json(legacy, default=[])
    rows2 = _normalize_rows(data2, None)
    if rows2:
        return rows2, primary
    return [], primary


def ensure_machines_sample_if_empty(rows: list[dict], primary_path: str):
    """Jeśli pusto – zapisuje 3 przykładowe rekordy do primary_path i je zwraca."""

    if rows:
        return rows
    sample = [
        {"id": "M-001", "nazwa": "Tokarka CNC", "typ": "CNC", "lokalizacja": "Hala A"},
        {"id": "M-002", "nazwa": "Frezarka 3-osiowa", "typ": "FREZ", "lokalizacja": "Hala A"},
        {"id": "M-003", "nazwa": "Prasa", "typ": "PRASA", "lokalizacja": "Hala B"},
    ]
    _safe_write_json(primary_path, {"maszyny": sample})
    return sample


def save_machines_rows(primary_path: str, rows: List[Dict]) -> bool:
    """Zapisuje dane maszyn w docelowym formacie ``{"maszyny": [...]}``."""

    return _safe_write_json(primary_path, {"maszyny": rows})


def load_machines_from_path(primary_path: str) -> Tuple[List[Dict], str]:
    """Pomocnicza funkcja do wczytywania z konkretnej ścieżki."""

    data = _safe_read_json(primary_path, default={"maszyny": []})
    rows = _normalize_rows(data, "maszyny") or _normalize_rows(data, None)
    return rows, primary_path


def upsert_machine(rows: List[Dict], upd: Dict) -> List[Dict]:
    """Aktualizuje rekord po ``id`` lub dodaje go na końcu listy."""

    machine_id = (upd or {}).get("id")
    if not machine_id:
        return rows

    updated: List[Dict] = []
    found = False
    for row in rows:
        if isinstance(row, dict) and row.get("id") == machine_id:
            updated.append({**row, **upd})
            found = True
        else:
            updated.append(row)
    if not found:
        updated.append(upd)
    return updated


def delete_machine(rows: List[Dict], machine_id: str) -> List[Dict]:
    """Usuń maszynę o wskazanym identyfikatorze."""

    return [row for row in rows if isinstance(row, dict) and row.get("id") != machine_id]


def merge_rows_union_by_id(base_rows: List[Dict], incoming_rows: List[Dict]) -> List[Dict]:
    """Połącz listy maszyn według ``id`` zachowując unikalne rekordy."""

    base_index = _index_by_id(base_rows)
    incoming_index = _index_by_id(incoming_rows)
    base_index.update(incoming_index)
    return [base_index[key] for key in sorted(base_index.keys())]
