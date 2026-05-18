# version: 1.0
"""Bootstrap routines ensuring WM root data exists and legacy files migrate."""

from __future__ import annotations

import logging
import os
import shutil

from config_manager import (
    ConfigManager,
    get_machines_path,
    resolve_rel,
    try_migrate_if_missing,
)
from utils_json import ensure_dir_json, safe_read_json

# Domyślne struktury dla automatycznie tworzonych plików JSON.  Wartości
# tekstowe zawierają wyraźne placeholdery "test …" aby użytkownik widział,
# jakie pola należy wypełnić własnymi danymi.
_DEFAULT_PROFILES = {
    "users": [
        {
            "login": "brygadzista",
            "role": "brygadzista",
            "pass_hash": "",
            "nazwa": "test nazwa",
            "opis": "test opis",
        }
    ]
}

_DEFAULT_MACHINES = {
    "maszyny": [
        {
            "id": "M-TEST",
            "nr_ewid": "TEST-000",
            "nr_hali": "test hala",
            "nazwa": "test nazwa",
            "typ": "test typ",
            "status": "test status",
            "opis": "test opis",
            "hala": "test hala",
            "x": 0,
            "y": 0,
            "zadania": [
                {
                    "data": "1970-01-01",
                    "typ_zadania": "test zadanie",
                    "uwagi": "test uwagi",
                    "opis": "test opis",
                }
            ],
        }
    ]
}

_DEFAULT_WAREHOUSE = {
    "pozycje": [
        {
            "kod": "TEST-001",
            "nazwa": "test nazwa",
            "opis": "test opis",
            "ilosc": 0,
            "jm": "szt",
            "stan": 0,
            "prog_alert": 0,
        }
    ]
}

_DEFAULT_BOM = {
    "pozycje": [
        {
            "symbol": "TEST-001",
            "nazwa": "test nazwa",
            "opis": "test opis",
        }
    ]
}

log = logging.getLogger(__name__)


def _ask_user_for_missing_file(label: str, expected_path: str) -> bool:
    """Ask user to point missing JSON file and copy it to expected path.

    Returns True only when user selected a file and it was copied.
    Returns False on cancel/error so existing bootstrap defaults still work.
    """

    if not expected_path:
        return False
    if os.path.exists(expected_path):
        return False

    filename = os.path.basename(expected_path)
    try:
        from tkinter import filedialog, messagebox
    except Exception:
        return False

    try:
        messagebox.showinfo(
            "Brakuje pliku danych WM",
            "Brakuje wymaganego pliku danych WM.\n\n"
            f"Element: {label}\n"
            f"Brakujący plik: {filename}\n\n"
            "WM szuka tutaj:\n"
            f"{expected_path}\n\n"
            "Wskaż właściwy plik JSON.\n"
            "Jeżeli anulujesz, WM utworzy domyślny plik.",
        )
        selected = filedialog.askopenfilename(
            title=f"Wskaż plik: {filename}",
            filetypes=[
                ("Pliki JSON", "*.json"),
                ("Wszystkie pliki", "*.*"),
            ],
        )
        if not selected:
            return False

        os.makedirs(os.path.dirname(expected_path) or ".", exist_ok=True)
        shutil.copy2(selected, expected_path)
        messagebox.showinfo(
            "Plik podpięty",
            "Skopiowano wskazany plik do lokalizacji WM.\n\n"
            f"Źródło:\n{selected}\n\n"
            f"Cel:\n{expected_path}",
        )
        return True
    except Exception as exc:
        try:
            messagebox.showwarning(
                "Nie udało się podpiąć pliku",
                "WM nie mógł skopiować wskazanego pliku.\n\n"
                f"Element: {label}\n"
                f"Cel:\n{expected_path}\n\n"
                f"Szczegóły: {exc}\n\n"
                "Program spróbuje utworzyć domyślny plik.",
            )
        except Exception:
            pass
        log.warning(
            "[ROOT] Nie udało się podpiąć pliku %s (%s): %s",
            label,
            expected_path,
            exc,
        )
        return False


