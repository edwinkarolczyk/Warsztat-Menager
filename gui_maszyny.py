from __future__ import annotations

import os, json
import tkinter as tk
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


def _fetch_real_machines() -> list[str]:
    """Zbiera listę identyfikatorów maszyn z katalogu machines_dir."""

    machines_dir: str | None = None
    coll = "NN"
    try:
        cfg_mgr = ConfigManager()
        machines_dir = cfg_mgr.get("paths.machines_dir", None)
        coll = str(cfg_mgr.get("tools.default_collection", coll) or coll)
    except Exception:
        machines_dir = None
        coll = "NN"

    machines_dir = (
        str(machines_dir)
        if machines_dir
        else os.path.join(os.getcwd(), "data", "maszyny")
    )

    items: list[str] = []
    seen: set[str] = set()
    try:
        for root, _dirs, files in os.walk(machines_dir):
            for fn in files:
                if not fn.lower().endswith(".json"):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
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
    except Exception as exc:  # pragma: no cover - log błędu wczytywania
        log.error(f"[ERROR][MASZYNY] Błąd wczytywania listy maszyn: {exc}")

    items.sort(key=lambda x: (len(x), x))
    log.info(
        f"[WM-DBG][MASZYNY] źródło={machines_dir} coll={coll} count={len(items)}"
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

        log.info("[WM-DBG][MASZYNY] Nie znaleziono widoku do podpięcia danych.")
    except Exception as exc:  # pragma: no cover - log błędu podpinania
        log.error(f"[ERROR][MASZYNY] Podpinanie danych do widoku: {exc}")


def _wm_init_hook_after_ui_build(self):
    try:
        machines = _fetch_real_machines()
        try:
            logger.info("[WM-DBG][Maszyny] Wczytano rekordów: %s", len(machines))
        except Exception:
            pass
        _bind_machines_to_view(self, machines)
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
