# =====================================================================
# ui_theme.py — DOKUMENTACJA (bez zmian logiki)
# ---------------------------------------------------------------------
# Ten blok komentarzy wyjaśnia, co odpowiada za kolory i style w motywie.
#
# GŁÓWNA PALETA (typowe nazwy zmiennych w tym pliku):
# - DARK_BG / BASE_BG         → główne tło okna (root/Toplevel)
# - DARK_BG_2 / INPUT_BG      → tło pól edycyjnych (Entry/Combobox/Spinbox)
# - SIDE_BG                   → tło bocznego paska (sidebar)
# - CARD_BG                   → tło kart/paneli (ramek typu "card")
# - FG / TEXT_FG              → podstawowy kolor tekstu (jasny)
# - MUTED_FG                  → przygaszony tekst (opisy, hinty)
# - BTN_BG                    → tło przycisków
# - BTN_BG_HOVER              → tło przycisków w stanie hover
# - BTN_BG_ACT                → tło przycisków w stanie aktywnym/klikniętym
#
# TTK STYLE KLASY (typowe użycie):
# - "WM.TFrame"               → ogólne ramki na ciemnym tle
# - "WM.Card.TFrame"          → panele/kafelki
# - "WM.Side.TFrame"          → panel boczny (sidebar)
#
# - "WM.TLabel"               → zwykłe etykiety
# - "WM.Card.TLabel"          → etykiety w kartach/panelach
# - "WM.Muted.TLabel"         → przygaszone etykiety (np. drobne opisy)
# - "WM.H1.TLabel"            → większe nagłówki (bold)
#
# - "WM.Side.TButton"         → przyciski w sidebarze (kolory BTN_*)
# - "TEntry / TCombobox / TSpinbox"
#                            → pola wejściowe (tło INPUT_BG, tekst FG,
#                              w readonly/disabled używany bywa MUTED_FG)
#
# - "WM.Treeview"             → wiersze tabeli (tło DARK_BG, tekst FG)
# - "WM.Treeview.Heading"     → nagłówki kolumn (BTN_BG / BTN_BG_HOVER)
#
# - "TNotebook" / "TNotebook.Tab"
#                            → zakładki (taby) – zwykle BTN_BG, wybrany BTN_BG_HOVER
#
# KOLORY SPECJALNE (jeśli występują):
# - COLORS['stock_ok']        → zielony (stany OK) dla Magazynu
# - COLORS['stock_warn']      → pomarańczowy (niski stan)
# - COLORS['stock_low']       → czerwony (bardzo niski stan)
#
# UWAGA: Poniżej zaczyna się NIEZMIENIONY kod Twojego pliku.
# =====================================================================

# =============================
# FILE: ui_theme.py
# VERSION: 1.1.3 (stable dark + magazyn colors)
# - Spójny ciemny motyw
# - WM.Treeview, karty, boczny panel
# - COLORS dla modułu Magazyn (stock_ok/warn/low)
# =============================

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from config_manager import ConfigManager

# Dostępne palety motywów
_THEMES = {
    "dark": {
        "dark_bg": "#1b1f24",
        "dark_bg_2": "#20262e",
        "side_bg": "#14181d",
        "card_bg": "#20262e",
        "fg": "#e6e6e6",
        "muted_fg": "#9aa0a6",
        "btn_bg": "#2a3139",
        "btn_bg_hover": "#343b45",
        "btn_bg_act": "#3b434e",
        "banner_bg": "#1b1b1b",
    },
    "light": {
        "dark_bg": "#f2f2f2",
        "dark_bg_2": "#ffffff",
        "side_bg": "#e6e6e6",
        "card_bg": "#ffffff",
        "fg": "#000000",
        "muted_fg": "#555555",
        "btn_bg": "#dddddd",
        "btn_bg_hover": "#cccccc",
        "btn_bg_act": "#bbbbbb",
        "banner_bg": "#ffffff",
    },
    "funky": {
        "dark_bg": "#2e1b47",
        "dark_bg_2": "#3b2a5d",
        "side_bg": "#25163b",
        "card_bg": "#3b2a5d",
        "fg": "#f0e130",
        "muted_fg": "#c0c0c0",
        "btn_bg": "#ff6f61",
        "btn_bg_hover": "#ff836e",
        "btn_bg_act": "#ff9e84",
        "banner_bg": "#1b1b1b",
    },
}

_ACCENTS = {
    "red": "#ff4d4d",
    "blue": "#4da6ff",
    "green": "#4dff4d",
    "orange": "#ffa64d",
}

_DEFAULT_THEME = "dark"
_DEFAULT_ACCENT = "red"

# Bieżące kolory
_palette = _THEMES[_DEFAULT_THEME]
DARK_BG = _palette["dark_bg"]
DARK_BG_2 = _palette["dark_bg_2"]
SIDE_BG = _palette["side_bg"]
CARD_BG = _palette["card_bg"]
FG = _palette["fg"]
MUTED_FG = _palette["muted_fg"]
BTN_BG = _palette["btn_bg"]
BTN_BG_HOVER = _palette["btn_bg_hover"]
BTN_BG_ACT = _palette["btn_bg_act"]
BANNER_FG = _ACCENTS[_DEFAULT_ACCENT]
BANNER_BG = _palette["banner_bg"]

