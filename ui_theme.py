# version: 1.1.2
"""Warstwa stylów Warsztat Menager.

Wersja 1.1.2 – usunięto rekurencyjne, wielokrotne nakładanie motywu podczas
budowy GUI. `ensure_theme_applied` i `Toplevel` stosują motyw tylko raz na okno.

Wersja 1.1.1 – dodano strażnika `ensure_theme_applied` z obsługą logowania
i importu wstecznie kompatybilnego.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping

import tkinter as tk
from tkinter import TclError, ttk

logger = logging.getLogger(__name__)

_WM_UI_THEME_LOG_ONCE: set[str] = set()


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
            msg = (
                f"[WM-DBG][THEME] Alias motywu '{stripped}' zamieniony na '{alias}'"
            )
            if msg not in _WM_UI_THEME_LOG_ONCE:
                _WM_UI_THEME_LOG_ONCE.add(msg)
                print(msg)
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


def _build_palette(name: str) -> Mapping[str, str]:
    theme = THEMES[name]
    bg = theme.get("bg", "#111214")
    panel = theme.get("panel", theme.get("card", bg))
    card = theme.get("card", panel)
    accent = theme.get("accent", "#3a86ff")
    accent_hover = theme.get("accent_hover", accent)
    line = theme.get("line", "#2a2c31")
    text = theme.get("text", "#ffffff")
    muted = theme.get("muted", "#d0d0d0")
    disabled = theme.get("disabled", "#9aa0a6")
    entry_bg = theme.get("entry_bg", panel)
    entry_fg = theme.get("entry_fg", text)
    entry_bd = theme.get("entry_bd", line)
    selection = theme.get("selection", accent_hover)

    soft_selection = theme.get("selection_soft", "#e9f2ff")
    return {
        "bg": bg,
        "bg_alt": panel,
        "card": card,
        "fg": text,
        "fg_dim": muted,
        "fg_disabled": disabled,
        "accent": accent,
        "accent_hover": accent_hover,
        "border": line,
        "entry_bg": entry_bg,
        "entry_fg": entry_fg,
        "entry_border": entry_bd,
        "selection": selection,
        "tab_active": theme.get("tab_active", accent),
        "tab_inactive": theme.get("tab_inactive", muted),
        "selection_soft": soft_selection,
        "success": theme.get("success", "#22c55e"),
        "warning": theme.get("warning", "#eab308"),
        "error": theme.get("error", "#ef4444"),
    }


_ACTIVE_THEME_NAME = DEFAULT_THEME
_ACTIVE_PALETTE = _build_palette(DEFAULT_THEME)

# Motywy/Style w ttk są współdzielone globalnie – powtórne konfigurowanie dla
# każdego nowego okna (np. Toplevel) potrafi być kosztowne. Trzymamy więc nazwę
# ostatnio skonfigurowanego motywu, aby ewentualne kolejne wywołania mogły
# pominąć cięższe operacje na stylach.
_THEME_STYLES_CONFIGURED: str | None = None

# Flaga do jednorazowego konfigurowania stylów ttk.
_WM_THEME_APPLIED = False


def _apply_base_styles(style: ttk.Style, palette: Mapping[str, str]) -> None:
    bg = palette["bg"]
    bg_alt = palette["bg_alt"]
    fg = palette["fg"]
    fg_dim = palette["fg_dim"]
    fg_disabled = palette["fg_disabled"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    border = palette["border"]
    selection = palette["selection"]

    style.configure(
        ".",
        background=bg,
        foreground=fg,
        fieldbackground=bg_alt,
        bordercolor=border,
    )

    style.configure("TFrame", background=bg)
    style.configure("TLabelframe", background=bg, bordercolor=border)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TLabel", background=bg, foreground=fg)

    style.configure(
        "TButton",
        background=bg_alt,
        foreground=fg,
        bordercolor=border,
        focusthickness=1,
        padding=(10, 6),
    )
    style.map(
        "TButton",
        foreground=[
            ("disabled", fg_disabled),
            ("pressed", fg),
            ("active", fg),
            ("!disabled", fg),
        ],
        background=[
            ("disabled", bg_alt),
            ("pressed", "#3b3e44"),
            ("active", "#2c2f35"),
        ],
        relief=[("pressed", "sunken"), ("!pressed", "raised")],
    )

    for cls in ("TEntry", "TSpinbox"):
        style.configure(
            cls,
            fieldbackground=palette["entry_bg"],
            foreground=palette["entry_fg"],
            bordercolor=palette["entry_border"],
            lightcolor=palette["entry_border"],
            darkcolor=palette["entry_border"],
            insertcolor=fg,
        )
        style.map(
            cls,
            fieldbackground=[
                ("disabled", palette["entry_bg"]),
                ("readonly", palette["entry_bg"]),
                ("focus", palette["entry_bg"]),
            ],
            foreground=[("disabled", fg_disabled), ("readonly", fg_dim)],
        )

    style.configure(
        "TCombobox",
        fieldbackground=palette["entry_bg"],
        foreground=palette["entry_fg"],
        background=palette["entry_bg"],
        bordercolor=palette["entry_border"],
        arrowsize=14,
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette["entry_bg"]), ("focus", palette["entry_bg"])],
        foreground=[("disabled", fg_disabled), ("readonly", fg)],
        background=[("active", palette["entry_bg"])],
    )
    try:
        style.configure("ComboboxPopdownFrame", background=bg)
    except Exception:
        pass

    style.configure(
        "TNotebook",
        background=bg,
        bordercolor=border,
        tabmargins=(6, 4, 6, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=bg_alt,
        foreground=fg_dim,
        padding=(12, 6),
    )
    style.map(
        "TNotebook.Tab",
        foreground=[("selected", fg), ("!selected", fg_dim)],
        background=[("selected", "#23252a"), ("!selected", bg_alt)],
        bordercolor=[("selected", palette["tab_active"])],
    )

    style.configure(
        "Treeview",
        background=bg_alt,
        fieldbackground=bg_alt,
        foreground=fg,
        bordercolor=border,
    )
    style.map(
        "Treeview",
        foreground=[("disabled", fg_disabled)],
        background=[("selected", selection), ("!selected", bg_alt)],
    )
    style.configure(
        "Treeview.Heading",
        background=bg,
        foreground=fg,
        bordercolor=border,
    )
    style.map("Treeview.Heading", background=[("active", bg_alt)])

    style.configure(
        "TProgressbar",
        background=accent,
        troughcolor=bg_alt,
        bordercolor=border,
    )
    style.configure(
        "Vertical.TScrollbar",
        background=bg_alt,
        troughcolor=bg,
        bordercolor=border,
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=bg_alt,
        troughcolor=bg,
        bordercolor=border,
    )

    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("TRadiobutton", background=bg, foreground=fg)

    try:
        style.configure("TMenubutton", background=bg_alt, foreground=fg, bordercolor=border)
        style.map(
            "TMenubutton",
            background=[("active", "#2c2f35")],
            foreground=[("disabled", fg_disabled)],
        )
    except Exception:
        pass


def _configure_wm_styles(
    style: ttk.Style, theme: Mapping[str, str], palette: Mapping[str, str]
) -> None:
    text = palette["fg"]
    muted = palette["fg_dim"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    panel = palette["bg_alt"]
    card = palette["card"]
    border = palette["border"]

    style.configure("Card.TFrame", background=card)
    style.configure("Muted.TLabel", foreground=muted)
    style.configure(
        "H1.TLabel",
        font=("Segoe UI", 16, "bold"),
        foreground=text,
        background=panel,
    )
    style.configure(
        "H2.TLabel",
        font=("Segoe UI", 13, "bold"),
        foreground=text,
        background=panel,
    )

    style.configure("WM.TFrame", background=panel)
    style.configure("WM.Side.TFrame", background=panel)
    style.configure("WM.Container.TFrame", background=palette["bg"])
    style.configure(
        "WM.Card.TFrame",
        background=card,
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "WM.Header.TFrame",
        background=panel,
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "WM.Cover.TFrame",
        background=accent,
        relief="flat",
        borderwidth=0,
    )

    style.configure("WM.TLabel", background=panel, foreground=text)
    style.configure("WM.Muted.TLabel", background=panel, foreground=muted)
    style.configure(
        "WM.H1.TLabel",
        background=panel,
        foreground=text,
        font=("Segoe UI", 16, "bold"),
    )
    style.configure(
        "WM.H2.TLabel",
        background=panel,
        foreground=text,
        font=("Segoe UI", 13, "bold"),
    )
    style.configure(
        "WM.Card.TLabel",
        background=card,
        foreground=text,
        font=("Segoe UI", 11, "bold"),
    )
    style.configure(
        "WM.CardLabel.TLabel",
        background=card,
        foreground=text,
    )
    style.configure(
        "WM.CardMuted.TLabel",
        background=card,
        foreground=muted,
    )
    style.configure(
        "WM.KPI.TLabel",
        background=card,
        foreground=accent,
        font=("Segoe UI", 18, "bold"),
    )
    style.configure(
        "WM.Tag.TLabel",
        background=card,
        foreground=text,
        padding=(6, 2),
    )
    style.configure("WM.Label", background=palette["bg"], foreground=text)
    style.configure(
        "WM.Banner.TLabel",
        background=accent,
        foreground=text,
        padding=(12, 8),
    )

    style.configure(
        "WM.Search.TEntry",
        fieldbackground=palette["entry_bg"],
        foreground=palette["entry_fg"],
        bordercolor=palette["entry_border"],
        insertcolor=text,
        padding=6,
    )

    button_map = {
        "background": [("active", accent_hover), ("pressed", accent)],
        "foreground": [("disabled", muted)],
    }
    style.map("WM.Button.TButton", **button_map)
    style.configure(
        "WM.Button.TButton",
        background=accent,
        foreground=text,
        padding=(12, 8),
        borderwidth=0,
    )

    style.configure(
        "WM.Side.TButton",
        background=panel,
        foreground=text,
        padding=(12, 8),
        borderwidth=0,
        relief="flat",
    )
    side_active = theme.get("line", border)
    style.map(
        "WM.Side.TButton",
        background=[("active", side_active), ("pressed", side_active)],
        foreground=[
            ("active", text),
            ("pressed", text),
            ("disabled", muted),
        ],
    )

    style.configure(
        "WM.Outline.TButton",
        background=panel,
        foreground=text,
        padding=(12, 8),
        borderwidth=1,
        relief="solid",
        bordercolor=accent,
    )
    style.map("WM.Outline.TButton", **button_map)

    style.configure(
        "WM.Treeview",
        background=card,
        fieldbackground=card,
        foreground=text,
        bordercolor=border,
        rowheight=24,
    )
    style.configure(
        "WM.Treeview.Heading",
        background=panel,
        foreground=text,
        bordercolor=border,
    )
    style.map(
        "WM.Treeview",
        background=[("selected", palette["selection"])],
        foreground=[("selected", "#000000")],
    )

    style.configure(
        "WM.Section.TLabelframe",
        background=card,
        foreground=text,
        bordercolor=border,
        labelmargins=(8, 4, 8, 4),
    )
    style.configure(
        "WM.Section.TLabelframe.Label",
        background=card,
        foreground=text,
        font=("Segoe UI", 11, "bold"),
    )

    style.configure("TSeparator", background=border)


def _current_palette() -> Mapping[str, str]:
    return _ACTIVE_PALETTE or _build_palette(_ACTIVE_THEME_NAME)


def attach_theme(win: tk.Misc | None) -> None:
    """Lekka operacja dla Toplevel – ustawia tylko tło i kolory pomocnicze."""

    if win is None:
        return

    palette = _current_palette()
    try:
        win.configure(bg=palette["bg"])
    except Exception:
        pass

    try:
        win._wm_colors = {
            "bg": palette["bg"],
            "panel": palette["bg_alt"],
            "card": palette["card"],
            "border": palette["border"],
            "text": palette["fg"],
            "muted": palette["fg_dim"],
            "accent": palette["accent"],
            "sel": palette["selection"],
            "input_bg": palette["entry_bg"],
            "input_ph": palette.get("entry_fg", palette["fg_dim"]),
        }
    except Exception:
        pass

    # Jeżeli style nie były jeszcze ustawione (np. ktoś wywoła attach_theme za wcześnie),
    # to zainicjalizuj je raz na ROOT. Jeśli już są – no-op. Chronimy się przed
    # rekurencją, bo apply_theme_once() samo korzysta z attach_theme().
    if not _WM_THEME_APPLIED and not getattr(win, "_wm_theme_init_running", False):
        try:
            setattr(win, "_wm_theme_init_running", True)
            root = win.winfo_toplevel()
            apply_theme_once(root)
        except Exception:
            pass
        finally:
            try:
                delattr(win, "_wm_theme_init_running")
            except Exception:
                try:
                    setattr(win, "_wm_theme_init_running", False)
                except Exception:
                    pass


def _apply_styles(root: tk.Misc | ttk.Style | None) -> None:
    """Cięższa część – konfiguracja ttk.Style powinna zajść tylko raz."""

    try:
        apply_theme_safe(root, scheme=_ACTIVE_THEME_NAME)
    except Exception:
        logger.exception("apply_theme_safe failed during _apply_styles")


def apply_theme_once(root: tk.Misc | None) -> None:
    """Zastosuj motyw globalnie – wolno wywołać tylko raz (root Tk)."""

    global _WM_THEME_APPLIED
    attach_theme(root)
    if _WM_THEME_APPLIED:
        return
    _WM_THEME_APPLIED = True
    _apply_styles(root)


def _set_bg_recursive(widget: tk.Misc, palette: Mapping[str, str]) -> None:
    bg = palette["bg"]
    fg = palette["fg"]

    try:
        widget.configure(bg=bg)
    except Exception:
        pass

    if not hasattr(widget, "winfo_children"):
        return

    for child in widget.winfo_children():
        if isinstance(child, (tk.Frame, tk.Toplevel, tk.LabelFrame, tk.Canvas)):
            try:
                child.configure(bg=bg)
            except Exception:
                pass
        if isinstance(child, tk.Label):
            try:
                child.configure(bg=bg, fg=fg)
            except Exception:
                pass
        _set_bg_recursive(child, palette)


def _apply_widget_options(root: tk.Misc, palette: Mapping[str, str]) -> None:
    try:
        root.option_add("*Text.background", palette["bg_alt"])
        root.option_add("*Text.foreground", palette["fg"])
        root.option_add("*Text.insertBackground", palette["fg"])
        root.option_add("*Text.selectBackground", palette["selection"])
        root.option_add("*Text.selectForeground", palette["fg"])
    except Exception:
        pass

    try:
        root.option_add("*Entry.background", palette["entry_bg"])
        root.option_add("*Entry.foreground", palette["entry_fg"])
        root.option_add("*Entry.insertBackground", palette["fg"])
        root.option_add("*Entry.selectBackground", palette["selection"])
        root.option_add("*Entry.selectForeground", palette["fg"])
    except Exception:
        pass


def apply_theme(target: tk.Misc | ttk.Style, *, scheme: str = DEFAULT_THEME) -> None:
    global _ACTIVE_THEME_NAME, _ACTIVE_PALETTE, _THEME_STYLES_CONFIGURED
    """Aplikuje motyw do wskazanego widgetu lub obiektu ttk.Style."""

    try:
        style = target if isinstance(target, ttk.Style) else ttk.Style(target)
    except Exception as exc:
        logger.debug("Nie można zainicjować ttk.Style dla %s: %s", target, exc)
        style = ttk.Style()

    resolved_name = resolve_theme_name(scheme)
    if resolved_name not in THEMES:
        print(
            f"[WM-DBG][THEME] Motyw '{resolved_name}' nieznany, przełączam na 'default'"
        )
        resolved_name = DEFAULT_THEME

    palette = _build_palette(resolved_name)
    _ACTIVE_THEME_NAME = resolved_name
    _ACTIVE_PALETTE = palette
    theme_changed = _THEME_STYLES_CONFIGURED != resolved_name

    if theme_changed:
        try:
            style.theme_use("clam")
        except TclError:
            logger.debug("Styl 'clam' jest niedostępny – pozostawiam bieżący motyw ttk")

        _apply_base_styles(style, palette)
        _configure_wm_styles(style, THEMES[resolved_name], palette)
        _THEME_STYLES_CONFIGURED = resolved_name

    root: tk.Misc | None
    if isinstance(target, ttk.Style):
        root = getattr(target, "master", None)
    else:
        root = target

    if root is None:
        root = getattr(style, "master", None)

    if isinstance(root, tk.Misc):
        _set_bg_recursive(root, palette)
        _apply_widget_options(root, palette)

    print(
        f"[WM-DBG][THEME] Zastosowano motyw: {resolved_name}"
        f" ({'reconfigure' if theme_changed else 'cached'})"
    )


def apply_theme_safe(
    target: tk.Misc | ttk.Style | None = None,
    scheme: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Wrapper na :func:`apply_theme`, ignorujący wszelkie wyjątki."""

    try:
        path = config_path or CONFIG_FILE
        theme_name = scheme or load_theme_name(path)
        theme_name = resolve_theme_name(theme_name)

        style_or_widget: tk.Misc | ttk.Style
        if isinstance(target, (tk.Misc, ttk.Style)):
            style_or_widget = target
        else:
            style_or_widget = ttk.Style(target)

        try:
            target_name = (
                target.winfo_toplevel().winfo_name()  # type: ignore[attr-defined]
                if isinstance(target, tk.Misc)
                else getattr(style_or_widget, "theme_use", lambda: "style")()
            )
        except Exception:
            target_name = target.__class__.__name__ if target is not None else "None"
        print(f"[WM-DBG][THEME] apply before build -> {theme_name} ({target_name})")
        apply_theme(style_or_widget, scheme=theme_name)
    except Exception:  # pragma: no cover - log i kontynuuj
        logger.exception("apply_theme failed")


