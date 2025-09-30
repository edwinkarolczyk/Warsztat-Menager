from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager
from ui_theme import ensure_theme_applied

logger = logging.getLogger(__name__)


def _get_settings_path_key():
    """
    Zwraca (klucz, domyślny_plik) dla ścieżki maszyn.
    Nie zmienia logiki – tylko centralizuje źródło prawdy.
    """

    # Domyślny plik jak w Rozwiniecie (ustal tu jedną ścieżkę docelową):
    default_file = os.path.join("data", "maszyny", "maszyny.json")
    # Klucz w Ustawieniach – jeśli masz inny, zmień nazwę tutaj 1:1:
    return "paths.maszyny", default_file


def _get_machines_file_from_settings():
    """
    Pobiera ścieżkę do pliku maszyn z CONFIG/USTAWIEŃ lub zwraca domyślną.
    """

    key, default_file = _get_settings_path_key()
    path = None
    try:
        # preferencja: start.CONFIG_MANAGER (jeśli jest)
        try:
            from start import CONFIG_MANAGER  # lazy import, unik cykli

            if CONFIG_MANAGER:
                path = CONFIG_MANAGER.get(key, default=default_file)
        except Exception:
            path = None
        # fallback: plik konfiguracyjny/zmienna środowiskowa (jeśli stosowane)
        if not path:
            path = os.environ.get("WM_MASZYNY_FILE", default_file)
    except Exception as e:
        logger.warning("[WM-DBG][Maszyny] Nie udało się pobrać ścieżki z ustawień: %r", e)
        path = default_file

    # Normalizacja i log
    try:
        path = os.path.normpath(path)
    except Exception:
        pass
    logger.info("[WM-DBG][Maszyny] Źródło prawdy: %s", path)
    return path


MACHINES_FILE = _get_machines_file_from_settings()


try:  # pragma: no cover - fallback dla środowisk testowych
    from logger import get_logger
except Exception:  # pragma: no cover - logger opcjonalny
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


logger = get_logger(__name__)


def _fetch_real_machines() -> list[str]:
    """Zbiera listę identyfikatorów maszyn z docelowego pliku."""

    machines_file = MACHINES_FILE
    coll = "NN"
    try:
        cfg_mgr = ConfigManager()
        coll = str(cfg_mgr.get("tools.default_collection", coll) or coll)
    except Exception:
        coll = "NN"

    records: list[dict] = []
    try:
        with open(machines_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        logger.warning("[WM-DBG][MASZYNY] Brak pliku z maszynami: %s", machines_file)
        payload = []
    except Exception as exc:  # pragma: no cover - log błędu wczytywania
        logger.error(
            "[ERROR][MASZYNY] Błąd wczytywania pliku maszyn %s: %s",
            machines_file,
            exc,
        )
        payload = []

    if isinstance(payload, dict):
        if isinstance(payload.get("maszyny"), list):
            records = payload.get("maszyny", [])
        elif isinstance(payload.get("items"), list):
            records = payload.get("items", [])
        else:
            records = [v for v in payload.values() if isinstance(v, dict)]
    elif isinstance(payload, list):
        records = payload

    items: list[str] = []
    seen: set[str] = set()
    for data in records:
        if not isinstance(data, dict):
            continue

        dcoll = str(data.get("kolekcja", coll) or coll)
        if dcoll != coll:
            continue

        ident = (
            data.get("ID")
            or data.get("id")
            or data.get("nr")
            or data.get("sn")
        )
        name = data.get("nazwa") or data.get("name") or ""
        ident = (
            (str(ident).strip() if ident is not None else "")
            .strip()
        )
        label = ident or str(name).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        items.append(label)

    items.sort(key=lambda x: (len(x), x))
    logger.info(
        "[WM-DBG][MASZYNY] źródło=%s coll=%s count=%s",
        machines_file,
        coll,
        len(items),
    )
    return items


def _bind_machines_to_view(self, items: list[str]) -> None:
    """Podłącza listę maszyn do dostępnego widoku."""

    try:
        if hasattr(self, "tree") and self.tree is not None:
            try:
                for iid in self.tree.get_children():
                    self.tree.delete(iid)
                for lbl in items:
                    self.tree.insert("", "end", text=lbl, values=(lbl,))
                return
            except Exception:
                pass

        if hasattr(self, "machines_list") and self.machines_list is not None:
            try:
                self.machines_list["values"] = tuple(items)
                if items:
                    try:
                        self.machines_list.current(0)
                    except Exception:
                        pass
                return
            except Exception:
                try:
                    self.machines_list.delete(0, "end")
                    for lbl in items:
                        self.machines_list.insert("end", lbl)
                    return
                except Exception:
                    pass

        logger.info("[WM-DBG][MASZYNY] Nie znaleziono widoku do podpięcia danych.")
    except Exception as exc:  # pragma: no cover - log błędu podpinania
        logger.error(f"[ERROR][MASZYNY] Podpinanie danych do widoku: {exc}")


def _wm_init_hook_after_ui_build(self):
    try:
        data = _fetch_real_machines()
        _bind_machines_to_view(self, data)
    except Exception as _exc:  # pragma: no cover - log błędu inicjalizacji
        logger.error(f"[ERROR][MASZYNY] Inicjalizacja listy maszyn: {_exc}")


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._build_ui()
        _wm_init_hook_after_ui_build(self)

    def _build_ui(self) -> None:
        bg = self.root["bg"] if "bg" in self.root.keys() else "#111214"
        main = tk.Frame(self.root, bg=bg)
        main.pack(fill="both", expand=True)

        header = tk.Label(
            main,
            text="Lista dostępnych maszyn",
            bg=bg,
            fg="#d1d5db",
            anchor="w",
            font=("TkDefaultFont", 12, "bold"),
        )
        header.pack(fill="x", padx=12, pady=(12, 6))

        tree_container = tk.Frame(main, bg=bg)
        tree_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree = ttk.Treeview(
            tree_container,
            columns=("nazwa",),
            show="tree headings",
            selectmode="browse",
            height=18,
        )
        self.tree.heading("nazwa", text="Maszyna")
        self.tree.column("#0", width=0, stretch=False)
        self.tree.column("nazwa", width=320, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            tree_container, orient="vertical", command=self.tree.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")
    ensure_theme_applied(root)
    MaszynyGUI(root)
    root.mainloop()
