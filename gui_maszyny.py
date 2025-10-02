from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager
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


def _load_machines_json(abs_path: str) -> list[dict]:
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [row for row in data["items"] if isinstance(row, dict)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        logger.error("[Maszyny] Nieobsługiwany format JSON: %s", abs_path)
        return []
    except Exception:
        logger.exception("[Maszyny] Błąd czytania: %s", abs_path)
        return []


def _resolve_machines_path(cfg_mgr) -> str | None:
    try:
        cfg = cfg_mgr.load()
    except Exception:
        cfg = {}
    root = ((cfg.get("paths") or {}).get("data_root") or "").strip()
    rel = ((cfg.get("machines") or {}).get("rel_path") or "").strip()
    if not (root and rel):
        return None
    return os.path.join(root, rel)


def _render_list(parent: tk.Misc, items: list[dict]) -> ttk.Treeview:
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
    for machine in items:
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


def _open_machines_panel(
    root,
    container,
    config_manager,
    Renderer=None,
) -> ttk.Treeview | None:
    for child in container.winfo_children():
        child.destroy()

    label_kwargs: dict[str, str] = {}
    if hasattr(container, "cget"):
        try:
            label_kwargs["bg"] = container.cget("bg")
        except Exception:
            pass
    if label_kwargs.get("bg"):
        label_kwargs.setdefault("fg", "#d1d5db")

    cm = _resolve_config_manager(config_manager)
    if cm is None:
        logger.warning("[Maszyny] Brak aktywnego ConfigManagera")
        messagebox.showwarning(
            "Maszyny",
            "Nie można odczytać konfiguracji maszyn. Ustaw Folder WM (root).",
        )
        tk.Label(container, text="Brak konfiguracji maszyn.", **label_kwargs).pack(pady=12)
        return None

    abs_path = _resolve_machines_path(cm)
    if not abs_path:
        logger.warning("[Maszyny] Brak paths.data_root lub machines.rel_path")
        messagebox.showwarning(
            "Maszyny",
            "Ustaw Folder WM (root) i relatywną ścieżkę pliku maszyn.",
        )
        tk.Label(
            container,
            text="Brak konfiguracji ścieżki maszyn.",
            **label_kwargs,
        ).pack(pady=12)
        return None
    if not os.path.exists(abs_path):
        logger.error("[Maszyny] Plik nie istnieje: %s", abs_path)
        messagebox.showwarning("Maszyny", f"Plik maszyn nie istnieje:\n{abs_path}")
        tk.Label(container, text="Plik maszyn nie istnieje.", **label_kwargs).pack(pady=12)
        return None

    items = _load_machines_json(abs_path)
    logger.info("[Maszyny] abs=%s | records=%s", abs_path, len(items))
    if not items:
        tk.Label(
            container,
            text="Brak rekordów maszyn w pliku.",
            **label_kwargs,
        ).pack(pady=12)
        return None

    if not Renderer:
        logger.warning("[Maszyny] Renderer hali niedostępny – używam widoku listy.")
        return _render_list(container, items)

    try:  # pragma: no cover - renderer opcjonalny
        if callable(Renderer):
            try:
                renderer_instance = Renderer(container, items)
            except TypeError:
                renderer_instance = Renderer(root, container, items)
            render = getattr(renderer_instance, "render", None)
            if callable(render):
                render()
                return None
            raise AttributeError("Renderer instance missing render()")
        render_callable = getattr(Renderer, "render", None)
        if callable(render_callable):
            render_callable(container, items)
            return None
        draw_callable = getattr(Renderer, "draw", None)
        if callable(draw_callable):
            draw_callable(items)
            return None
        raise TypeError("Renderer does not expose render/draw API")
    except Exception:
        logger.exception("[Maszyny] Renderer zgłosił wyjątek – fallback na listę.")
        return _render_list(container, items)

    return None


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

        self.tree = _open_machines_panel(
            self.root,
            self.container,
            CONFIG_MANAGER,
            Renderer=Renderer,
        )


def panel_maszyny(root, frame, login=None, rola=None):
    """Adapter używany przez główny panel aplikacji."""

    _open_machines_panel(root, frame, CONFIG_MANAGER, Renderer=Renderer)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")
    ensure_theme_applied(root)
    MaszynyGUI(root)
    root.mainloop()
