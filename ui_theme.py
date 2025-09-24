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
from tkinter import TclError, ttk

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
THEME_ALIASES: Mapping[str, str] = {
    "dark": DEFAULT_THEME,
    "ciemny": DEFAULT_THEME,
}
CONFIG_FILE = Path("config.json")


def resolve_theme_name(name: str) -> str:
    """Mapuje aliasy motywów na rzeczywiste nazwy i normalizuje zapis."""

    stripped = name.strip()
    key = stripped.lower()
    alias = THEME_ALIASES.get(key)
    if alias is not None:
        if stripped != alias:
            print(
                f"[WM-DBG][THEME] Alias motywu '{stripped}' zamieniony na '{alias}'"
            )
        return alias
    if key in THEMES:
        if stripped != key:
            print(
                f"[WM-DBG][THEME] Normalizuję nazwę motywu '{stripped}' -> '{key}'"
            )
        return key
    return stripped


def load_theme_name(config_path: Path) -> str:
    """Czyta config.json i zwraca nazwę motywu; fallback = 'default'."""

    try:
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))

            ui_section = data.get("ui")
            name: str | None = None
            if isinstance(ui_section, Mapping):
                ui_theme = ui_section.get("theme")
                if isinstance(ui_theme, str):
                    name = ui_theme

            if name is None:
                legacy_theme = data.get("theme")
                if isinstance(legacy_theme, str):
                    name = legacy_theme

            if isinstance(name, str):
                resolved_name = resolve_theme_name(name)
                if resolved_name in THEMES:
                    print("[WM-DBG][THEME] Wybrany motyw z config:", resolved_name)
                    return resolved_name

                print(
                    f"[WM-DBG][THEME] Motyw '{name}' z config nieznany, "
                    "przełączam na 'default'"
                )
    except Exception as ex:
        print("[ERROR][THEME] Nie udało się odczytać config.json:", ex)
    print("[WM-DBG][THEME] Używam domyślnego motywu: default")
    return DEFAULT_THEME


