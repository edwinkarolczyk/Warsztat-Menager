# Plik: ustawienia_systemu.py
# Wersja pliku: 1.5.2
# Zmiany 1.5.2 (2025-08-18):
# - apply_theme wywoływany na oknie nadrzędnym (frame.winfo_toplevel())
# - Notebook i Frame używają stylu WM.* tylko jeśli taki styl istnieje (fallback do domyślnego)
# - Bez zmian funkcjonalnych w zakładkach
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager, ConfigError
import ustawienia_uzytkownicy
from gui_settings_shifts import ShiftsSettingsFrame

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

    lang_var = tk.StringVar(value=cfg.get("ui.language", "pl"))
    theme_var = tk.StringVar(value=cfg.get("ui.theme", "dark"))
    accent_var = tk.StringVar(value=cfg.get("ui.accent", "red"))
    backup_var = tk.StringVar(value=cfg.get("backup.folder", ""))
    auto_var = tk.BooleanVar(value=cfg.get("updates.auto", True))
    remote_var = tk.StringVar(value=cfg.get("updates.remote", "origin"))
    branch_var = tk.StringVar(value=cfg.get("updates.branch", "proby-rozwoju"))
    connection_status_var = tk.StringVar()
    color_vars = {
        "dark_bg": tk.StringVar(
            value=cfg.get("ui.colors.dark_bg", "#1b1f24")
        ),
        "dark_bg_2": tk.StringVar(
            value=cfg.get("ui.colors.dark_bg_2", "#20262e")
        ),
        "side_bg": tk.StringVar(
            value=cfg.get("ui.colors.side_bg", "#14181d")
        ),
        "card_bg": tk.StringVar(
            value=cfg.get("ui.colors.card_bg", "#20262e")
        ),
        "fg": tk.StringVar(value=cfg.get("ui.colors.fg", "#e6e6e6")),
        "muted_fg": tk.StringVar(
            value=cfg.get("ui.colors.muted_fg", "#9aa0a6")
        ),
        "btn_bg": tk.StringVar(
            value=cfg.get("ui.colors.btn_bg", "#2a3139")
        ),
        "btn_bg_hover": tk.StringVar(
            value=cfg.get("ui.colors.btn_bg_hover", "#343b45")
        ),
        "btn_bg_act": tk.StringVar(
            value=cfg.get("ui.colors.btn_bg_act", "#3b434e")
        ),
        "banner_fg": tk.StringVar(
            value=cfg.get("ui.colors.banner_fg", "#ff4d4d")
        ),
        "banner_bg": tk.StringVar(
            value=cfg.get("ui.colors.banner_bg", "#1b1b1b")
        ),
    }

    # --- Motyw ---
    tab_theme = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_theme, text="Motyw")

    frm_theme = ttk.Frame(tab_theme)
    frm_theme.pack(fill="x", padx=12, pady=12)
    frm_theme.columnconfigure(1, weight=1)

    ttk.Label(frm_theme, text="Motyw:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm_theme,
        textvariable=theme_var,
        values=["dark", "light"],
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_theme, text="Akcent:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm_theme,
        textvariable=accent_var,
        values=["red", "blue", "green", "orange"],
        state="readonly",
    ).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    for i, (color_key, var) in enumerate(color_vars.items(), start=2):
        ttk.Label(frm_theme, text=f"{color_key}:").grid(
            row=i, column=0, sticky="w", padx=5, pady=5
        )
        ttk.Entry(frm_theme, textvariable=var).grid(
            row=i, column=1, sticky="ew", padx=5, pady=5
        )
    _theme_save_row = len(color_vars) + 2

    # --- Ogólne ---
    tab1 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab1, text="Ogólne")

    frm = ttk.Frame(tab1)
    frm.pack(fill="x", padx=12, pady=12)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Język UI:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm,
        textvariable=lang_var,
        values=["pl", "en"],
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm, text="Katalog kopii zapasowych:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=backup_var).grid(
        row=1, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm, text="Automatyczne aktualizacje:").grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Checkbutton(frm, variable=auto_var).grid(
        row=2, column=1, sticky="w", padx=5, pady=5
    )

    ttk.Label(frm, text="Zdalne repozytorium:").grid(
        row=3, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=remote_var).grid(
        row=3, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm, text="Gałąź aktualizacji:").grid(
        row=4, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=branch_var).grid(
        row=4, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm, textvariable=connection_status_var).grid(
        row=5, column=0, columnspan=2, sticky="w", padx=5, pady=5
    )

    def _check_git_connection():
        remote = remote_var.get()
        branch = branch_var.get()
        try:
            subprocess.run(
                ["git", "ls-remote", remote, branch],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            connection_status_var.set("Połączenie prawidłowe")
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            connection_status_var.set(err)

    def _save():
        try:
            cfg.set("ui.language", lang_var.get())
            cfg.set("ui.theme", theme_var.get())
            cfg.set("ui.accent", accent_var.get())
            cfg.set("backup.folder", backup_var.get())
            cfg.set("updates.auto", bool(auto_var.get()))
            cfg.set("updates.remote", remote_var.get())
            cfg.set("updates.branch", branch_var.get())
            for color_key, var in color_vars.items():
                cfg.set(f"ui.colors.{color_key}", var.get())
            cfg.save_all()
            import ui_theme

            ui_theme._inited = False
            ui_theme.apply_theme(frame.winfo_toplevel())
        except ConfigError as e:
            messagebox.showerror("Błąd", str(e))

    ttk.Button(frm, text="Aktualizuj", command=_check_git_connection).grid(
        row=6, column=0, columnspan=2, pady=5
    )
    ttk.Button(frm, text="Zapisz", command=_save).grid(
        row=7, column=0, columnspan=2, pady=10
    )
    ttk.Button(frm_theme, text="Zapisz", command=_save).grid(
        row=_theme_save_row, column=0, columnspan=2, pady=10
    )

    _check_git_connection()

    # --- Użytkownicy ---
    tab2 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab2, text="Użytkownicy")
    ustawienia_uzytkownicy.make_tab(tab2, rola)

    # --- Magazyn ---
    tab3 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab3, text="Magazyn")
    try:
        panel_ustawien_magazyn(tab3)
    except Exception as e:
        ttk.Label(tab3, text=f"Panel Magazynu – błąd: {e}").pack(padx=10, pady=10)

    # --- Produkty (BOM) ---
    tab4 = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab4, text="Produkty (BOM)")
    try:
        panel_ustawien_produkty(tab4, rola)
    except Exception as e:
        ttk.Label(tab4, text=f"Panel Produktów (BOM) – błąd: {e}").pack(padx=10, pady=10)

    # --- Grafiki zmian ---
    tab_sh = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_sh, text="Grafiki zmian")
    ShiftsSettingsFrame(tab_sh).pack(fill="both", expand=True)

    # --- Aktualizacje ---
    tab5 = UpdatesUI(nb)
    nb.add(tab5, text="Aktualizacje")

# ⏹ KONIEC KODU