def apply_theme_once(
    target: tk.Misc | ttk.Style | None = None,
    *,
    scheme: str | None = None,
    config_path: Path | None = None,
) -> bool:
    """Zastosuj motyw najwyżej raz dla danego okna/widgetu głównego.

    Nie używa `_get_apply_fn()`, aby uniknąć wybrania samej siebie i rekurencji.
    """

    global _WM_THEME_APPLIED
    try:
        if isinstance(target, tk.Misc):
            widget = target
        else:
            widget = getattr(target, "master", None)

        if widget is not None and getattr(widget, "_wm_theme_applied", False):
            return True

        apply_theme_safe(target, scheme=scheme, config_path=config_path)
        _WM_THEME_APPLIED = True

        if widget is not None:
            try:
                setattr(widget, "_wm_theme_applied", True)
            except Exception:
                pass
        return True
    except Exception:
        logger.exception("apply_theme_once failed")
        return False


def apply_theme_tree(
    widget: tk.Misc | None,
    scheme: str | None = None,
    *,
    config_path: Path | None = None,
) -> None:
    """Zastosuj motyw raz dla okna.

    `apply_theme()` już obsługuje istniejące potomki, więc nie przechodzimy
    ponownie rekurencyjnie po każdym widżecie.
    """

    apply_theme_once(widget, scheme=scheme, config_path=config_path)


