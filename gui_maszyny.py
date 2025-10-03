from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from config_manager import ConfigManager, resolve_rel
from ui_theme import ensure_theme_applied
from utils_json import load_json

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


def _load_machines_sot(
    config_manager: ConfigManager | None,
    cfg: dict | None = None,
) -> list[dict]:
    """Ładuje SoT maszyn korzystając z ``resolve_rel`` i ``load_json``."""

    data_cfg: dict = {}
    if cfg is not None:
        data_cfg = cfg
    elif config_manager is not None:
        try:
            data_cfg = config_manager.load()
        except Exception:
            logger.exception("[Maszyny] Nie udało się wczytać konfiguracji.")
            data_cfg = {}

    path = resolve_rel(data_cfg, "machines") if data_cfg else None
    if not path:
        logger.warning("[Maszyny] Nie zdefiniowano ścieżki SoT maszyn.")
        return []

    data = load_json(path, default={"maszyny": []})
    if isinstance(data, dict):
        records = [
            row
            for row in data.get("maszyny") or []
            if isinstance(row, dict)
        ]
    else:
        records = [
            row
            for row in data or []
            if isinstance(row, dict)
        ]
    logger.info("[Maszyny] abs=%s | records=%d", path, len(records))
    return records


def _build_list_view(parent: tk.Misc, records: list[dict]) -> ttk.Treeview:
    """Fallback widoku listy maszyn."""

    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    columns = ("id", "kod", "nazwa", "lokacja", "status")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
    for column in columns:
        tree.heading(column, text=column.upper())
        tree.column(column, width=120, stretch=True, anchor="w")
    for record in records:
        tree.insert(
            "",
            "end",
            values=(
                record.get("id", ""),
                record.get("kod", ""),
                record.get("nazwa", ""),
                record.get("lokacja", ""),
                record.get("status", ""),
            ),
        )
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    scrollbar.pack(side="right", fill="y")
    tree.configure(yscrollcommand=scrollbar.set)
    return tree


def _try_build_renderer_or_list(
    parent: tk.Misc,
    config_manager: ConfigManager | None,
    *,
    records: list[dict] | None = None,
    label_kwargs: dict[str, str] | None = None,
    renderer: object | None = None,
) -> ttk.Treeview | None:
    """Próbuje zbudować renderer hali lub fallback listy."""

    items = records if records is not None else _load_machines_sot(config_manager)
    if not items:
        tk.Label(
            parent,
            text="Brak rekordów maszyn w pliku.",
            **(label_kwargs or {}),
        ).pack(pady=12)
        return None

    active_renderer = renderer if renderer is not None else Renderer

    if not active_renderer:
        logger.warning("[Maszyny] Renderer hali niedostępny – używam widoku listy.")
        return _build_list_view(parent, items)

    try:  # pragma: no cover - renderer opcjonalny
        if callable(active_renderer):
            try:
                renderer_instance = active_renderer(parent, items)
            except TypeError:
                renderer_instance = active_renderer(
                    parent.winfo_toplevel(),
                    parent,
                    items,
                )
            render = getattr(renderer_instance, "render", None)
            if callable(render):
                render()
                return None
            raise AttributeError("Renderer instance missing render()")
        render_callable = getattr(active_renderer, "render", None)
        if callable(render_callable):
            render_callable(parent, items)
            return None
        draw_callable = getattr(active_renderer, "draw", None)
        if callable(draw_callable):
            draw_callable(items)
            return None
        raise TypeError("Renderer does not expose render/draw API")
    except Exception as exc:
        logger.warning(
            "[Maszyny] Renderer niedostępny – fallback na listę (%s)",
            exc,
        )
        return _build_list_view(parent, items)


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

    try:
        cfg = cm.load()
    except Exception:
        logger.exception("[Maszyny] Nie udało się wczytać konfiguracji.")
        messagebox.showwarning(
            "Maszyny",
            "Błąd podczas wczytywania konfiguracji maszyn.",
        )
        tk.Label(
            container,
            text="Nie udało się wczytać konfiguracji maszyn.",
            **label_kwargs,
        ).pack(pady=12)
        return None

    abs_path = resolve_rel(cfg, "machines")
    if not abs_path:
        logger.warning("[Maszyny] Brak paths.data_root lub ścieżki maszyn")
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

    items = _load_machines_sot(cm, cfg=cfg)
    if not items:
        tk.Label(
            container,
            text="Brak rekordów maszyn w pliku.",
            **label_kwargs,
        ).pack(pady=12)
        return None

    return _try_build_renderer_or_list(
        container,
        cm,
        records=items,
        label_kwargs=label_kwargs,
        renderer=Renderer,
    )


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
