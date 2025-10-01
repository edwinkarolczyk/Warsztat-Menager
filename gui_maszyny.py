from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager, resolve_under_root
from ui_theme import ensure_theme_applied

logger = logging.getLogger(__name__)

try:  # pragma: no cover - fallback dla środowisk testowych
    from logger import get_logger
except Exception:  # pragma: no cover - logger opcjonalny

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


logger = get_logger(__name__)

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


def _load_machines_list(abs_path: str) -> list[dict]:
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [row for row in data["items"] if isinstance(row, dict)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        logger.error("[Maszyny] Nieobsługiwany format w %s", abs_path)
        return []
    except Exception:
        logger.exception("[Maszyny] Błąd czytania %s", abs_path)
        return []


def load_machines_from_config(config_manager) -> list[dict]:
    try:
        cfg = {}
        cm = _resolve_config_manager(config_manager)
        if cm is not None:
            if hasattr(cm, "load") and callable(getattr(cm, "load")):
                cfg = cm.load()
            else:
                cfg = getattr(cm, "merged", {}) or {}
    except Exception:
        cfg = {}

    abs_path = resolve_under_root(cfg, ("machines", "rel_path"))
    if not abs_path:
        messagebox.showwarning(
            "Maszyny",
            "Nie ustawiono relatywnej ścieżki 'maszyny/…' względem Folderu WM (root).",
        )
        logger.warning("[Maszyny] Brak machines.rel_path albo paths.data_root")
        return []
    if not os.path.exists(abs_path):
        messagebox.showwarning("Maszyny", f"Plik maszyn nie istnieje:\n{abs_path}")
        logger.error("[Maszyny] Brak pliku: %s", abs_path)
        return []
    items = _load_machines_list(abs_path)
    logger.info(
        "[Maszyny] root=%s | rel=%s | abs=%s | records=%s",
        (cfg.get("paths") or {}).get("data_root"),
        (cfg.get("machines") or {}).get("rel_path"),
        abs_path,
        len(items),
    )
    return items


def _render_machines_list(parent: tk.Misc, machines: list[dict]) -> ttk.Treeview:
    tree = ttk.Treeview(
        parent,
        columns=("id", "kod", "nazwa", "lokacja", "status"),
        show="headings",
    )
    for col, text in (
        ("id", "ID"),
        ("kod", "Kod"),
        ("nazwa", "Nazwa"),
        ("lokacja", "Lokacja"),
        ("status", "Status"),
    ):
        tree.heading(col, text=text)
        tree.column(col, width=120, stretch=True, anchor="w")
    for machine in machines:
        tree.insert(
            "",
            "end",
            values=(
                machine.get("id", ""),
                machine.get("kod", ""),
                machine.get("nazwa", ""),
                machine.get("lokacja", ""),
                machine.get("status", ""),
            ),
        )
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.configure(yscrollcommand=scrollbar.set)
    return tree


def _open_machines_panel(root, container, config_manager) -> ttk.Treeview | None:
    for child in container.winfo_children():
        child.destroy()

    label_kwargs = {}
    if hasattr(container, "cget"):
        try:
            label_kwargs["bg"] = container.cget("bg")
        except Exception:
            pass
    if label_kwargs.get("bg"):
        label_kwargs.setdefault("fg", "#d1d5db")

    machines = load_machines_from_config(config_manager)

    if not Renderer:
        logger.warning(
            "[Maszyny] Renderer hali niedostępny – pokażę listę tekstową zamiast podglądu."
        )
    else:  # pragma: no cover - renderer opcjonalny
        try:
            Renderer.draw(machines)
        except Exception:
            logger.exception("[Maszyny] Błąd renderowania podglądu hali")

    if not machines:
        tk.Label(
            container,
            text="Brak rekordów maszyn lub niepoprawna ścieżka.",
            **label_kwargs,
        ).pack(pady=12)
        return None

    return _render_machines_list(container, machines)


class MaszynyGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.container: tk.Frame | None = None
        self.tree: ttk.Treeview | None = None
        self._build_ui()

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

        self.container = tk.Frame(main, bg=bg)
        self.container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree = _open_machines_panel(self.root, self.container, CONFIG_MANAGER)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")
    ensure_theme_applied(root)
    MaszynyGUI(root)
    root.mainloop()