def attach_theme(
    widget: tk.Misc | None,
    *,
    scheme: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Nałóż motyw na ``widget`` oraz jego potomków (bezpiecznie)."""

    if widget is None:
        return
    apply_theme_tree(widget, scheme=scheme, config_path=config_path)


def get_theme_color(name: str, *, fallback: str | None = None) -> str:
    """Pobierz kolor motywu zgodnie z aktualnie zastosowaną paletą."""

    palette = _ACTIVE_PALETTE or _build_palette(_ACTIVE_THEME_NAME)
    try:
        value = palette[name]
    except KeyError:
        theme = THEMES.get(_ACTIVE_THEME_NAME, {})
        raw = theme.get(name) if isinstance(theme, Mapping) else None
        if isinstance(raw, str):
            return raw
        if name == "danger":
            return palette.get("error", fallback or "#ef4444")
        if fallback is not None:
            return fallback
        return palette.get("accent", "#3a86ff")
    else:
        return value


# ===== Kolory magazynu (używane przez gui_magazyn) =====
COLORS = {
    "stock_ok": "#2d6a4f",
    "stock_warn": "#d35400",
    "stock_low": "#c0392b",
}


# [HOTFIX-THEME-01] ensure_theme_applied – idempotentne zastosowanie motywu

import logging

_logger = logging.getLogger(__name__)


def _get_apply_fn():
    # Nigdy nie zwracaj apply_theme_once z wnętrza mechanizmu "once".
    # W przeciwnym razie funkcja może wybrać samą siebie i wejść w rekurencję.
    fn = globals().get("apply_theme_safe") or globals().get("apply_theme")
    return fn if callable(fn) else None


if "ensure_theme_applied" not in globals():

    def ensure_theme_applied(win):
        """Idempotentnie zastosuj motyw raz dla danego okna."""
        try:
            if not win:
                return False
            if getattr(win, "_wm_theme_applied", False):
                return True
            return bool(apply_theme_once(win))
        except Exception:
            return False


try:
    __all__  # noqa: F821
except NameError:
    __all__ = []
if "apply_theme_once" not in __all__:
    __all__.append("apply_theme_once")
if "ensure_theme_applied" not in __all__:
    __all__.append("ensure_theme_applied")
if "attach_theme" not in __all__:
    __all__.append("attach_theme")
if "get_theme_color" not in __all__:
    __all__.append("get_theme_color")
if "apply_theme_once" not in __all__:
    __all__.append("apply_theme_once")
if "attach_theme" not in __all__:
    __all__.append("attach_theme")


_ORIG_TOPLEVEL_INIT = getattr(tk.Toplevel, "__init__", None)


def _toplevel_init_patch(self, *a, **kw):
    if _ORIG_TOPLEVEL_INIT:
        _ORIG_TOPLEVEL_INIT(self, *a, **kw)
    try:
        ensure_theme_applied(self)
    except Exception:
        pass


if _ORIG_TOPLEVEL_INIT and not getattr(tk.Toplevel, "_wm_autotheme_patched", False):
    tk.Toplevel.__init__ = _toplevel_init_patch
    tk.Toplevel._wm_autotheme_patched = True
    try:
        print("[WM-DBG][THEME] Auto-theme for Toplevel enabled")
    except Exception:
        pass

# ⏹ KONIEC KODU
