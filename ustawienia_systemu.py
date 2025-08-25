# Plik: ustawienia_systemu.py
# Wersja pliku: 1.5.2
# Zmiany 1.5.2 (2025-08-18):
# - apply_theme wywoływany na oknie nadrzędnym (frame.winfo_toplevel())
# - Notebook i Frame używają stylu WM.* tylko jeśli taki styl istnieje (fallback do domyślnego)
# - Bez zmian funkcjonalnych w zakładkach
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme

# --- import panelu magazynowego ---
try:
    from gui_magazyn import panel_ustawien_magazyn
except Exception:
    def panel_ustawien_magazyn(parent):
        ttk.Label(parent, text="Panel ustawień Magazynu – błąd importu").pack(padx=10, pady=10)

# --- import panelu produktów (BOM) ---
try:
    from ustawienia_produkty_bom import make_tab as panel_ustawien_produkty
except Exception:
    def panel_ustawien_produkty(parent, rola=None):
        ttk.Label(parent, text="Panel ustawień Produktów (BOM) – błąd importu").pack(padx=10, pady=10)

# --- import zakładki Aktualizacje ---
try:
    from updater import UpdatesUI
except Exception:
    class UpdatesUI(ttk.Frame):
        def __init__(self, master):
            super().__init__(master)
            ttk.Label(self, text="Aktualizacje – błąd importu updater.py").pack(padx=10, pady=10)

def _style_exists(stylename: str) -> bool:
    try:
        st = ttk.Style()
        return bool(st.layout(stylename))
    except Exception:
        return False

def _make_frame(parent, style_name: str | None = None) -> ttk.Frame:
    if style_name and _style_exists(style_name):
        return ttk.Frame(parent, style=style_name)
    return ttk.Frame(parent)

def panel_ustawien(root, frame, login=None, rola=None):
    # wyczyść
    for w in frame.winfo_children():
        w.destroy()

    # Zastosuj motyw NA OKNIE nadrzędnym
    apply_theme(frame.winfo_toplevel())

    # Notebook — użyj stylu tylko jeśli istnieje
    if _style_exists("WM.TNotebook"):
        nb = ttk.Notebook(frame, style="WM.TNotebook")
    else:
        nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    # --- Ogólne ---
    tab1 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab1, text="Ogólne")
    ttk.Label(tab1, text="Ustawienia ogólne systemu").pack(padx=12, pady=12)

    # --- Użytkownicy ---
    tab2 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab2, text="Użytkownicy")
    ttk.Label(tab2, text="Zarządzanie użytkownikami").pack(padx=12, pady=12)

    # --- Magazyn ---
    tab3 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab3, text="Magazyn")
    panel_ustawien_magazyn(tab3)

    # --- Produkty (BOM) ---
    tab4 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab4, text="Produkty (BOM)")
    panel_ustawien_produkty(tab4, rola)

    # --- Aktualizacje ---
    tab5 = UpdatesUI(nb)
    nb.add(tab5, text="Aktualizacje")

# ⏹ KONIEC KODU
