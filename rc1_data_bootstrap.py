# -*- coding: utf-8 -*-
# RC1: automatyczne dogenerowanie brakujących plików danych + naprawa ścieżek w configu

from __future__ import annotations
import os, json

ROOT = os.getcwd()
DEFAULTS = {
    "warehouse.stock_source":  os.path.join(ROOT, "data", "magazyn",   "magazyn.json"),
    "bom.file":                os.path.join(ROOT, "data", "produkty",  "bom.json"),
    "tools.types_file":        os.path.join(ROOT, "data", "narzedzia", "typy_narzedzi.json"),
    "tools.statuses_file":     os.path.join(ROOT, "data", "narzedzia", "statusy_narzedzi.json"),
    "tools.task_templates_file": os.path.join(ROOT, "data", "narzedzia", "szablony_zadan.json"),
}

CONFIG_PATH = os.path.join(ROOT, "config.json")

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RC1][bootstrap] config save error: {e}")

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _write_json_if_missing(path: str, payload) -> bool:
    if not os.path.exists(path):
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    return False

def _ask_yesno(title: str, message: str) -> bool:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        ans = messagebox.askyesno(title, message)
        root.destroy()
        return bool(ans)
    except Exception:
        return True

def _normalize_path(p: str | None) -> str | None:
    if not p: return None
    return os.path.normpath(str(p).strip().strip('"').strip("'"))

def _set_cfg_path(cfg: dict, dotted_key: str, value_path: str) -> None:
    parts = dotted_key.split(".")
    cur = cfg
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value_path
    if dotted_key == "bom.file":
        cfg.setdefault("bom", {})["file"] = value_path
        cfg["bom.file"] = value_path

def ensure_data_files():
    cfg = _load_config()
    changed_cfg = False
    created_files: list[str] = []

    defaults_payload = {
        "warehouse.stock_source":  [],
        "bom.file":                [],
        "tools.types_file":        [],
        "tools.statuses_file":     [],
        "tools.task_templates_file": [],
    }

    for key, def_path in DEFAULTS.items():
        current_path = _normalize_path(
            cfg.get(key)
            or (cfg.get(key.split(".")[0], {}) if "." in key else {}).get(key.split(".")[-1])
        ) or def_path

        if not os.path.exists(current_path):
            if _ask_yesno("Brak pliku danych",
                          f"Nie znaleziono pliku:\n{current_path}\n\nUtworzyć pusty?"):
                if _write_json_if_missing(current_path, defaults_payload[key]):
                    created_files.append(current_path)
                _set_cfg_path(cfg, key, current_path)
                changed_cfg = True
        else:
            has_in_cfg = cfg.get(key) or (cfg.get(key.split(".")[0], {}) if "." in key else {}).get(key.split(".")[-1])
            if not has_in_cfg:
                _set_cfg_path(cfg, key, current_path)
                changed_cfg = True

    if changed_cfg:
        _save_config(cfg)

    if created_files:
        print("[RC1][bootstrap] Utworzono pliki:")
        for p in created_files:
            print("  -", p)
    else:
        print("[RC1][bootstrap] Wszystkie wymagane pliki istnieją.")

try:
    ensure_data_files()
except Exception as e:
    print(f"[RC1][bootstrap] ERROR: {e}")

if __name__ == "__main__":
    ensure_data_files()
