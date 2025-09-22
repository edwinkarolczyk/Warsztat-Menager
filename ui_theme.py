"""Warstwa stylów Warsztat Menager.

Wersja 1.1.0 – dodano motyw "warm" oraz funkcje `load_theme_name` i
`apply_theme` akceptującą nazwę motywu.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping

import tkinter as tk
from tkinter import ttk

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


def load_theme_name(config_path: Path) -> str:
    """Czyta config.json i zwraca nazwę motywu; fallback = 'default'."""

    try:
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            name = data.get("theme", DEFAULT_THEME)
            if name in THEMES:
                print("[WM-DBG][THEME] Wybrany motyw z config:", name)
                return name
    except Exception as ex:
        print("[ERROR][THEME] Nie udało się odczytać config.json:", ex)
    print("[WM-DBG][THEME] Używam domyślnego motywu: default")
    return DEFAULT_THEME


def apply_theme(style: ttk.Style, name: str = DEFAULT_THEME) -> None:
    """Aplikuje motyw do ttk.Style."""

    if name not in THEMES:
        print(
            f"[WM-DBG][THEME] Motyw '{name}' nieznany, przełączam na 'default'"
        )
        name = DEFAULT_THEME
    c = THEMES[name]

    root = style.master if hasattr(style, "master") else None
    if isinstance(root, tk.Tk):
        root.configure(bg=c["bg"])

    style.configure(".", background=c["bg"], foreground=c["text"])
    style.configure("TFrame", background=c["panel"])
    style.configure("Card.TFrame", background=c["card"])
    style.configure("TLabel", background=c["panel"], foreground=c["text"])
    style.configure("Muted.TLabel", foreground=c["muted"])
    style.configure(
        "H1.TLabel",
        font=("Segoe UI", 16, "bold"),
        foreground=c["text"],
        background=c["panel"],
    )
    style.configure(
        "H2.TLabel",
        font=("Segoe UI", 13, "bold"),
        foreground=c["text"],
        background=c["panel"],
    )

    style.configure(
        "TButton", background=c["card"], foreground=c["text"], padding=(10, 6)
    )
    style.map(
        "TButton",
        background=[("active", c["accent_hover"]), ("pressed", c["accent"])],
        foreground=[("disabled", c["muted"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=c["entry_bg"],
        foreground=c["entry_fg"],
        bordercolor=c["entry_bd"],
        insertcolor=c["text"],
        padding=6,
    )
    style.configure(
        "TCombobox",
        fieldbackground=c["entry_bg"],
        foreground=c["entry_fg"],
        bordercolor=c["entry_bd"],
        arrowsize=14,
        padding=6,
    )

    style.configure("TNotebook", background=c["panel"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(12, 6),
        background=c["panel"],
        foreground=c["muted"],
    )
    style.map(
        "TNotebook.Tab",
        foreground=[("selected", c["text"])],
        background=[("selected", c["panel"])],
        bordercolor=[("selected", c["tab_active"])],
    )

    style.configure(
        "Treeview",
        background=c["card"],
        fieldbackground=c["card"],
        foreground=c["text"],
        bordercolor=c["line"],
        rowheight=24,
    )
    style.configure("Treeview.Heading", background=c["panel"], foreground=c["text"])
    style.map(
        "Treeview",
        background=[("selected", c["accent"])],
        foreground=[("selected", "#000000")],
    )

    style.configure("TSeparator", background=c["line"])
    print(f"[WM-DBG][THEME] Zastosowano motyw: {name}")


def apply_theme_safe(
    target: tk.Misc | ttk.Style | None = None,
    name: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Wrapper na :func:`apply_theme`, ignorujący wszelkie wyjątki."""

    try:
        style = target if isinstance(target, ttk.Style) else ttk.Style(target)
        path = config_path or CONFIG_FILE
        theme_name = name or load_theme_name(path)
        apply_theme(style, theme_name)
        if isinstance(target, tk.Misc):
            try:
                target.configure(bg=THEMES[theme_name]["bg"])
            except tk.TclError:
                logger.exception("Failed to configure widget background")
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
