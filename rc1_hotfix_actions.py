# -*- coding: utf-8 -*-
# RC1: hotfix dispatcher (BOM export/import + Audyt)

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict


def _log(msg: str) -> None:
    print(f"[RC1][hotfix] {msg}")


CONFIG_PATH = os.path.join(os.getcwd(), "config.json")


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
        _log(f"config.save.error: {e}")


def _ask_open_file(filters=None) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        types = [(f, f) for f in (filters or ["*.json", "*.csv", "*.xlsx"])]
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


def action_bom_export_current(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = _config_load()
    src = cfg.get("bom", {}).get("file") or cfg.get("bom.file")
    if not src or not os.path.exists(src):
        _warn("Eksport BOM", "Brak pliku BOM w ustawieniach (bom.file).")
        return {"ok": False}
    dst = _ask_save_file(os.path.basename(src))
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
    sel = _ask_open_file((params or {}).get("filters"))
    if not sel:
        return {"ok": False, "msg": "cancelled"}
    cfg = _config_load()
    cfg.setdefault("bom", {})
    cfg["bom"]["file"] = sel
    cfg["bom.file"] = sel
    _config_save(cfg)
    _info("Import BOM", f"Ustawiono plik BOM:\n{sel}")
    return {"ok": True, "path": sel}


def action_wm_audit_run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        import audit
    except Exception as e:
        _error("Audyt WM", f"Brak modułu audit: {e}")
        return {"ok": False, "msg": "audit missing"}
    try:
        res = getattr(audit, "run", None)
        if callable(res):
            out = res() or {}
            ok = bool(out.get("ok")) if isinstance(out, dict) else True
            msg = out.get("msg", "") if isinstance(out, dict) else str(out)
            path = out.get("path") if isinstance(out, dict) else None
            (_info if ok else _warn)(
                "Audyt WM", msg or ("OK" if ok else "Problemy wykryte")
            )
            return {"ok": ok, "msg": msg, "path": path}
        _error("Audyt WM", "Brak funkcji audit.run()")
        return {"ok": False, "msg": "audit.run missing"}
    except Exception as e:
        _error("Audyt WM", f"Błąd audytu:\n{e}")
        return {"ok": False, "msg": str(e)}


_HOTFIX_ACTIONS: Dict[str, Any] = {
    "bom.export_current": action_bom_export_current,
    "bom.import_dialog": action_bom_import_dialog,
    "wm_audit.run": action_wm_audit_run,
}


def _install_into_dispatch() -> None:
    try:
        import dispatch
    except Exception as e:
        _log(f"dispatch.import.error: {e}")
        return
    # A) globalny słownik akcji
    try:
        actions = getattr(dispatch, "ACTIONS", None)
        if isinstance(actions, dict):
            for key, handler in _HOTFIX_ACTIONS.items():
                if key not in actions:
                    actions[key] = handler
            _log("registered via ACTIONS")
            return
    except Exception:
        pass
    # B) wrap execute (fallback)
    try:
        orig = getattr(dispatch, "execute", None)
        if callable(orig):
            def wrapped(action: str, params: Dict[str, Any] | None = None):
                if action in _HOTFIX_ACTIONS:
                    return _HOTFIX_ACTIONS[action](params or {})
                return orig(action, params)

            setattr(dispatch, "execute", wrapped)
            _log("wrapped execute")
    except Exception as e:
        _log(f"execute.wrap.error: {e}")


_install_into_dispatch()
_log("ready")
