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

# Paleta domyślna
_DEFAULT_COLORS = {
    "dark_bg": "#1b1f24",      # tło główne
    "dark_bg_2": "#20262e",    # tło pól
    "side_bg": "#14181d",
    "card_bg": "#20262e",
    "fg": "#e6e6e6",
    "muted_fg": "#9aa0a6",
    "btn_bg": "#2a3139",
    "btn_bg_hover": "#343b45",
    "btn_bg_act": "#3b434e",
    "banner_fg": "#ff4d4d",
    "banner_bg": "#1b1b1b",
}

# Bieżące kolory
DARK_BG = _DEFAULT_COLORS["dark_bg"]
DARK_BG_2 = _DEFAULT_COLORS["dark_bg_2"]
SIDE_BG = _DEFAULT_COLORS["side_bg"]
CARD_BG = _DEFAULT_COLORS["card_bg"]
FG = _DEFAULT_COLORS["fg"]
MUTED_FG = _DEFAULT_COLORS["muted_fg"]
BTN_BG = _DEFAULT_COLORS["btn_bg"]
BTN_BG_HOVER = _DEFAULT_COLORS["btn_bg_hover"]
BTN_BG_ACT = _DEFAULT_COLORS["btn_bg_act"]
BANNER_FG = _DEFAULT_COLORS["banner_fg"]
BANNER_BG = _DEFAULT_COLORS["banner_bg"]

_inited = False

def _init_styles(root: tk.Misc | None = None) -> None:
    global _inited, DARK_BG, DARK_BG_2, SIDE_BG, CARD_BG, FG, MUTED_FG
    global BTN_BG, BTN_BG_HOVER, BTN_BG_ACT, BANNER_FG, BANNER_BG
    if _inited:
        return
    cfg = ConfigManager()
    colors = cfg.get("ui.colors", {})
    DARK_BG = colors.get("dark_bg", _DEFAULT_COLORS["dark_bg"])
    DARK_BG_2 = colors.get("dark_bg_2", _DEFAULT_COLORS["dark_bg_2"])
    SIDE_BG = colors.get("side_bg", _DEFAULT_COLORS["side_bg"])
    CARD_BG = colors.get("card_bg", _DEFAULT_COLORS["card_bg"])
    FG = colors.get("fg", _DEFAULT_COLORS["fg"])
    MUTED_FG = colors.get("muted_fg", _DEFAULT_COLORS["muted_fg"])
    BTN_BG = colors.get("btn_bg", _DEFAULT_COLORS["btn_bg"])
    BTN_BG_HOVER = colors.get(
        "btn_bg_hover", _DEFAULT_COLORS["btn_bg_hover"]
    )
    BTN_BG_ACT = colors.get("btn_bg_act", _DEFAULT_COLORS["btn_bg_act"])
    BANNER_FG = colors.get("banner_fg", _DEFAULT_COLORS["banner_fg"])
    BANNER_BG = colors.get("banner_bg", _DEFAULT_COLORS["banner_bg"])
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

# ===== Kolory magazynu (używane przez gui_magazyn) =====
COLORS = {
    "stock_ok":   "#2d6a4f",
    "stock_warn": "#d35400",
    "stock_low":  "#c0392b",
}
