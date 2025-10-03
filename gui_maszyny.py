from __future__ import annotations

import os
import tkinter as tk
from logging import getLogger
from tkinter import messagebox, ttk

try:
    from config_manager import get_config, resolve_rel  # type: ignore
except Exception:  # pragma: no cover - fallback dla starszych wersji
    try:
        from config_manager import resolve_rel  # type: ignore
    except Exception:  # pragma: no cover - fallback gdy moduł nieosiągalny

        def resolve_rel(cfg: dict, what: str) -> str:
            root = (cfg.get("paths", {}) or {}).get("data_root") or "C:/wm/data"
            mapping = {"machines": os.path.join("maszyny", "maszyny.json")}
            return os.path.normpath(os.path.join(root, mapping.get(what, "")))

    def get_config() -> dict:
        try:
            from config_manager import ConfigManager  # type: ignore

            return ConfigManager().load()
        except Exception:
            return {}

from ui_theme import ensure_theme_applied
from utils_maszyny import (
    ensure_machines_sample_if_empty,
    load_machines_rows_with_fallback,
)

logger = getLogger(__name__)
_ = messagebox  # pragma: no cover - import utrzymany dla kompatybilności

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


def _open_machines_panel(root, container, Renderer=None):
    for child in container.winfo_children():
        child.destroy()

    info = tk.StringVar()
    info_label = ttk.Label(container, textvariable=info)
    info_label.pack(fill="x", padx=8, pady=8)

    try:
        cfg = get_config()
    except Exception:
        logger.exception("[Maszyny] Nie udało się wczytać konfiguracji.")
        cfg = {}

    rows, primary_path = load_machines_rows_with_fallback(cfg, resolve_rel)
    rows, primary_path = ensure_machines_sample_if_empty(rows, primary_path)

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
    logger.info("[Maszyny] Panel otwarty; rekordów: %d; plik=%s", len(rows), primary_path)
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
            Renderer=Renderer,
        )


def panel_maszyny(root, frame, login=None, rola=None):
    """Adapter używany przez główny panel aplikacji."""

    _open_machines_panel(root, frame, Renderer=Renderer)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Warsztat Menager — Maszyny")
    ensure_theme_applied(root)
    MaszynyGUI(root)
    root.mainloop()
