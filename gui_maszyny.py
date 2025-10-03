from __future__ import annotations

import json
import os
import tkinter as tk
from logging import getLogger
from tkinter import messagebox, ttk

try:
    from config_manager import ConfigManager, resolve_rel
except Exception:  # pragma: no cover - fallback gdy moduł nieosiągalny
    ConfigManager = None  # type: ignore[assignment]

    def resolve_rel(cfg: dict, what: str) -> str:
        root = (cfg.get("paths", {}) or {}).get("data_root") or "C:/wm/data"
        mapping = {"machines": os.path.join("maszyny", "maszyny.json")}
        return os.path.normpath(os.path.join(root, mapping.get(what, "")))

from ui_theme import ensure_theme_applied

logger = getLogger(__name__)
_ = messagebox  # pragma: no cover - import utrzymany dla kompatybilności

try:  # pragma: no cover - CONFIG_MANAGER jest opcjonalny
    from start import CONFIG_MANAGER
except Exception:  # pragma: no cover - środowiska testowe
    CONFIG_MANAGER = None


def _safe_read_json(path: str, default: dict) -> dict:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(default, handle, ensure_ascii=False, indent=2)
            logger.warning("[AUTOJSON] Brak pliku %s – utworzono szablon", path)
            return default.copy()
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:  # pragma: no cover - ochrona przed błędami IO
        logger.error("[Maszyny] Błąd JSON (%s): %s", path, exc)
        return default.copy()


def _resolve_manager(explicit: ConfigManager | None) -> ConfigManager | None:
    if explicit is not None:
        return explicit
    if CONFIG_MANAGER is not None:
        return CONFIG_MANAGER
    if ConfigManager is None:
        return None
    try:
        return ConfigManager()
    except Exception:  # pragma: no cover - ConfigManager opcjonalny
        logger.exception("[Maszyny] Nie udało się zainicjalizować ConfigManagera.")
        return None


def _build_tree(parent: tk.Misc, rows: list[dict]) -> ttk.Treeview:
    tree = ttk.Treeview(parent, columns=("id", "nazwa", "typ"), show="headings", height=18)
    tree.heading("id", text="ID")
    tree.heading("nazwa", text="Nazwa")
    tree.heading("typ", text="Typ")
    tree.column("id", width=120, anchor="w")
    tree.column("nazwa", width=360, anchor="w")
    tree.column("typ", width=160, anchor="w")
    for item in rows:
        tree.insert(
            "",
            "end",
            values=(item.get("id", ""), item.get("nazwa", ""), item.get("typ", "")),
        )
    tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    return tree


Renderer = None


def _open_machines_panel(root, container, config_manager=None, Renderer=None):
    for child in container.winfo_children():
        child.destroy()

    info = tk.StringVar()
    info_label = ttk.Label(container, textvariable=info)
    info_label.pack(fill="x", padx=8, pady=8)

    manager = _resolve_manager(config_manager)
    try:
        cfg = manager.load() if manager is not None else {}
    except Exception:
        logger.exception("[Maszyny] Nie udało się wczytać konfiguracji.")
        cfg = {}

    machines_path = resolve_rel(cfg, "machines") if cfg else resolve_rel({}, "machines")
    default_doc = {"maszyny": []}
    rows_data = _safe_read_json(machines_path, default_doc)
    if isinstance(rows_data, dict):
        rows = rows_data.get("maszyny") or []
    elif isinstance(rows_data, list):
        rows = rows_data
    else:
        rows = []
    rows = [row for row in rows if isinstance(row, dict)]

    if not rows:
        info.set("Brak maszyn w konfiguracji. Lista jest pusta – możesz dodać pozycje.")
    else:
        info.set(f"Wczytano {len(rows)} maszyn.")

    tree: ttk.Treeview | None = None
    active_renderer = Renderer
    if rows and active_renderer is not None:
        try:  # pragma: no cover - renderer opcjonalny
            if callable(active_renderer):
                try:
                    renderer_instance = active_renderer(container, rows)
                except TypeError:
                    renderer_instance = active_renderer(
                        container.winfo_toplevel(),
                        container,
                        rows,
                    )
                render = getattr(renderer_instance, "render", None)
                if callable(render):
                    render()
                    tree = None
                else:
                    raise AttributeError("Renderer instance missing render()")
            else:
                render_callable = getattr(active_renderer, "render", None)
                if callable(render_callable):
                    render_callable(container, rows)
                    tree = None
                else:
                    draw_callable = getattr(active_renderer, "draw", None)
                    if callable(draw_callable):
                        draw_callable(rows)
                        tree = None
                    else:
                        raise TypeError("Renderer does not expose render/draw API")
        except Exception as exc:
            logger.warning("[Maszyny] Renderer niedostępny – fallback na listę (%s)", exc)
            tree = None

    if tree is None:
        tree = _build_tree(container, rows)
    logger.info("[Maszyny] Panel otwarty; rekordów: %d", len(rows))
    return tree


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
