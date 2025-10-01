from __future__ import annotations

import json
import os
import tkinter as tk
import tkinter.messagebox as messagebox
from tkinter import ttk

from config_manager import ConfigManager
from ui_theme import ensure_theme_applied

try:  # pragma: no cover - fallback dla środowisk testowych
    from logger import get_logger
except Exception:  # pragma: no cover - logger opcjonalny
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


log = get_logger(__name__)
logger = log

Renderer = None

try:  # pragma: no cover - CONFIG_MANAGER jest opcjonalny
    from start import CONFIG_MANAGER
except Exception:  # pragma: no cover - środowiska testowe
    CONFIG_MANAGER = None


def _resolve_config_manager(cm: ConfigManager | None) -> ConfigManager | None:
    if cm is not None:
        return cm
    try:
        return ConfigManager()
    except Exception:  # pragma: no cover - fallback gdy ConfigManager nie działa
        return None


def load_machines_from_config(config_manager) -> list[dict]:
    """Wczytaj listę maszyn ze ścieżki podanej w config.json (klucz: machines.file)."""

    machines: list[dict] = []
    path: str | None = None

    cm = _resolve_config_manager(config_manager)
    try:
        if cm is not None:
            if hasattr(cm, "load") and callable(getattr(cm, "load")):
                cfg = cm.load()
            else:
                cfg = getattr(cm, "merged", {}) or {}
            path = cfg.get("machines", {}).get("file")
    except Exception:
        path = None

    if not path:
        logger.warning("[Maszyny] Brak ustawionej ścieżki (config['machines.file']).")
        messagebox.showwarning(
            "Maszyny", "Nie ustawiono źródła prawdy dla maszyn w Ustawieniach."
        )
        logger.info("[Maszyny] Wczytano %s rekordów (brak ścieżki w config).", len(machines))
        return machines

    if not os.path.exists(path):
        logger.error("[Maszyny] Plik źródła prawdy nie istnieje: %s", path)
        messagebox.showwarning("Maszyny", f"Plik maszyn nie istnieje:\n{path}")
        logger.info("[Maszyny] Wczytano %s rekordów z %s", len(machines), path)
        return machines

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if "items" in data:
                machines = [row for row in data["items"] if isinstance(row, dict)]
            elif "maszyny" in data:
                machines = [row for row in data["maszyny"] if isinstance(row, dict)]
            else:
                logger.error(
                    "[Maszyny] Nieobsługiwany format dict w pliku: %s", path
                )
                messagebox.showwarning(
                    "Maszyny",
                    (
                        "Plik "
                        f"{path} ma nieobsługiwany format (brak 'items' ani "
                        "'maszyny')."
                    ),
                )
                logger.info("[Maszyny] Wczytano %s rekordów z %s", len(machines), path)
                return []
        elif isinstance(data, list):
            machines = [row for row in data if isinstance(row, dict)]
        else:
            logger.error("[Maszyny] Nieobsługiwany format w pliku: %s", path)
            messagebox.showwarning(
                "Maszyny", f"Plik {path} ma nieobsługiwany format."
            )
            logger.info("[Maszyny] Wczytano %s rekordów z %s", len(machines), path)
            return []
        logger.info("[Maszyny] Wczytano %s rekordów z %s", len(machines), path)
        return machines
    except Exception as e:  # pragma: no cover - logowanie błędów IO
        logger.exception("[Maszyny] Błąd przy wczytywaniu %s", path)
        messagebox.showwarning("Maszyny", f"Błąd przy wczytywaniu pliku:\n{e}")
        logger.info("[Maszyny] Wczytano %s rekordów z %s", len(machines), path)
        return []


def _prepare_machine_labels(rows: list[dict]) -> list[str]:
    """Przekształć rekordy maszyn na posortowane etykiety do wyświetlenia."""

    items: list[str] = []
    seen: set[str] = set()

    for row in rows or []:
        try:
            ident = (
                row.get("ID")
                or row.get("id")
                or row.get("nr")
                or row.get("nr_ewid")
                or row.get("sn")
            )
            name = row.get("nazwa") or row.get("name") or ""
            ident = (str(ident).strip() if ident is not None else "").strip()
            label = ident or str(name).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            items.append(label)
        except Exception as exc:  # pragma: no cover - defensywne logowanie
            logger.warning("[Maszyny] Nie mogę przetworzyć rekordu: %s", exc)

    items.sort(key=lambda value: (len(value), value))
    logger.info("[Maszyny] Przygotowano %s etykiet do widoku", len(items))
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

        log.info("[WM-DBG][MASZYNY] Nie znaleziono widoku do podpięcia danych.")
    except Exception as exc:  # pragma: no cover - log błędu podpinania
        log.error(f"[ERROR][MASZYNY] Podpinanie danych do widoku: {exc}")


def _wm_init_hook_after_ui_build(self):
    try:
        machines = load_machines_from_config(CONFIG_MANAGER)
        labels = _prepare_machine_labels(machines)
        _bind_machines_to_view(self, labels)
        if Renderer is None:
            logger.warning(
                "[Maszyny] Renderer hali nie jest dostępny – pomijam podgląd."
            )
        else:  # pragma: no cover - renderer opcjonalny
            try:
                Renderer.draw(machines)
            except Exception:
                logger.exception("[Maszyny] Błąd renderowania podglądu hali")
    except Exception as _exc:  # pragma: no cover - log błędu inicjalizacji
        log.error(f"[ERROR][MASZYNY] Inicjalizacja listy maszyn: {_exc}")


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