_inited = False

def _init_styles(root: tk.Misc | None = None) -> None:
    global _inited, DARK_BG, DARK_BG_2, SIDE_BG, CARD_BG, FG, MUTED_FG
    global BTN_BG, BTN_BG_HOVER, BTN_BG_ACT, BANNER_FG, BANNER_BG
    if _inited:
        return
    cfg = ConfigManager()
    theme_name = cfg.get("ui.theme", _DEFAULT_THEME)
    palette = _THEMES.get(theme_name, _THEMES[_DEFAULT_THEME])
    accent_name = cfg.get("ui.accent", _DEFAULT_ACCENT)
    accent = _ACCENTS.get(accent_name, _ACCENTS[_DEFAULT_ACCENT])
    DARK_BG = palette["dark_bg"]
    DARK_BG_2 = palette["dark_bg_2"]
    SIDE_BG = palette["side_bg"]
    CARD_BG = palette["card_bg"]
    FG = palette["fg"]
    MUTED_FG = palette["muted_fg"]
    BTN_BG = palette["btn_bg"]
    BTN_BG_HOVER = palette["btn_bg_hover"]
    BTN_BG_ACT = palette["btn_bg_act"]
    BANNER_FG = accent
    BANNER_BG = palette["banner_bg"]
    style = ttk.Style(root)
    try:
        if style.theme_use() != "clam":
            style.theme_use("clam")
    except Exception:
        pass

    # Bazowe style dla standardowych klas
    style.configure("TFrame", background=DARK_BG)
    style.configure("TLabel", background=DARK_BG, foreground=FG)
    style.configure("TButton", background=BTN_BG, foreground=FG, padding=6)

    # Frames / cards / side
    style.configure("WM.TFrame", background=DARK_BG)
    style.configure("WM.Card.TFrame", background=CARD_BG)
    style.configure("WM.Side.TFrame", background=SIDE_BG)

    # Labels
    style.configure("WM.TLabel", background=DARK_BG, foreground=FG)
    style.configure("WM.Card.TLabel", background=CARD_BG, foreground=FG)
    style.configure("WM.Muted.TLabel", background=DARK_BG, foreground=MUTED_FG)
    style.configure("WM.H1.TLabel", background=DARK_BG, foreground=FG, font=("Segoe UI", 16, "bold"))
    style.configure("WM.Banner.TLabel", background=BANNER_BG, foreground=BANNER_FG,
                    font=("Consolas", 11, "bold"))

    # Buttons (w tym boczne)
    style.configure("WM.Side.TButton", background=BTN_BG, foreground=FG, padding=6)
    style.map("WM.Side.TButton",
              background=[("active", BTN_BG_HOVER), ("pressed", BTN_BG_ACT)],
              relief=[("pressed", "sunken"), ("!pressed", "flat")])

    # Inputs
    for base in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(base,
                        fieldbackground=DARK_BG_2,
                        background=BTN_BG,
                        foreground=FG)
        style.map(base,
                  fieldbackground=[("readonly", DARK_BG_2), ("focus", DARK_BG_2)],
                  foreground=[("disabled", MUTED_FG)])

    # Treeview
    style.configure("WM.Treeview",
                    background=DARK_BG,
                    fieldbackground=DARK_BG,
                    foreground=FG,
                    borderwidth=0)
    style.map("WM.Treeview",
              background=[("selected", BTN_BG_HOVER)],
              foreground=[("selected", FG)])
    style.configure("WM.Treeview.Heading",
                    background=BTN_BG,
                    foreground=FG)
    style.map("WM.Treeview.Heading",
              background=[("active", BTN_BG_HOVER), ("pressed", BTN_BG_ACT)])

    # Notebook
    style.configure("TNotebook", background=DARK_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=BTN_BG, foreground=FG)
    style.map("TNotebook.Tab",
              background=[("selected", BTN_BG_HOVER)],
              foreground=[("selected", FG)])

    _inited = True


def apply_theme(widget: tk.Misc | None) -> None:
    """Idempotentny motyw ciemny. Ustawia bg TYLKO na Tk/Toplevel."""
    _init_styles(widget)
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        try:
            widget.configure(bg=DARK_BG)
        except Exception:
            pass


def apply_theme_safe(widget: tk.Misc | None) -> None:
    """Wrapper na :func:`apply_theme`, ignorujący wszelkie wyjątki."""
    try:
        apply_theme(widget)
    except Exception:
        pass


def apply_theme_tree(widget: tk.Misc | None) -> None:
    """Zastosuj motyw dla podanego widgetu i całego jego drzewa potomków."""
    apply_theme_safe(widget)
    if hasattr(widget, "winfo_children"):
        for child in widget.winfo_children():
            apply_theme_tree(child)

# ===== Kolory magazynu (używane przez gui_magazyn) =====
COLORS = {
    "stock_ok":   "#2d6a4f",
    "stock_warn": "#d35400",
    "stock_low":  "#c0392b",
}
