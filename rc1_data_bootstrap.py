# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")

# Minimalne payloady (bezpieczne, "puste")
PAYLOADS = {
    "warehouse.stock_source":        [],  # magazyn: lista pozycji
    "bom.file":                      [],  # BOM: lista pozycji
    "tools.types_file":              [],  # lista stringów
    "tools.statuses_file":           [],  # lista stringów
    "tools.task_templates_file":     [],  # lista dictów lub stringów
    "hall.machines_file":            [],  # lista maszyn
}

# Podpowiedzi katalogów (tylko z paths.* — żadnych repo fallbacków)
KEY_TO_PATHDIR = {
    "warehouse.stock_source":        "warehouse_dir",
    "bom.file":                      "products_dir",
    "tools.types_file":              "tools_dir",
    "tools.statuses_file":           "tools_dir",
    "tools.task_templates_file":     "tools_dir",
    "hall.machines_file":            "machines_dir",
}

# Sugerowane nazwy plików oraz filtry
KEY_TO_FILENAME = {
    "warehouse.stock_source":        "magazyn.json",
    "bom.file":                      "bom.json",
    "tools.types_file":              "typy_narzedzi.json",
    "tools.statuses_file":           "statusy_narzedzi.json",
    "tools.task_templates_file":     "szablony_zadan.json",
    "hall.machines_file":            "maszyny.json",
}
KEY_TO_FILTERS = {
    "warehouse.stock_source":        [("Plik JSON", "*.json")],
    "bom.file":                      [("Plik JSON", "*.json")],
    "tools.types_file":              [("Plik JSON", "*.json")],
    "tools.statuses_file":           [("Plik JSON", "*.json")],
    "tools.task_templates_file":     [("Plik JSON", "*.json")],
    "hall.machines_file":            [("Plik JSON", "*.json")],
}


def _bootstrap_active() -> bool:
    try:
        start_module = sys.modules.get("start")
        if start_module is None:
            return False
        return bool(getattr(start_module, "BOOTSTRAP_ACTIVE", False))
    except Exception:
        return False


def _log_dialog_block(kind: str, reason: str) -> None:
    reason_text = reason or "brak powodu"
    msg = (
        "[RC1][bootstrap] Zablokowano dialog "
        f"{kind} podczas bootstrapa (powód: {reason_text})"
    )
    print(msg)

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
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(title, message)
        root.destroy()
        return bool(ans)
    except Exception:
        # headless → nie blokujemy pracy
        return True


def _ask_open_file(initialdir: str | None, filters, *, reason: str = "") -> str | None:
    if _bootstrap_active():
        _log_dialog_block("open", reason)
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(initialdir=initialdir or "", filetypes=filters)
        root.destroy()
        return path or None
    except Exception:
        return None


def _ask_save_file(
    initialdir: str | None,
    initialfile: str,
    filters,
    *,
    reason: str = "",
) -> str | None:
    if _bootstrap_active():
        _log_dialog_block("save", reason or initialfile)
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.asksaveasfilename(
            initialdir=initialdir or "",
            initialfile=initialfile,
            defaultextension=".json",
            filetypes=filters
        )
        root.destroy()
        return path or None
    except Exception:
        return None


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
    _set(cfg, "bom.file", path)
    cfg.setdefault("bom", {})["file"] = path
    cfg["bom.file"] = path


def _paths_from_settings(cfg: dict) -> dict:
    paths = cfg.get("paths", {}) if isinstance(cfg.get("paths"), dict) else {}
    return {
        "data_root":     _norm(paths.get("data_root") or cfg.get("data_root")),
        "warehouse_dir": _norm(paths.get("warehouse_dir")),
        "products_dir":  _norm(paths.get("products_dir")),
        "tools_dir":     _norm(paths.get("tools_dir")),
        "machines_dir":  _norm(paths.get("machines_dir") or paths.get("hall_dir")),
    }


def _resolve_initialdir(cfg: dict, dotted_key: str) -> str | None:
    base_map = _paths_from_settings(cfg)
    hint_dir_key = KEY_TO_PATHDIR.get(dotted_key)
    return base_map.get(hint_dir_key) if hint_dir_key else base_map.get("data_root")