def describe_root_targets(cfg: dict) -> list[tuple[str, str, str]]:
    """Return human-readable root targets checked/created during bootstrap.

    Tuple format:
    - label
    - path
    - kind: "file" or "dir"
    """

    tools_defs_path = resolve_rel(cfg, "tools_defs")
    targets = [
        ("profile użytkowników", resolve_rel(cfg, "profiles"), "file"),
        ("maszyny", get_machines_path(cfg), "file"),
        ("magazyn", resolve_rel(cfg, "warehouse"), "file"),
        ("produkty/BOM", resolve_rel(cfg, "bom"), "file"),
        ("narzędzia", resolve_rel(cfg, "tools_dir"), "dir"),
        ("zlecenia", resolve_rel(cfg, "orders_dir"), "dir"),
    ]

    if tools_defs_path:
        targets.append(("definicje/zadania narzędzi", tools_defs_path, "file"))

    return [(label, str(path or ""), kind) for label, path, kind in targets if path]


def _ensure_all(cfg: dict) -> None:
    """Create minimal directory / file structure for root storage."""

    profiles_path = resolve_rel(cfg, "profiles")
    if not _ask_user_for_missing_file("profile użytkowników", profiles_path):
        ensure_dir_json(profiles_path, _DEFAULT_PROFILES)

    machines_path = get_machines_path(cfg)
    if not _ask_user_for_missing_file("maszyny", machines_path):
        ensure_dir_json(machines_path, _DEFAULT_MACHINES)

    warehouse_path = resolve_rel(cfg, "warehouse")
    if not _ask_user_for_missing_file("magazyn", warehouse_path):
        ensure_dir_json(warehouse_path, _DEFAULT_WAREHOUSE)

    bom_path = resolve_rel(cfg, "bom")
    if not _ask_user_for_missing_file("produkty/BOM", bom_path):
        ensure_dir_json(bom_path, _DEFAULT_BOM)

    os.makedirs(resolve_rel(cfg, "tools_dir"), exist_ok=True)
    os.makedirs(resolve_rel(cfg, "orders_dir"), exist_ok=True)
    tools_defs_path = resolve_rel(cfg, "tools_defs")
    if tools_defs_path:
        if os.path.splitext(tools_defs_path)[1].lower() == ".json":
            _ask_user_for_missing_file(
                "definicje/zadania narzędzi",
                tools_defs_path,
            )
        os.makedirs(os.path.dirname(tools_defs_path), exist_ok=True)


def _migrate_legacy(cfg: dict) -> None:
    """Attempt one-way migrations from legacy locations if destination missing."""

    root = (cfg.get("paths") or {}).get("data_root") or ""
    legacy = {
        os.path.join(root, "layout", "maszyny.json"): get_machines_path(cfg),
        os.path.join(root, "magazyn", "magazyn.json"): resolve_rel(cfg, "warehouse"),
        os.path.join(root, "produkty", "bom.json"): resolve_rel(cfg, "bom"),
        os.path.join(root, "profiles.json"): resolve_rel(cfg, "profiles"),
    }

    moved: list[tuple[str, str]] = []
    for src, dst in legacy.items():
        try:
            if try_migrate_if_missing(src, dst):
                moved.append((src, dst))
        except Exception as exc:  # pragma: no cover - log only
            log.warning("Migracja %s -> %s nieudana: %s", src, dst, exc)

    for src, dst in moved:
        log.info("[MIGRACJA] %s -> %s", src, dst)


def ensure_root_min_files(cfg: dict) -> None:
    """Ensure minimal JSON files exist under configured root."""

    safe_read_json(get_machines_path(cfg), default=_DEFAULT_MACHINES)
    safe_read_json(resolve_rel(cfg, "profiles"), default=_DEFAULT_PROFILES)
    safe_read_json(resolve_rel(cfg, "tools"), default={"items": [], "narzedzia": []})
    safe_read_json(resolve_rel(cfg, "orders"), default={"zlecenia": []})
    safe_read_json(resolve_rel(cfg, "warehouse_stock"), default=_DEFAULT_WAREHOUSE)
    safe_read_json(resolve_rel(cfg, "bom"), default=_DEFAULT_BOM)


def ensure_root_ready(config_path: str = "config.json") -> bool:
    """Run ensure + migration steps for root data directory."""

    cm = ConfigManager(config_path)
    cfg = cm.load()
    _ensure_all(cfg)
    _migrate_legacy(cfg)
    return True
