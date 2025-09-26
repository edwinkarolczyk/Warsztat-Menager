import os
import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, Optional

try:
    from wm_log import dbg as wm_dbg, info as wm_info, err as wm_err
except ImportError:  # pragma: no cover - środowiska testowe bez wm_log
    def wm_dbg(*args, **kwargs):
        return None

    def wm_info(*args, **kwargs):
        return None

    def wm_err(*args, **kwargs):
        return None
from backend import updater

try:
    # audyt jest w podkatalogu
    from backend.audit import wm_audit_runtime as wm_audit
except Exception:
    wm_audit = None


class ActionHandlers:
    """
    Prosty, bezinwazyjny handler akcji z settings_schema.json:
      - dialog.open_file  -> wybór pliku z dysku
      - dialog.open_dir   -> wybór katalogu z dysku
      - os.open_path      -> otwarcie ścieżki w eksploratorze
    """

    def __init__(self, settings_state: Dict[str, Any], on_change=None):
        self.state = settings_state
        self.on_change = on_change or (lambda k, v: None)

    # -------- helpers --------

    def _set_key(self, key: str, value: Any):
        self.state[key] = value
        try:
            self.on_change(key, value)
        except Exception:
            pass

    def _ensure_tk_root(self) -> tk.Tk:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        return root

    def _initial_dir(self, params: Dict[str, Any]) -> Optional[str]:
        init_key = params.get("initialdir_key")
        if init_key and self.state.get(init_key):
            return str(self.state.get(init_key))
        if self.state.get("paths.data_root"):
            return str(self.state.get("paths.data_root"))
        return None

    # -------- actions --------

    def dialog_open_file(self, params: Dict[str, Any]):
        wm_dbg("dispatch.dialog_open_file", "enter", params=params)
        write_key = params.get("write_to_key")
        if not write_key:
            wm_err("dispatch.dialog_open_file", "missing write_to_key")
            return
        filters = params.get("filters") or []
        if filters:
            filetypes = [("Dozwolone pliki", " ".join(filters)), ("Wszystkie pliki", "*.*")]
        else:
            filetypes = [("Wszystkie pliki", "*.*")]

        initialdir = self._initial_dir(params)

        root = self._ensure_tk_root()
        try:
            path = filedialog.askopenfilename(parent=root,
                                              filetypes=filetypes,
                                              initialdir=initialdir)
        finally:
            root.destroy()

        if path:
            self._set_key(write_key, path)
            wm_info("dispatch.dialog_open_file", "picked", key=write_key, path=path)

    def dialog_open_dir(self, params: Dict[str, Any]):
        wm_dbg("dispatch.dialog_open_dir", "enter", params=params)
        write_key = params.get("write_to_key")
        if not write_key:
            wm_err("dispatch.dialog_open_dir", "missing write_to_key")
            return

        initialdir = self._initial_dir(params)

        root = self._ensure_tk_root()
        try:
            path = filedialog.askdirectory(parent=root,
                                           initialdir=initialdir,
                                           mustexist=True)
        finally:
            root.destroy()

        if path:
            self._set_key(write_key, path)
            wm_info("dispatch.dialog_open_dir", "picked", key=write_key, path=path)
            # Autotworzenie podkatalogów, jeśli podane:
            for sub in params.get("autocreate_subdirs", []) or []:
                try:
                    os.makedirs(os.path.join(path, sub), exist_ok=True)
                except Exception:
                    pass

    def os_open_path(self, params: Dict[str, Any]):
        wm_dbg("dispatch.os_open_path", "enter", params=params)
        key = params.get("path_key")
        if not key:
            wm_err("dispatch.os_open_path", "missing path_key")
            return
        path = self.state.get(key)
        if not path:
            return
        try:
            os.startfile(path)  # Windows
        except Exception:
            pass
        else:
            wm_info("dispatch.os_open_path", "opened", key=key)

    # -------- dispatcher --------

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None):
        wm_dbg("dispatch.execute", "enter", action=action, params=params or {})
        params = params or {}
        try:
            # akcje dialogów i OS:
            if action == "dialog.open_file":
                return self.dialog_open_file(params)
            if action == "dialog.open_dir":
                return self.dialog_open_dir(params)
            if action == "os.open_path":
                return self.os_open_path(params)

            # --- NOWE: akcje updatera -----------------------------------
            if action == "updater.git_pull":
                res = updater.git_pull()
                # możesz pokazać notyfikację w UI na podstawie res
                wm_info("dispatch.execute", "updater.git_pull", result=res)
                return res

            if action == "updater.pull_branch":
                # gałąź bierzemy ze stanu przez klucz podany w params
                branch_key = params.get("branch_key")
                branch = self.state.get(branch_key) if branch_key else None
                res = updater.pull_branch(branch or "")
                wm_info("dispatch.execute", "updater.pull_branch", branch=branch, result=res)
                return res

            if action == "updater.backup_zip":
                res = updater.backup_zip()
                wm_info("dispatch.execute", "updater.backup_zip", result=res)
                return res

            if action == "updater.restore_dialog":
                # otwórz okno wyboru ZIP i przywróć
                # (używamy istniejącego mechanizmu dialogu plików)
                # tymczasowo wybór pliku tutaj:
                self.dialog_open_file({"filters": ["*.zip"], "write_to_key": "__tmp_restore_zip"})
                zip_path = self.state.get("__tmp_restore_zip")
                if zip_path:
                    res = updater.restore_from_zip(zip_path)
                    wm_info("dispatch.execute", "updater.restore_from_zip", zip=zip_path, result=res)
                    return res
                wm_info("dispatch.execute", "restore_cancelled")
                return {"ok": False, "msg": "Anulowano wybór pliku ZIP."}

            # --- NOWE: audyt WM ------------------------------------------
            if action == "wm_audit.run":
                if wm_audit is None:
                    wm_err("dispatch.execute", "wm_audit missing")
                    return {"ok": False, "msg": "Moduł audytu nie jest dostępny."}
                res = wm_audit.run()
                wm_info("dispatch.execute", "wm_audit.run", result=res)
                return res

            wm_dbg("dispatch.execute", "unknown action", action=action)
        except Exception as e:
            wm_err("dispatch.execute", "exception", e, action=action, params=params)


# Wygodny singleton do prostego wpięcia w GUI:
_GLOBAL: Optional[ActionHandlers] = None


def bind(settings_state: Dict[str, Any], on_change=None):
    global _GLOBAL
    _GLOBAL = ActionHandlers(settings_state, on_change)
    return _GLOBAL


def execute(action: Optional[str], params: Optional[Dict[str, Any]] = None):
    if not action:
        return
    if _GLOBAL is None:
        raise RuntimeError("ActionHandlers niezbindowany. Wywołaj bind(state, on_change).")
    return _GLOBAL.execute(action, params or {})
