# -*- coding: utf-8 -*-
# RC1: bootstrap użytkowników + przypominajka o zmianie domyślnego hasła admina
#
# Co robi:
# - Ustala ścieżkę do profiles.json na podstawie configu (paths.* / profiles.file) – bez sztywnych ścieżek.
# - Jeśli plik nie istnieje → pyta, czy utworzyć minimalny plik z kontem "admin"/"admin".
# - Na każdym starcie sprawdza, czy wciąż istnieje konto "admin" z hasłem "admin"/pustym → przypomina, aż zmienisz.
# - Działa też w trybie bez GUI (wtedy tworzy automatycznie i wypisuje ostrzeżenie do loga/STDOUT).

from __future__ import annotations
import os, json

ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")

DEFAULT_ADMIN_RECORD = {
    "login": "admin",
    "haslo": "admin",
    "rola": "administrator",
    "aktywny": True,
    "imie": "Administrator",
    "nazwisko": "",
    "email": "",
    "ostatnie_logowanie": None
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
        print(f"[RC1][profiles] config save error: {e}")

def _norm(p: str | None) -> str | None:
    if not p: return None
    return os.path.normpath(str(p).strip().strip('"').strip("'"))

def _ensure_dir_for(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _ask_yesno(title: str, message: str) -> bool:
    # Bez GUI (headless) → True, żeby nie blokować startu.
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        ans = messagebox.askyesno(title, message)
        root.destroy()
        return bool(ans)
    except Exception:
        return True

def _warn(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showwarning(title, message)
        root.destroy()
    except Exception:
        print(f"[RC1][profiles][WARN] {title}: {message}")

def _paths_base(cfg: dict) -> dict:
    # Zbiera bazy ścieżek z configu, fallback do struktury repo.
    paths = cfg.get("paths", {}) if isinstance(cfg.get("paths"), dict) else {}
    data_root   = _norm(paths.get("data_root")) or _norm(cfg.get("data_root"))
    users_dir   = _norm(paths.get("users_dir")) or (_norm(paths.get("profiles_dir")) if isinstance(paths.get("profiles_dir"), str) else None)
    if not users_dir:
        users_dir = os.path.join(data_root, "users") if data_root else None
    users_dir = users_dir or os.path.join(ROOT, "data")  # fallback: w repo trzymamy w data/profiles.json
    return {"users_dir": users_dir}

def _profiles_path(cfg: dict) -> str:
    # 1) jeżeli config ma profiles.file → użyj
    val = None
    try:
        # obsługa kilku możliwych miejsc trzymania klucza
        val = cfg.get("profiles", {}).get("file") or cfg.get("profiles.file")
    except Exception:
        val = None
    val = _norm(val)
    if val:
        return val

    # 2) w przeciwnym razie wylicz z paths.*
    base = _paths_base(cfg)
    return os.path.join(base["users_dir"], "profiles.json")

def _read_profiles(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        # czasem bywa {"profiles":[...]}
        if isinstance(data, dict) and isinstance(data.get("profiles"), list):
            return [x for x in data["profiles"] if isinstance(x, dict)]
        return []
    except Exception as e:
        print(f"[RC1][profiles] read error {path}: {e}")
        return []

def _write_profiles(path: str, records: list[dict]) -> None:
    _ensure_dir_for(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def _has_default_admin(records: list[dict]) -> bool:
    for r in records:
        login = str(r.get("login") or "").strip().lower()
        haslo = (r.get("haslo") or "")
        if login == "admin" and (haslo == "admin" or str(haslo).strip() == ""):
            return True
    return False

def _ensure_profiles_file(cfg: dict) -> str:
    path = _profiles_path(cfg)
    if not os.path.exists(path):
        if _ask_yesno("Brak pliku użytkowników",
                      f"Nie znaleziono pliku profili:\n{path}\n\nUtworzyć minimalny plik z kontem 'admin' / 'admin'?"):
            _write_profiles(path, [DEFAULT_ADMIN_RECORD])
            # zapisz ścieżkę do configu w możliwych aliasach
            cfg.setdefault("profiles", {})["file"] = path
            cfg["profiles.file"] = path
            _save_config(cfg)
            print(f"[RC1][profiles] utworzono {path} z kontem 'admin'/'admin'")
    else:
        # jeśli plik istnieje, ale w configu brak wpisu → uzupełnij
        need_save = False
        if not _norm(cfg.get("profiles", {}).get("file")):
            cfg.setdefault("profiles", {})["file"] = path
            need_save = True
        if not _norm(cfg.get("profiles.file")):
            cfg["profiles.file"] = path
            need_save = True
        if need_save:
            _save_config(cfg)
    return path

def ensure_profiles_and_warn():
    cfg = _load_config()
    path = _ensure_profiles_file(cfg)
    recs = _read_profiles(path)

    if _has_default_admin(recs):
        _warn(
            "Bezpieczeństwo: zmień hasło admina",
            "Wykryto konto 'admin' z domyślnym lub pustym hasłem.\n\n"
            "Dla bezpieczeństwa zmień je w Ustawieniach/Użytkownicy.\n"
            "Ta informacja będzie pokazywana przy starcie, dopóki nie zmienisz hasła."
        )

# auto-run przy imporcie (start programu)
try:
    ensure_profiles_and_warn()
except Exception as e:
    print(f"[RC1][profiles] ERROR: {e}")

if __name__ == "__main__":
    ensure_profiles_and_warn()