def _migrate_layout_machines_path(cfg: dict) -> str | None:
    """
    Jeśli w configu jest stary/błędny hall.machines_file → ...\\data\\layout\\maszyny.json,
    a w katalogu z paths.machines_dir istnieje 'maszyny.json', zapytaj o migrację.
    """
    cur = _norm(_get(cfg, "hall.machines_file"))
    if not cur:
        return None
    low = cur.replace("/", "\\").lower()
    if ("\\data\\layout\\maszyny.json" in low) or ("/data/layout/maszyny.json" in cur.replace("\\", "/").lower()):
        base_dir = _resolve_initialdir(cfg, "hall.machines_file")
        candidate = os.path.join(base_dir, "maszyny.json") if base_dir else None
        if candidate and os.path.exists(candidate):
            if _ask_yesno("Migracja pliku maszyn",
                          f"Wykryto wpis do layout\\maszyny.json, ale istnieje:\n{candidate}\n\n"
                          f"Czy podmienić ustawienie na ten plik?"):
                _set(cfg, "hall.machines_file", candidate)
                return candidate
    return None


def _pick_or_create_path(cfg: dict, dotted_key: str) -> str | None:
    """
    Wybiera ścieżkę dla klucza:
    - jeśli klucz jest pusty → pozwala wybrać plik (open) lub wskazać nowy (save),
    - jeśli klucz jest ustawiony, ale pliku brak → pyta o utworzenie lub zmianę ścieżki.
    Zwraca finalną ścieżkę lub None (gdy użytkownik anulował).
    """
    filters = KEY_TO_FILTERS[dotted_key]
    initialfile = KEY_TO_FILENAME[dotted_key]
    current = _norm(_get(cfg, dotted_key))
    if dotted_key == "bom.file" and not current:
        current = _norm(cfg.get("bom.file")) or _norm(cfg.get("bom", {}).get("file"))

    base_dir = _resolve_initialdir(cfg, dotted_key)

    # 1) nic nie ustawiono → zapytaj o istniejący, a jeśli brak — zaproponuj zapis nowego
    if not current:
        chosen = _ask_open_file(base_dir, filters, reason=f"open:{dotted_key}")
        if not chosen:
            chosen = _ask_save_file(
                base_dir,
                initialfile,
                filters,
                reason=f"save:{dotted_key}",
            )
            if not chosen:
                # headless: jeśli mamy base_dir, utwórz domyślną nazwę tam; jeśli nie — przerwij
                if base_dir:
                    chosen = os.path.join(base_dir, initialfile)
                    _write_if_missing(chosen, PAYLOADS[dotted_key])
                else:
                    return None
        return chosen

    # 2) jest ścieżka, ale brak pliku → zapytaj o utworzenie, albo pozwól wybrać inny
    if not os.path.exists(current):
        if _ask_yesno("Brak pliku danych",
                      f"Nie znaleziono pliku:\n{current}\n\nUtworzyć pusty plik w tej lokalizacji?"):
            _write_if_missing(current, PAYLOADS[dotted_key])
            return current
        else:
            chosen = _ask_open_file(base_dir, filters, reason=f"open-missing:{dotted_key}")
            if not chosen:
                chosen = _ask_save_file(
                    base_dir,
                    initialfile,
                    filters,
                    reason=f"save-missing:{dotted_key}",
                )
            return chosen or None

    return current


def ensure_data_files():
    cfg = _load_config()
    changed_cfg = False
    created_files: list[str] = []

    # ewentualna migracja hall.machines_file (layout -> machines_dir)
    migrated = _migrate_layout_machines_path(cfg)
    if migrated:
        changed_cfg = True
        print(f"[RC1][bootstrap] MIGRACJA: hall.machines_file → {migrated}")

    # kolejne klucze do obsłużenia (kolejność nieprzypadkowa ze względu na aliasy BOM)
    for dotted_key in [
        "warehouse.stock_source",
        "bom.file",
        "tools.types_file",
        "tools.statuses_file",
        "tools.task_templates_file",
        "hall.machines_file",
    ]:
        target = _pick_or_create_path(cfg, dotted_key)
        if not target:
            # użytkownik anulował — nie wymuszamy defaultów
            print(f"[RC1][bootstrap] Pominięto ustawienie: {dotted_key} (użytkownik nie wskazał pliku)")
            continue

        # Zapisz do configu
        if dotted_key == "bom.file":
            _set_aliases_for_bom(cfg, target)
        else:
            _set(cfg, dotted_key, target)
        changed_cfg = True

        # Upewnij się, że plik istnieje (mógł zostać wybrany save path)
        if _write_if_missing(target, PAYLOADS[dotted_key]):
            created_files.append(target)

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
