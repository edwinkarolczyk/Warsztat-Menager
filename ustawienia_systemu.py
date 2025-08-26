# Plik: ustawienia_systemu.py
# Wersja pliku: 1.5.2
# Zmiany 1.5.2 (2025-08-18):
# - apply_theme wywoływany na oknie nadrzędnym (frame.winfo_toplevel())
# - Notebook i Frame używają stylu WM.* tylko jeśli taki styl istnieje (fallback do domyślnego)
# - Bez zmian funkcjonalnych w zakładkach
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager, ConfigError

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
    cfg = ConfigManager()

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

    frm = ttk.Frame(tab1)
    frm.pack(fill="x", padx=12, pady=12)
    frm.columnconfigure(1, weight=1)

    lang_var = tk.StringVar(value=cfg.get("ui.language", "pl"))
    theme_var = tk.StringVar(value=cfg.get("ui.theme", "dark"))
    backup_var = tk.StringVar(value=cfg.get("backup.folder", ""))
    auto_var = tk.BooleanVar(value=cfg.get("updates.auto", True))

    ttk.Label(frm, text="Język UI:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Combobox(frm, textvariable=lang_var, values=["pl", "en"], state="readonly").grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm, text="Motyw:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Combobox(frm, textvariable=theme_var, values=["dark", "light"], state="readonly").grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm, text="Katalog kopii zapasowych:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(frm, textvariable=backup_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm, text="Automatyczne aktualizacje:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Checkbutton(frm, variable=auto_var).grid(row=3, column=1, sticky="w", padx=5, pady=5)

    def _save():
        try:
            cfg.set("ui.language", lang_var.get())
            cfg.set("ui.theme", theme_var.get())
            cfg.set("backup.folder", backup_var.get())
            cfg.set("updates.auto", bool(auto_var.get()))
            cfg.save_all()
        except ConfigError as e:
            messagebox.showerror("Błąd", str(e))

    ttk.Button(frm, text="Zapisz", command=_save).grid(row=4, column=0, columnspan=2, pady=10)

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