def apply_theme(style: ttk.Style, name: str = DEFAULT_THEME) -> None:
    """Aplikuje motyw do ttk.Style."""

    try:
        style.theme_use("clam")
    except TclError:
        logger.debug("Styl 'clam' jest niedostępny – pozostawiam bieżący motyw ttk")

    name = resolve_theme_name(name)

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

    # --- Motywy przestrzeni WM ---
    style.configure("WM.TFrame", background=c["panel"])
    style.configure("WM.Side.TFrame", background=c["panel"])
    style.configure("WM.Container.TFrame", background=c["bg"])
    style.configure(
        "WM.Card.TFrame",
        background=c["card"],
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "WM.Header.TFrame",
        background=c["panel"],
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "WM.Cover.TFrame",
        background=c["accent"],
        relief="flat",
        borderwidth=0,
    )

    style.configure("WM.TLabel", background=c["panel"], foreground=c["text"])
    style.configure("WM.Muted.TLabel", background=c["panel"], foreground=c["muted"])
    style.configure(
        "WM.H1.TLabel",
        background=c["panel"],
        foreground=c["text"],
        font=("Segoe UI", 16, "bold"),
    )
    style.configure(
        "WM.H2.TLabel",
        background=c["panel"],
        foreground=c["text"],
        font=("Segoe UI", 13, "bold"),
    )
    style.configure(
        "WM.Card.TLabel",
        background=c["card"],
        foreground=c["text"],
        font=("Segoe UI", 11, "bold"),
    )
    style.configure(
        "WM.CardLabel.TLabel",
        background=c["card"],
        foreground=c["text"],
    )
    style.configure(
        "WM.CardMuted.TLabel",
        background=c["card"],
        foreground=c["muted"],
    )
    style.configure(
        "WM.KPI.TLabel",
        background=c["card"],
        foreground=c["accent"],
        font=("Segoe UI", 18, "bold"),
    )
    style.configure(
        "WM.Tag.TLabel",
        background=c["card"],
        foreground=c["text"],
        padding=(6, 2),
    )
    style.configure(
        "WM.Label", background=c["bg"], foreground=c["text"]
    )
    style.configure(
        "WM.Banner.TLabel",
        background=c["accent"],
        foreground=c["text"],
        padding=(12, 8),
    )

    style.configure(
        "WM.Search.TEntry",
        fieldbackground=c["entry_bg"],
        foreground=c["entry_fg"],
        bordercolor=c["entry_bd"],
        insertcolor=c["text"],
        padding=6,
    )

    style.configure(
        "TButton",
        background=c["card"],
        foreground=c["text"],
        padding=(10, 6),
    )
    button_map = {
        "background": [("active", c["accent_hover"]), ("pressed", c["accent"])],
        "foreground": [("disabled", c["muted"])],
    }
    style.map("TButton", **button_map)

    style.configure(
        "WM.Side.TButton",
        background=c["panel"],
        foreground=c["text"],
        padding=(12, 8),
        borderwidth=0,
        relief="flat",
    )
    side_active = c.get("line", "#2c2d31")
    style.map(
        "WM.Side.TButton",
        background=[("active", side_active), ("pressed", side_active)],
        foreground=[
            ("active", c["text"]),
            ("pressed", c["text"]),
            ("disabled", c["muted"]),
        ],
    )

    style.configure(
        "WM.Button.TButton",
        background=c["accent"],
        foreground=c["text"],
        padding=(12, 8),
        borderwidth=0,
    )
    style.map("WM.Button.TButton", **button_map)

    style.configure(
        "WM.Outline.TButton",
        background=c["panel"],
        foreground=c["text"],
        padding=(12, 8),
        borderwidth=1,
        relief="solid",
        bordercolor=c["accent"],
    )
    style.map("WM.Outline.TButton", **button_map)

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
    style.configure(
        "Treeview.Heading", background=c["panel"], foreground=c["text"]
    )
    style.map(
        "Treeview",
        background=[("selected", c["accent"])],
        foreground=[("selected", "#000000")],
    )

    style.configure(
        "WM.Treeview",
        background=c["card"],
        fieldbackground=c["card"],
        foreground=c["text"],
        bordercolor=c["line"],
        rowheight=24,
    )
    style.configure(
        "WM.Treeview.Heading",
        background=c["panel"],
        foreground=c["text"],
        bordercolor=c["line"],
    )
    style.map(
        "WM.Treeview",
        background=[("selected", c["accent"])],
        foreground=[("selected", "#000000")],
    )

    style.configure(
        "WM.Section.TLabelframe",
        background=c["card"],
        foreground=c["text"],
        bordercolor=c["line"],
        labelmargins=(8, 4, 8, 4),
    )
    style.configure(
        "WM.Section.TLabelframe.Label",
        background=c["card"],
        foreground=c["text"],
        font=("Segoe UI", 11, "bold"),
    )

    style.configure("TSeparator", background=c["line"])
    print(f"[WM-DBG][THEME] Zastosowano motyw: {name}")


def _set_widget_background(widget: tk.Misc, bg_color: str) -> None:
    """Ustawia tło dla widgetu tk/ttk w sposób odporny na wyjątki."""

    def _set_native_background(w: tk.Misc) -> bool:
        try:
            w.configure(background=bg_color)
            return True
        except TclError:
            pass
        try:
            w.configure(bg=bg_color)
            return True
        except TclError:
            return False

    if _set_native_background(widget):
        print(
            f"[WM-DBG][THEME] BG set native for {widget.__class__.__name__} = {bg_color}"
        )
        return

    try:
        style = ttk.Style(widget)
        widget_class = widget.winfo_class()
        unique_id = str(widget).replace(".", "_")
        style_name = f"{widget_class}.{unique_id}"
        style.configure(style_name, background=bg_color, fieldbackground=bg_color)
        widget.configure(style=style_name)
        print(f"[WM-DBG][THEME] BG set via ttk.Style for {widget_class} -> {bg_color}")
    except Exception as exc:  # pragma: no cover - jedynie log
        print(f"[WM-DBG][THEME] Nie można ustawić tła dla {widget}: {exc}")


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
        theme_name = resolve_theme_name(theme_name)
        apply_theme(style, theme_name)
        if isinstance(target, tk.Misc):
            _set_widget_background(target, THEMES[theme_name]["bg"])
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
