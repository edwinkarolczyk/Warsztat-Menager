# -*- coding: utf-8 -*-
"""RC1 bootstrap: ensure default data files exist and config paths are valid."""

from __future__ import annotations

import json
import os
from typing import Any


ROOT = os.getcwd()
DEFAULTS = {
    "warehouse.stock_source": os.path.join(
        ROOT, "data", "magazyn", "magazyn.json"
    ),
    "bom.file": os.path.join(ROOT, "data", "produkty", "bom.json"),
    "tools.types_file": os.path.join(
        ROOT, "data", "narzedzia", "typy_narzedzi.json"
    ),
    "tools.statuses_file": os.path.join(
        ROOT, "data", "narzedzia", "statusy_narzedzi.json"
    ),
    "tools.task_templates_file": os.path.join(
        ROOT, "data", "narzedzia", "szablony_zadan.json"
    ),
}

CONFIG_PATH = os.path.join(ROOT, "config.json")


def _load_config() -> dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _save_config(cfg: dict[str, Any]) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as file:
            json.dump(cfg, file, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[RC1][bootstrap] config save error: {exc}")


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _write_json_if_missing(path: str, payload: Any) -> bool:
    """Write payload as JSON only when file is missing."""

    if not os.path.exists(path):
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return True
    return False


def _ask_yesno(title: str, message: str) -> bool:
    """Ask user for confirmation; default to yes when GUI is unavailable."""

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(title, message)
        root.destroy()
        return bool(answer)
    except Exception:
        return True


def _normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    return os.path.normpath(str(path).strip().strip('"').strip("'"))


def _resolve_alias(cfg: dict[str, Any], dotted_key: str) -> Any:
    base_key, _, leaf = dotted_key.partition(".")
    if not _:
        return cfg.get(dotted_key)
    section = cfg.get(base_key, {})
    return cfg.get(dotted_key) or section.get(leaf)


def _set_cfg_path(cfg: dict[str, Any], dotted_key: str, value_path: str) -> None:
    parts = dotted_key.split(".")
    cursor: dict[str, Any] = cfg
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value_path
    if dotted_key == "bom.file":
        cfg.setdefault("bom", {})["file"] = value_path
        cfg["bom.file"] = value_path


def ensure_data_files() -> None:
    cfg = _load_config()
    changed_cfg = False
    created_files: list[str] = []

    defaults_payload = {
        "warehouse.stock_source": [],
        "bom.file": [],
        "tools.types_file": [],
        "tools.statuses_file": [],
        "tools.task_templates_file": [],
    }

    for key, default_path in DEFAULTS.items():
        configured_path = _normalize_path(_resolve_alias(cfg, key)) or default_path

        if not os.path.exists(configured_path):
            title = "Brak pliku danych"
            message = (
                "Nie znaleziono pliku:\n"
                f"{configured_path}\n\n"
                "Czy utworzyć teraz pusty plik i ustawić tę ścieżkę w ustawieniach?"
            )
            if _ask_yesno(title, message):
                if _write_json_if_missing(configured_path, defaults_payload[key]):
                    created_files.append(configured_path)
                _set_cfg_path(cfg, key, configured_path)
                changed_cfg = True
        else:
            if not _resolve_alias(cfg, key):
                _set_cfg_path(cfg, key, configured_path)
                changed_cfg = True

    if changed_cfg:
        _save_config(cfg)

    if created_files:
        print("[RC1][bootstrap] Utworzono pliki:")
        for path in created_files:
            print("  -", path)
    else:
        print("[RC1][bootstrap] Wszystkie wymagane pliki istnieją.")


try:
    ensure_data_files()
except Exception as exc:
    print(f"[RC1][bootstrap] ERROR: {exc}")


if __name__ == "__main__":
    ensure_data_files()
