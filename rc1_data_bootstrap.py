# -*- coding: utf-8 -*-
# RC1: bootstrap danych – korzysta z kluczy w ustawieniach (paths.* i istniejące wartości)
# Zasady:
# - JEŚLI w configu JEST ścieżka do pliku, ale plik NIE istnieje → pytamy, czy utworzyć TAM.
# - JEŚLI w configu NIE MA ścieżki → wyliczamy z paths.* i tworzymy bez pytania.
# - paths.* są nadrzędne wobec defaultów; defaulty tylko jako ostateczny fallback.

from __future__ import annotations

import json
import os

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")

# Minimalne payloady (bezpieczne, "puste")
PAYLOADS = {
    "warehouse.stock_source":        [],  # magazyn: lista pozycji
    "bom.file":                      [],  # BOM: lista pozycji
    "tools.types_file":              [],  # lista stringów
    "tools.statuses_file":           [],  # lista stringów
    "tools.task_templates_file":     [],  # lista dictów lub stringów
}

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


def _norm(p: str | None) -> str | None:
    if not p:
        return None
    return os.path.normpath(str(p).strip().strip('"').strip("'"))


def _ensure_dir_for(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _write_if_missing(path: str, payload) -> bool:
    if not os.path.exists(path):
        _ensure_dir_for(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    return False


def _ask_yesno(title: str, message: str) -> bool:
    # Gdy GUI brak (headless) → True (nie blokujemy startu)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(title, message)
        root.destroy()
        return bool(ans)
    except Exception:
        return True


def _get(cfg: dict, dotted: str):
    parts = dotted.split(".")
    cur = cfg
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _set(cfg: dict, dotted: str, value):
    parts = dotted.split(".")
    cur = cfg
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _set_aliases_for_bom(cfg: dict, path: str):
    # kompatybilność z aliasami historycznymi
    _set(cfg, "bom.file", path)
    cfg.setdefault("bom", {})["file"] = path
    cfg["bom.file"] = path


def _paths_base(cfg: dict) -> dict:
    """Zbiera bazy ścieżek z configu (jeśli ustawione), inaczej używa struktury repo."""
    paths = cfg.get("paths", {}) if isinstance(cfg.get("paths"), dict) else {}
    data_root = _norm(paths.get("data_root")) or _norm(cfg.get("data_root"))
    warehouse_dir = _norm(paths.get("warehouse_dir")) or (
        os.path.join(data_root, "magazyn") if data_root else None
    )
    products_dir = _norm(paths.get("products_dir")) or (
        os.path.join(data_root, "produkty") if data_root else None
    )
    tools_dir = _norm(paths.get("tools_dir")) or (
        os.path.join(data_root, "narzedzia") if data_root else None
    )

    # Fallback do struktury repo, gdy nic nie ustawiono
    warehouse_dir = warehouse_dir or os.path.join(ROOT, "data", "magazyn")
    products_dir = products_dir or os.path.join(ROOT, "data", "produkty")
    tools_dir = tools_dir or os.path.join(ROOT, "data", "narzedzia")

    return {
        "warehouse_dir": warehouse_dir,
        "products_dir": products_dir,
        "tools_dir": tools_dir,
    }


def ensure_data_files():
    cfg = _load_config()
    base = _paths_base(cfg)
    changed_cfg = False
    created_files: list[str] = []

    # Definicje KLUCZ → nazwa pliku (gdy brak w configu, tworzymy z paths.*)
    desired_when_missing = {
        "warehouse.stock_source": os.path.join(base["warehouse_dir"], "magazyn.json"),
        "bom.file": os.path.join(base["products_dir"], "bom.json"),
        "tools.types_file": os.path.join(base["tools_dir"], "typy_narzedzi.json"),
        "tools.statuses_file": os.path.join(base["tools_dir"], "statusy_narzedzi.json"),
        "tools.task_templates_file": os.path.join(
            base["tools_dir"], "szablony_zadan.json"
        ),
    }

    for dotted_key, fallback_path in desired_when_missing.items():
        # 1) Jeżeli w configu jest ścieżka:
        current = _norm(_get(cfg, dotted_key))
        if dotted_key == "bom.file" and not current:
            current = _norm(cfg.get("bom.file")) or _norm(cfg.get("bom", {}).get("file"))

        if current:
            # Plik nie istnieje → zapytaj, czy utworzyć w tej lokalizacji
            if not os.path.exists(current):
                if _ask_yesno(
                    "Brak pliku danych",
                    f"Nie znaleziono pliku:\n{current}\n\nUtworzyć pusty plik w tej lokalizacji?",
                ):
                    if _write_if_missing(current, PAYLOADS[dotted_key]):
                        created_files.append(current)
            # BOM: utrzymuj aliasy spójne
            if dotted_key == "bom.file":
                _set_aliases_for_bom(cfg, current)
                changed_cfg = True
        else:
            # 2) W configu brak ścieżki → wylicz z paths.* i UTWÓRZ bez pytania
            target = fallback_path
            if _write_if_missing(target, PAYLOADS[dotted_key]):
                created_files.append(target)
            if dotted_key == "bom.file":
                _set_aliases_for_bom(cfg, target)
            else:
                _set(cfg, dotted_key, target)
            changed_cfg = True

    if changed_cfg:
        _save_config(cfg)

    if created_files:
        print("[RC1][bootstrap] Utworzono pliki:")
        for p in created_files:
            print("  -", p)
    else:
        print("[RC1][bootstrap] Wszystkie wymagane pliki istnieją.")


# Auto-run przy imporcie
try:
    ensure_data_files()
except Exception as e:
    print(f"[RC1][bootstrap] ERROR: {e}")


if __name__ == "__main__":
    ensure_data_files()
