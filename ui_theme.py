"""Warstwa stylów Warsztat Menager.

Wersja 1.1.0 – dodano motyw "warm" oraz funkcje `load_theme_name` i
`apply_theme` akceptującą nazwę motywu.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

import tkinter as tk
from tkinter import ttk

from config_manager import ConfigManager

logger = logging.getLogger(__name__)

# -----------------------------
# Palety kolorów (2 motywy)
# -----------------------------
THEMES: Mapping[str, Mapping[str, str]] = {
    "default": {
        # ciemny + czerwone akcenty
        "bg": "#111214",
        "panel": "#1a1c1f",
        "card": "#202226",
        "text": "#e6e6e6",
        "muted": "#a9abb3",
        "accent": "#d43c3c",
        "accent_hover": "#e25353",
        "line": "#2a2d33",
        "success": "#29a36a",
        "warning": "#d69d2b",
        "error": "#e05555",
        "entry_bg": "#181a1d",
        "entry_fg": "#e6e6e6",
        "entry_bd": "#2a2d33",
        "tab_active": "#e25353",
        "tab_inactive": "#5a5d66",
    },
    "warm": {
        # grafitowe tła + bursztynowe akcenty
        "bg": "#131416",
        "panel": "#1b1d20",
        "card": "#212327",
        "text": "#f0f0f0",
        "muted": "#b7b9bf",
        "accent": "#ff9933",
        "accent_hover": "#ffb255",
        "line": "#2b2e34",
        "success": "#2fa779",
        "warning": "#e0a84a",
        "error": "#e36a5a",
        "entry_bg": "#1a1c1f",
        "entry_fg": "#f0f0f0",
        "entry_bd": "#2b2e34",
        "tab_active": "#ff9933",
        "tab_inactive": "#6a6d75",
    },
    "christmas": {
        "bg": "#0d1a0d",  # ciemna zieleń
        "panel": "#142414",
        "card": "#1a2a1a",
        "text": "#ffffff",
        "muted": "#a8b0a8",
        "accent": "#cc3333",  # czerwony
        "accent_hover": "#d44d4d",
        "line": "#223322",
        "success": "#2fa779",
        "warning": "#d4af37",  # złoty
        "error": "#e05555",
        "entry_bg": "#142414",
        "entry_fg": "#ffffff",
        "entry_bd": "#223322",
        "tab_active": "#d4af37",
        "tab_inactive": "#556655",
    },
}

DEFAULT_THEME = "default"
CONFIG_FILE = Path("config.json")
THEME_ALIASES = {
    "dark": "default",
    "ciemny": "default",
    "wm": "default",
    "default": "default",
    "warm": "warm",
}


def _normalize_theme_name(name: str | None) -> str:
    if not name:
        return DEFAULT_THEME
    candidate = THEME_ALIASES.get(name.strip().lower(), name.strip().lower())
    if candidate in THEMES:
        return candidate
    logger.warning("[WM-DBG][THEME] Motyw '%s' nieznany, używam domyślnego", name)
    return DEFAULT_THEME


# --------------------------------
# Odczyt nazwy motywu z config.json
# --------------------------------
def load_theme_name(config_path: Path | None = None) -> str:
    """Czyta config.json i zwraca nazwę motywu. Domyślnie 'default'."""

    path = config_path or CONFIG_FILE
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            theme_name = _extract_theme_from_dict(data)
            if theme_name:
                normalized = _normalize_theme_name(theme_name)
                print("[WM-DBG][THEME] Wybrany motyw z config:", normalized)
                return normalized
    except Exception as exc:  # pragma: no cover - log i fallback
        print("[ERROR][THEME] Nie udało się odczytać config.json:", exc)

    # Fallback do ConfigManager (stare wersje korzystały z sekcji ui.theme)
    try:
        raw_name = ConfigManager().get("ui.theme", DEFAULT_THEME)
        normalized = _normalize_theme_name(raw_name if isinstance(raw_name, str) else DEFAULT_THEME)
        print("[WM-DBG][THEME] Motyw z ConfigManager:", normalized)
        return normalized
    except Exception:  # pragma: no cover - log i fallback
        logger.exception("Nie udało się pobrać motywu z ConfigManager")

    print("[WM-DBG][THEME] Używam domyślnego motywu: default")
    return DEFAULT_THEME


def _extract_theme_from_dict(data: Any) -> str | None:
    """Wydziel nazwę motywu z dict-a config.json."""

    if not isinstance(data, dict):
        return None
    theme_name = data.get("theme")
    if isinstance(theme_name, str):
        return theme_name
    ui_section = data.get("ui")
    if isinstance(ui_section, dict):
        ui_theme = ui_section.get("theme")
        if isinstance(ui_theme, str):
            return ui_theme
    return None


def _apply_palette_to_style(style: ttk.Style, palette: Mapping[str, str]) -> None:
    """Konfiguruj style ttk w oparciu o wskazaną paletę."""

    try:
        if style.theme_use() != "clam":
            style.theme_use("clam")
    except tk.TclError:  # pragma: no cover - zależne od platformy
        logger.exception("Failed to set 'clam' theme")

    bg = palette["bg"]
    panel = palette["panel"]
    card = palette["card"]
    text = palette["text"]
    muted = palette["muted"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    line = palette["line"]

    style.configure(".", background=bg, foreground=text)

    # Frames / cards / side panels
    style.configure("TFrame", background=panel)
    style.configure("Card.TFrame", background=card)
    style.configure("WM.TFrame", background=panel)
    style.configure("WM.Card.TFrame", background=card)
    style.configure("WM.Side.TFrame", background=panel)

    # Labels
    style.configure("TLabel", background=panel, foreground=text)
    style.configure("WM.TLabel", background=panel, foreground=text)
    style.configure("WM.Card.TLabel", background=card, foreground=text)
    style.configure("WM.Muted.TLabel", background=panel, foreground=muted)
    style.configure(
        "WM.H1.TLabel",
        background=panel,
        foreground=text,
        font=("Segoe UI", 16, "bold"),
    )
    style.configure(
        "WM.Banner.TLabel",
        background=panel,
        foreground=accent,
        font=("Consolas", 11, "bold"),
    )

    # Buttons
    style.configure(
        "TButton",
        background=card,
        foreground=text,
        borderwidth=1,
        focusthickness=3,
        focuscolor=accent,
        padding=(10, 6),
    )
    style.map(
        "TButton",
        background=[("active", accent_hover), ("pressed", accent)],
        foreground=[("disabled", muted)],
    )
    style.configure(
        "WM.Side.TButton",
        background=panel,
        foreground=text,
        borderwidth=0,
        padding=6,
    )
    style.map(
        "WM.Side.TButton",
        background=[("active", accent_hover), ("pressed", accent)],
        relief=[("pressed", "sunken"), ("!pressed", "flat")],
    )

    # Inputs (Entry/Combobox/Spinbox)
    entry_common = dict(
        fieldbackground=palette["entry_bg"],
        foreground=palette["entry_fg"],
        background=panel,
        bordercolor=palette["entry_bd"],
        lightcolor=palette["entry_bd"],
        darkcolor=palette["entry_bd"],
        insertcolor=text,
        padding=6,
    )
    for base in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(base, **entry_common)
        style.map(
            base,
            fieldbackground=[("readonly", palette["entry_bg"]), ("focus", palette["entry_bg"])],
            foreground=[("disabled", muted)],
        )
    style.configure(
        "Transparent.TEntry",
        fieldbackground=bg,
        background=bg,
        borderwidth=0,
        foreground=text,
    )

    # Notebook (zakładki)
    style.configure("TNotebook", background=panel, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(12, 6),
        background=panel,
        foreground=palette["tab_inactive"],
    )
    style.map(
        "TNotebook.Tab",
        foreground=[("selected", text)],
        background=[("selected", panel)],
        bordercolor=[("selected", palette["tab_active"])],
    )

    # Treeview
    tree_opts = dict(
        background=card,
        fieldbackground=card,
        foreground=text,
        bordercolor=line,
        rowheight=24,
    )
    style.configure("Treeview", **tree_opts)
    style.configure("WM.Treeview", **tree_opts)
    style.map(
        "Treeview",
        background=[("selected", accent)],
        foreground=[("selected", "#000000")],
    )
    style.map(
        "WM.Treeview",
        background=[("selected", accent)],
        foreground=[("selected", "#000000")],
    )
    heading_opts = dict(background=panel, foreground=text)
    style.configure("Treeview.Heading", **heading_opts)
    style.configure("WM.Treeview.Heading", **heading_opts)

    # Separator
    style.configure("TSeparator", background=line)


def _resolve_style_master(style: ttk.Style) -> tk.Misc | None:
    master = getattr(style, "master", None)
    if isinstance(master, tk.Misc):
        return master
    return None


# -----------------------
# Aplikacja stylu do ttk i widgetów
# -----------------------
def apply_theme(
    target: tk.Misc | ttk.Style | None = None,
    name: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Aplikuje motyw do ttk.Style lub bezpośrednio do widgetu."""

    theme_name = _normalize_theme_name(name) if name else load_theme_name(config_path)
    palette = THEMES[theme_name]

    if isinstance(target, ttk.Style):
        style = target
    else:
        style = ttk.Style(target)

    _apply_palette_to_style(style, palette)

    roots: Iterable[tk.Misc] = []
    if isinstance(target, (tk.Tk, tk.Toplevel)):
        roots = (target,)
    elif isinstance(target, tk.Misc):
        roots = (target.winfo_toplevel(),)
    else:
        master = _resolve_style_master(style)
        if isinstance(master, (tk.Tk, tk.Toplevel)):
            roots = (master,)

    for root in roots:
        try:
            root.configure(bg=palette["bg"])
        except tk.TclError:  # pragma: no cover - zależne od platformy
            logger.exception("Failed to configure widget background")


def apply_theme_safe(
    target: tk.Misc | ttk.Style | None = None,
    name: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Wrapper na :func:`apply_theme`, ignorujący wszelkie wyjątki."""

    try:
        apply_theme(target, name=name, config_path=config_path)
    except Exception:  # pragma: no cover - log i kontynuuj
        logger.exception("apply_theme failed")


def apply_theme_tree(
    widget: tk.Misc | None,
    name: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Zastosuj motyw dla podanego widgetu i całego jego drzewa potomków."""

    apply_theme_safe(widget, name=name, config_path=config_path)
    if hasattr(widget, "winfo_children"):
        for child in widget.winfo_children():
            apply_theme_tree(child, name=name, config_path=config_path)


# ===== Kolory magazynu (używane przez gui_magazyn) =====
COLORS = {
    "stock_ok": "#2d6a4f",
    "stock_warn": "#d35400",
    "stock_low": "#c0392b",
}

# ⏹ KONIEC KODU
