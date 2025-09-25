import os
import json
import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any


class ActionHandlers:
    def __init__(self, settings_state: Dict[str, Any], on_change=None):
        """
        settings_state: dict z aktualnymi ustawieniami (klucz -> wartość)
        on_change: callback(key:str, value:Any) wywoływany po zmianie
        """
        self.state = settings_state
        self.on_change = on_change or (lambda k, v: None)

    # --- helpers -------------------------------------------------------------

    def _set_key(self, key: str, value: Any):
        self.state[key] = value
        try:
            self.on_change(key, value)
        except Exception:
            pass

    def _ensure_tk(self):
        # Utwórz ukrytego roota tylko na czas dialogu
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        return root

    # --- actions -------------------------------------------------------------

    def dialog_open_file(self, params: Dict[str, Any]):
        """
        params:
          - filters: list[str] np. ["*.json","*.csv"]
          - write_to_key: str
          - initialdir_key (opcjonalne): str -> odczyta katalog startowy z self.state
        """
        write_key = params.get("write_to_key")
        if not write_key:
            return

        filetypes = []
        filters = params.get("filters") or []
        if filters:
            pattern = " ".join(filters)
            filetypes = [("Dozwolone pliki", pattern), ("Wszystkie pliki", "*.*")]
        else:
            filetypes = [("Wszystkie pliki", "*.*")]

        initialdir = None
        init_key = params.get("initialdir_key")
        if init_key and self.state.get(init_key):
            initialdir = self.state.get(init_key)
        elif self.state.get("paths.data_root"):
            initialdir = self.state.get("paths.data_root")

        root = self._ensure_tk()
        try:
            path = filedialog.askopenfilename(parent=root, filetypes=filetypes, initialdir=initialdir)
        finally:
            root.destroy()

        if path:
            self._set_key(write_key, path)

    def dialog_open_dir(self, params: Dict[str, Any]):
        """
        params:
          - write_to_key: str
          - initialdir_key (opcjonalne): str
          - autocreate_subdirs (opcjonalne): list[str] -> utwórz podkatalogi po wyborze
        """
        write_key = params.get("write_to_key")
        if not write_key:
            return

        initialdir = None
        init_key = params.get("initialdir_key")
        if init_key and self.state.get(init_key):
            initialdir = self.state.get(init_key)
        elif self.state.get("paths.data_root"):
            initialdir = self.state.get("paths.data_root")

        root = self._ensure_tk()
        try:
            path = filedialog.askdirectory(parent=root, initialdir=initialdir, mustexist=True)
        finally:
            root.destroy()

        if path:
            self._set_key(write_key, path)
            # ewentualne auto-tworzenie podkatalogów
            subdirs = params.get("autocreate_subdirs") or []
            for name in subdirs:
                try:
                    os.makedirs(os.path.join(path, name), exist_ok=True)
                except Exception:
                    pass

    def os_open_path(self, params: Dict[str, Any]):
        """
        params:
          - path_key: str  (weź ścieżkę ze stanu i otwórz w Explorerze)
        """
        key = params.get("path_key")
        if not key:
            return
        path = self.state.get(key)
        if not path:
            return
        try:
            os.startfile(path)  # Windows
        except Exception:
            pass

    # --- public API ----------------------------------------------------------

    def execute(self, action: str, params: Dict[str, Any] | None = None):
        params = params or {}
        if action == "dialog.open_file":
            return self.dialog_open_file(params)
        if action == "dialog.open_dir":
            return self.dialog_open_dir(params)
        if action == "os.open_path":
            return self.os_open_path(params)
        # brakująca akcja = no-op


# Szybki singleton – jeżeli chcesz używać bez własnej instancji:
_global_instance: ActionHandlers | None = None


def bind(settings_state: Dict[str, Any], on_change=None):
    global _global_instance
    _global_instance = ActionHandlers(settings_state, on_change)
    return _global_instance


def execute(action: str, params: Dict[str, Any] | None = None):
    if _global_instance is None:
        raise RuntimeError("ActionHandlers niezabindowany. Wywołaj bind(state).")
    return _global_instance.execute(action, params or {})
