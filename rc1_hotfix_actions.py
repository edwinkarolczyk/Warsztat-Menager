# -*- coding: utf-8 -*-
# rc1_hotfix_actions.py
# Minimalny hotfix RC1: rejestruje brakujące akcje dla BOM i audytu
# Nie zmienia istniejącej architektury – tylko delikatnie "wstrzykuje" akcje.
# Jeśli dispatcher ma ACTIONS lub register() – użyje ich.
# Jeśli nie – opakuje dispatch.execute() i doda swoje.

from __future__ import annotations

import json
import os
import shutil
import traceback
from pathlib import Path
from typing import Any, Dict

# -- Pomocnicze: lekkie logowanie
def _log(msg: str) -> None:
    print(f"WM|RC1|hotfix|{msg}")

# -- Bezpieczny dostęp do configu (czytamy i zapisujemy config.json)
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _SCRIPT_DIR / "config.json"


def _resolve_config_path() -> Path:
    """Zwraca możliwie najbardziej prawdopodobną ścieżkę do config.json."""

    if _DEFAULT_CONFIG_PATH.exists():
        return _DEFAULT_CONFIG_PATH
    cwd_path = Path(os.getcwd()) / "config.json"
    return cwd_path if cwd_path.exists() else _DEFAULT_CONFIG_PATH


CONFIG_PATH = _resolve_config_path()


def _config_load() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _config_save(cfg: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log(f"config.save.error: {e.__class__.__name__}: {e}")


# -- GUI helpery (tk filedialog / messagebox – importowane leniwie)
def _ask_open_file(filters=None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        types = [("Wszystkie pliki", "*.*")]
        if filters:
            types = [(f, f) for f in filters]
        path = filedialog.askopenfilename(filetypes=types)
        root.destroy()
        return path or None
    except Exception as e:
        _log(f"filedialog.open.error: {e}")
        return None


def _ask_save_file(default_name="bom.json") -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=default_name
        )
        root.destroy()
        return path or None
    except Exception as e:
        _log(f"filedialog.save.error: {e}")
        return None


def _info(title: str, msg: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, msg)
        root.destroy()
    except Exception:
        _log(f"INFO: {title}: {msg}")


def _warn(title: str, msg: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(title, msg)
        root.destroy()
    except Exception:
        _log(f"WARN: {title}: {msg}")


def _error(title: str, msg: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, msg)
        root.destroy()
    except Exception:
        _log(f"ERROR: {title}: {msg}")


# === Implementacje akcji ===

def action_bom_export_current(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Eksport BOM:
    - Szuka ścieżki źródłowej w config['bom.file']
    - Pyta gdzie zapisać
    - Kopiuje plik 1:1 (nie przetwarza zawartości)
    """
    cfg = _config_load()
    src = cfg.get("bom", {}).get("file") or cfg.get("bom.file")
    if not src or not os.path.exists(src):
        _warn(
            "Eksport BOM",
            "Nie znaleziono ścieżki BOM w ustawieniach (bom.file) lub plik nie istnieje.",
        )
        return {"ok": False, "msg": "BOM source missing"}

    dst = _ask_save_file(os.path.basename(src) if isinstance(src, str) else "bom.json")
    if not dst:
        return {"ok": False, "msg": "cancelled"}

    try:
        shutil.copyfile(src, dst)
        _info("Eksport BOM", f"Zapisano do:\n{dst}")
        return {"ok": True, "dst": dst}
    except Exception as e:
        _error("Eksport BOM", f"Błąd zapisu:\n{e}")
        return {"ok": False, "msg": str(e)}


def action_bom_import_dialog(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Import BOM (tylko ustawienie ścieżki w configu):
    - Otwiera dialog wyboru pliku (json/csv/xlsx – filtr symboliczny)
    - Zapisuje do config['bom.file'] oraz do struktury z kluczem 'bom':{'file':...} (kompat).
    """
    filters = (params or {}).get("filters") or ["*.json", "*.csv", "*.xlsx"]
    sel = _ask_open_file(filters)
    if not sel:
        return {"ok": False, "msg": "cancelled"}

    cfg = _config_load()
    cfg.setdefault("bom", {})
    cfg["bom"]["file"] = sel
    cfg["bom.file"] = sel  # kompatybilność z logami
    _config_save(cfg)

    _info("Import BOM", f"Ustawiono plik BOM:\n{sel}")
    return {"ok": True, "path": sel}


def action_wm_audit_run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Wywołuje audyt jeśli moduł `audit` udostępnia funkcję run().
    Pokazuje wynik w info/warn.
    """
    try:
        import audit
    except Exception as e:
        _error("Audyt WM", f"Brak modułu audit: {e}")
        return {"ok": False, "msg": "audit module missing"}

    try:
        res = getattr(audit, "run", None)
        if callable(res):
            out = res()
            ok = bool(out.get("ok")) if isinstance(out, dict) else True
            msg = out.get("msg", str(out)) if isinstance(out, dict) else str(out)
            title = "Audyt WM – wynik"
            if ok:
                _info(title, msg or "OK")
            else:
                _warn(title, msg or "Problemy wykryte")
            return {"ok": ok, "msg": msg}
        else:
            _error("Audyt WM", "Brak funkcji audit.run()")
            return {"ok": False, "msg": "audit.run not callable"}
    except Exception as e:
        _error("Audyt WM", f"Błąd uruchomienia audytu:\n{e}")
        return {"ok": False, "msg": str(e)}


# Zestaw akcji do rejestracji
_HOTFIX_ACTIONS: Dict[str, Any] = {
    "bom.export_current": action_bom_export_current,
    "bom.import_dialog": action_bom_import_dialog,
    "wm_audit.run": action_wm_audit_run,
}


# === Rejestracja w istniejącym dispatcherze ===
def _install_into_dispatch() -> None:
    try:
        import dispatch  # oczekiwany moduł wg logów: dispatch.execute|...
    except Exception as e:
        _log(f"dispatch.import.error: {e}")
        return

    # Przypadek A: dispatch ma ACTIONS (dict-like)
    try:
        actions = getattr(dispatch, "ACTIONS", None)
        if isinstance(actions, dict):
            actions.update({k: v for k, v in _HOTFIX_ACTIONS.items() if k not in actions})
            _log("registered via ACTIONS.update")
            return
    except Exception as e:
        _log(f"dispatch.ACTIONS.update.error: {e}")

    # Przypadek B: dispatch ma funkcję register(name, func)
    try:
        register = getattr(dispatch, "register", None)
        if callable(register):
            for k, v in _HOTFIX_ACTIONS.items():
                register(k, v)
            _log("registered via dispatch.register()")
            return
    except Exception as e:
        _log(f"dispatch.register.error: {e}")

    # Przypadek C: brak publicznej rejestracji – zawijamy execute
    try:
        orig_execute = getattr(dispatch, "execute", None)
        if callable(orig_execute):

            def wrapped(action: str, params: Dict[str, Any] | None = None) -> Any:
                if action in _HOTFIX_ACTIONS:
                    _log(f"execute.hotfix:{action}")
                    return _HOTFIX_ACTIONS[action](params or {})
                return orig_execute(action, params)

            setattr(dispatch, "execute", wrapped)
            _log("wrapped dispatch.execute")
        else:
            _log("dispatch.execute missing – nie udało się zainstalować hotfixa")
    except Exception:
        _log("execute.wrap.error: " + traceback.format_exc().splitlines()[-1])


_install_into_dispatch()
_log("ready")
