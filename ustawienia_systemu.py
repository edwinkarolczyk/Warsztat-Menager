# Plik: ustawienia_systemu.py
# Wersja pliku: 1.6.0
# Zmiany 1.6.0:
# - Dodano zakładki: Logowanie/Autoryzacja, Ścieżki danych,
#   Moduły i widoki, Wygląd i rozdzielczość, Narzędzia oraz
#   Profile użytkowników
# - Zmiany zapisywane przez ConfigManager.set i odświeżanie motywu
#   dla ustawień wpływających na wygląd
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import subprocess

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager, ConfigError
import ustawienia_uzytkownicy
from gui_settings_shifts import ShiftsSettingsFrame
from utils.gui_helpers import clear_frame

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
    clear_frame(frame)

    container = ttk.Frame(frame)
    container.pack(fill="both", expand=True)

    # Zastosuj motyw NA OKNIE nadrzędnym
    apply_theme(container.winfo_toplevel())

    # Notebook — użyj stylu tylko jeśli istnieje
    if _style_exists("WM.TNotebook"):
        nb = ttk.Notebook(container, style="WM.TNotebook")
    else:
        nb = ttk.Notebook(container)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    lang_var = tk.StringVar(value=cfg.get("ui.language", "pl"))
    theme_var = tk.StringVar(value=cfg.get("ui.theme", "dark"))
    accent_var = tk.StringVar(value=cfg.get("ui.accent", "red"))
    backup_var = tk.StringVar(value=cfg.get("backup.folder", ""))
    auto_var = tk.BooleanVar(value=cfg.get("updates.auto", True))
    remote_var = tk.StringVar(value=cfg.get("updates.remote", "origin"))
    branch_var = tk.StringVar(value=cfg.get("updates.branch", "proby-rozwoju"))
    push_branch_var = tk.StringVar(value=cfg.get("updates.push_branch", "git-push"))
    feedback_url_var = tk.StringVar(value=cfg.get("feedback.url", ""))
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

    color_labels = {
        "dark_bg": "Tło główne",
        "dark_bg_2": "Tło drugiego planu",
        "side_bg": "Tło panelu bocznego",
        "card_bg": "Tło kart (ramki ustawień)",
        "fg": "Kolor tekstu",
        "muted_fg": "Kolor tekstu przygaszonego",
        "btn_bg": "Tło przycisków",
        "btn_bg_hover": "Tło przycisków (najechanie)",
        "btn_bg_act": "Tło przycisków (aktywny)",
        "banner_fg": "Kolor tekstu baneru",
        "banner_bg": "Tło baneru",
    }

    # zmienne dla dodatkowych zakładek
    auth_required_var = tk.BooleanVar(value=cfg.get("auth.required", True))
    auth_timeout_var = tk.IntVar(
        value=cfg.get("auth.session_timeout_min", 30)
    )
    auth_pin_var = tk.IntVar(value=cfg.get("auth.pin_length", 4))
    pinless_brygadzista_var = tk.BooleanVar(
        value=cfg.get("auth.pinless_brygadzista", False)
    )

    path_maszyny_var = tk.StringVar(
        value=cfg.get("paths.maszyny", "maszyny.json")
    )
    path_narzedzia_var = tk.StringVar(
        value=cfg.get("paths.narzedzia", "narzedzia.json")
    )
    path_zlecenia_var = tk.StringVar(
        value=cfg.get("paths.zlecenia", "zlecenia.json")
    )
    data_dir_var = tk.StringVar(value=cfg.get("sciezka_danych", "data/"))

    start_view_var = tk.StringVar(
        value=cfg.get("app.start_view", "dashboard")
    )
    module_service_var = tk.BooleanVar(
        value=cfg.get("modules.service.enabled", True)
    )
    mini_hall_var = tk.BooleanVar(
        value=cfg.get("dashboard.mini_hall.enabled", True)
    )

    fullscreen_var = tk.BooleanVar(
        value=cfg.get("local.fullscreen_on_start", False)
    )
    ui_scale_var = tk.IntVar(value=cfg.get("local.ui_scale", 100))
    hall_grid_var = tk.IntVar(value=cfg.get("hall.grid_size_px", 4))

    profiles_tab_enabled_var = tk.BooleanVar(
        value=cfg.get("profiles.tab_enabled", True)
    )
    profiles_show_name_var = tk.BooleanVar(
        value=cfg.get("profiles.show_name_in_header", True)
    )
    profiles_avatar_dir_var = tk.StringVar(
        value=cfg.get("profiles.avatar_dir", "")
    )
    profiles_fields_visible_text = "\n".join(
        cfg.get("profiles.fields_visible", [])
    )
    profiles_fields_editable_text = "\n".join(
        cfg.get("profiles.fields_editable_by_user", [])
    )
    profiles_allow_pin_change_var = tk.BooleanVar(
        value=cfg.get("profiles.allow_pin_change", False)
    )
    profiles_task_deadline_var = tk.IntVar(
        value=cfg.get("profiles.task_default_deadline_days", 7)
    )

    statusy_nowe_text = "\n".join(cfg.get("statusy_narzedzi_nowe", []))
    statusy_stare_text = "\n".join(cfg.get("statusy_narzedzi_stare", []))
    szablony_text = "\n".join(cfg.get("szablony_zadan_narzedzia", []))
    szablony_stare_text = "\n".join(
        cfg.get("szablony_zadan_narzedzia_stare", [])
    )
    typy_narzedzi_text = "\n".join(cfg.get("typy_narzedzi", []))

    def _lines_from_text(widget: tk.Text) -> list[str]:
        return [
            ln.strip()
            for ln in widget.get("1.0", "end").splitlines()
            if ln.strip()
        ]

    class _TextWrapper:
        def __init__(self, widget: tk.Text):
            self.widget = widget

        def get(self):
            return _lines_from_text(self.widget)

        def set(self, value):
            self.widget.delete("1.0", "end")
            if isinstance(value, list):
                self.widget.insert("1.0", "\n".join(value))
            else:
                self.widget.insert("1.0", str(value))

    original_vals = {}
    dirty_keys = {}
    tracked_vars = {}

    def track(key, var, cast):
        original_vals[key] = cast(var.get())
        tracked_vars[key] = (var, cast)
        def _mark(*_):
            try:
                val = cast(var.get())
            except Exception:
                val = var.get()
            if val != original_vals[key]:
                dirty_keys[key] = True
            else:
                dirty_keys.pop(key, None)
        if hasattr(var, "trace_add"):
            var.trace_add("write", _mark)
        else:
            var.widget.bind("<FocusOut>", _mark)

    track("ui.language", lang_var, str)
    track("ui.theme", theme_var, str)
    track("ui.accent", accent_var, str)
    track("backup.folder", backup_var, str)
    track("updates.auto", auto_var, bool)
    track("updates.remote", remote_var, str)
    track("updates.branch", branch_var, str)
    track("updates.push_branch", push_branch_var, str)
    track("feedback.url", feedback_url_var, str)
    for color_key, var in color_vars.items():
        track(f"ui.colors.{color_key}", var, str)

    track("auth.required", auth_required_var, bool)
    track("auth.session_timeout_min", auth_timeout_var, int)
    track("auth.pin_length", auth_pin_var, int)
    track("auth.pinless_brygadzista", pinless_brygadzista_var, bool)

    track("paths.maszyny", path_maszyny_var, str)
    track("paths.narzedzia", path_narzedzia_var, str)
    track("paths.zlecenia", path_zlecenia_var, str)
    track("sciezka_danych", data_dir_var, str)

    track("app.start_view", start_view_var, str)
    track("modules.service.enabled", module_service_var, bool)
    track("dashboard.mini_hall.enabled", mini_hall_var, bool)

    track("local.fullscreen_on_start", fullscreen_var, bool)
    track("local.ui_scale", ui_scale_var, int)
    track("hall.grid_size_px", hall_grid_var, int)

    track("profiles.tab_enabled", profiles_tab_enabled_var, bool)
    track("profiles.show_name_in_header", profiles_show_name_var, bool)
    track("profiles.avatar_dir", profiles_avatar_dir_var, str)
    track("profiles.allow_pin_change", profiles_allow_pin_change_var, bool)
    track(
        "profiles.task_default_deadline_days", profiles_task_deadline_var, int
    )

    def on_exit(_event=None):
        if not dirty_keys:
            return
        if messagebox.askyesno("Zapisz", "Czy zapisać zmiany?"):
            changed = list(dirty_keys)
            for key in changed:
                var, cast = tracked_vars[key]
                try:
                    val = cast(var.get())
                except Exception:
                    val = var.get()
                cfg.set(key, val)
            cfg.save_all()
            top = container.winfo_toplevel()
            apply_theme(top)
            if "auth.session_timeout_min" in changed:
                try:
                    top.event_generate("<<AuthTimeoutChanged>>")
                except Exception:
                    pass
        else:
            for key in list(dirty_keys):
                var, _ = tracked_vars[key]
                var.set(original_vals[key])
        dirty_keys.clear()

    container.bind("<Destroy>", on_exit)

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
        ttk.Label(frm_theme, text=f"{color_labels[color_key]}:").grid(
            row=i, column=0, sticky="w", padx=5, pady=5
        )
        row_frame = ttk.Frame(frm_theme)
        row_frame.grid(row=i, column=1, sticky="ew", padx=5, pady=5)
        row_frame.columnconfigure(0, weight=1)
        ttk.Entry(row_frame, textvariable=var).grid(
            row=0, column=0, sticky="ew"
        )
        btn = tk.Button(row_frame, width=2, bg=var.get())
        btn.grid(row=0, column=1, padx=(5, 0))

        def _choose_color(v=var, b=btn):
            color = colorchooser.askcolor(initialcolor=v.get())[1]
            if color:
                v.set(color)
                b.configure(bg=color)
                apply_theme(container.winfo_toplevel())

        btn.configure(command=_choose_color)
        var.trace_add(
            "write", lambda *_v, v=var, b=btn: b.configure(bg=v.get())
        )

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

    ttk.Label(frm, text="Gałąź git push:").grid(
        row=5, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=push_branch_var).grid(
        row=5, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm, text="Adres wysyłania opinii:").grid(
        row=6, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=feedback_url_var).grid(
        row=6, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm, textvariable=connection_status_var).grid(
        row=7, column=0, columnspan=2, sticky="w", padx=5, pady=5
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

    ttk.Button(frm, text="Aktualizuj", command=_check_git_connection).grid(
        row=8, column=0, columnspan=2, pady=5
    )

    _check_git_connection()

    # --- Logowanie/Autoryzacja ---
    tab_auth = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_auth, text="Logowanie/Autoryzacja")
    frm_auth = ttk.Frame(tab_auth)
    frm_auth.pack(fill="x", padx=12, pady=12)
    frm_auth.columnconfigure(1, weight=1)

    ttk.Label(frm_auth, text="Wymagaj logowania:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Checkbutton(frm_auth, variable=auth_required_var).grid(
        row=0, column=1, sticky="w", padx=5, pady=5
    )

    ttk.Label(frm_auth, text="Limit bezczynności (min):").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_auth, from_=1, to=480, textvariable=auth_timeout_var, width=5
    ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(frm_auth, text="Długość PIN:").grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_auth, from_=4, to=8, textvariable=auth_pin_var, width=5
    ).grid(row=2, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(frm_auth, text="Logowanie brygadzisty bez PIN:").grid(
        row=3, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Checkbutton(
        frm_auth, variable=pinless_brygadzista_var
    ).grid(row=3, column=1, sticky="w", padx=5, pady=5)

    # --- Ścieżki danych ---
    tab_paths = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_paths, text="Ścieżki danych")
    frm_paths = ttk.Frame(tab_paths)
    frm_paths.pack(fill="x", padx=12, pady=12)
    frm_paths.columnconfigure(1, weight=1)

    ttk.Label(frm_paths, text="maszyny.json:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_paths, textvariable=path_maszyny_var).grid(
        row=0, column=1, sticky="ew", padx=5, pady=5
    )
    ttk.Label(frm_paths, text="narzedzia.json:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_paths, textvariable=path_narzedzia_var).grid(
        row=1, column=1, sticky="ew", padx=5, pady=5
    )
    ttk.Label(frm_paths, text="zlecenia.json:").grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_paths, textvariable=path_zlecenia_var).grid(
        row=2, column=1, sticky="ew", padx=5, pady=5
    )
    ttk.Label(frm_paths, text="Folder danych:").grid(
        row=3, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_paths, textvariable=data_dir_var).grid(
        row=3, column=1, sticky="ew", padx=5, pady=5
    )

    # --- Moduły i widoki ---
    tab_modules = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_modules, text="Moduły i widoki")
    frm_modules = ttk.Frame(tab_modules)
    frm_modules.pack(fill="x", padx=12, pady=12)
    frm_modules.columnconfigure(1, weight=1)

    ttk.Label(frm_modules, text="Widok startowy:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm_modules,
        textvariable=start_view_var,
        values=["dashboard", "hala", "narzedzia", "zlecenia"],
        state="readonly",
    ).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_modules, text="Moduł serwisowy włączony:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Checkbutton(frm_modules, variable=module_service_var).grid(
        row=1, column=1, sticky="w", padx=5, pady=5
    )
    ttk.Label(
        frm_modules, text="Mini-widok hali w Dashboard:"
    ).grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Checkbutton(frm_modules, variable=mini_hall_var).grid(
        row=2, column=1, sticky="w", padx=5, pady=5
    )

    # --- Wygląd i rozdzielczość ---
    tab_display = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_display, text="Wygląd i rozdzielczość")
    frm_display = ttk.Frame(tab_display)
    frm_display.pack(fill="x", padx=12, pady=12)
    frm_display.columnconfigure(1, weight=1)

    ttk.Label(frm_display, text="Pełny ekran przy starcie:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Checkbutton(frm_display, variable=fullscreen_var).grid(
        row=0, column=1, sticky="w", padx=5, pady=5
    )
    ttk.Label(frm_display, text="Skalowanie UI (%):").grid(
        row=1, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_display, from_=80, to=150, textvariable=ui_scale_var, width=5
    ).grid(row=1, column=1, sticky="w", padx=5, pady=5)
    ttk.Label(frm_display, text="Siatka hali (px):").grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_display, from_=1, to=20, textvariable=hall_grid_var, width=5
    ).grid(row=2, column=1, sticky="w", padx=5, pady=5)

    # --- Narzędzia ---
    tab_tools = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_tools, text="Narzędzia")
    frm_tools = ttk.Frame(tab_tools)
    frm_tools.pack(fill="both", expand=True, padx=12, pady=12)
    frm_tools.columnconfigure(1, weight=1)

    ttk.Label(frm_tools, text="Statusy – NOWE:").grid(
        row=0, column=0, sticky="nw", padx=5, pady=5
    )
    txt_statusy_nowe = tk.Text(frm_tools, height=5)
    txt_statusy_nowe.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    txt_statusy_nowe.insert("1.0", statusy_nowe_text)

    ttk.Label(frm_tools, text="Statusy – STARE:").grid(
        row=1, column=0, sticky="nw", padx=5, pady=5
    )
    txt_statusy_stare = tk.Text(frm_tools, height=5)
    txt_statusy_stare.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    txt_statusy_stare.insert("1.0", statusy_stare_text)

    ttk.Label(frm_tools, text="Szablony zadań:").grid(
        row=2, column=0, sticky="nw", padx=5, pady=5
    )
    txt_szablony = tk.Text(frm_tools, height=5)
    txt_szablony.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    txt_szablony.insert("1.0", szablony_text)

    ttk.Label(frm_tools, text="Szablony serwisowe STARE:").grid(
        row=3, column=0, sticky="nw", padx=5, pady=5
    )
    txt_szablony_stare = tk.Text(frm_tools, height=5)
    txt_szablony_stare.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    txt_szablony_stare.insert("1.0", szablony_stare_text)

    ttk.Label(frm_tools, text="Typy narzędzi:").grid(
        row=4, column=0, sticky="nw", padx=5, pady=5
    )
    txt_typy = tk.Text(frm_tools, height=5)
    txt_typy.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    txt_typy.insert("1.0", typy_narzedzi_text)

    statusy_nowe_var = _TextWrapper(txt_statusy_nowe)
    track("statusy_narzedzi_nowe", statusy_nowe_var, lambda x: x)
    statusy_stare_var = _TextWrapper(txt_statusy_stare)
    track("statusy_narzedzi_stare", statusy_stare_var, lambda x: x)
    szablony_var = _TextWrapper(txt_szablony)
    track("szablony_zadan_narzedzia", szablony_var, lambda x: x)
    szablony_stare_var = _TextWrapper(txt_szablony_stare)
    track("szablony_zadan_narzedzia_stare", szablony_stare_var, lambda x: x)
    typy_var = _TextWrapper(txt_typy)
    track("typy_narzedzi", typy_var, lambda x: x)

    # --- Profile użytkowników ---
    tab_profiles = _make_frame(nb, "WM.Card.TFrame")
    nb.add(tab_profiles, text="Profile użytkowników")
    frm_profiles = ttk.Frame(tab_profiles)
    frm_profiles.pack(fill="x", padx=12, pady=12)
    frm_profiles.columnconfigure(1, weight=1)

    ttk.Label(
        frm_profiles, text="Włącz kartę \"Profil użytkownika\":"
    ).grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Checkbutton(frm_profiles, variable=profiles_tab_enabled_var).grid(
        row=0, column=1, sticky="w", padx=5, pady=5
    )

    ttk.Label(
        frm_profiles, text="Pokaż zalogowanego w nagłówku:"
    ).grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Checkbutton(frm_profiles, variable=profiles_show_name_var).grid(
        row=1, column=1, sticky="w", padx=5, pady=5
    )

    ttk.Label(frm_profiles, text="Folder z avatarami:").grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_profiles, textvariable=profiles_avatar_dir_var).grid(
        row=2, column=1, sticky="ew", padx=5, pady=5
    )

    ttk.Label(frm_profiles, text="Pola widoczne w profilu:").grid(
        row=3, column=0, sticky="nw", padx=5, pady=5
    )
    txt_fields_visible = tk.Text(frm_profiles, height=4)
    txt_fields_visible.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    txt_fields_visible.insert("1.0", profiles_fields_visible_text)

    ttk.Label(frm_profiles, text="Pola edytowalne w profilu:").grid(
        row=4, column=0, sticky="nw", padx=5, pady=5
    )
    txt_fields_editable = tk.Text(frm_profiles, height=4)
    txt_fields_editable.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    txt_fields_editable.insert("1.0", profiles_fields_editable_text)

    fields_visible_var = _TextWrapper(txt_fields_visible)
    track("profiles.fields_visible", fields_visible_var, lambda x: x)
    fields_editable_var = _TextWrapper(txt_fields_editable)
    track("profiles.fields_editable_by_user", fields_editable_var, lambda x: x)

    ttk.Checkbutton(
        frm_profiles,
        text="Pozwól użytkownikowi zmieniać PIN",
        variable=profiles_allow_pin_change_var,
    ).grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    ttk.Label(
        frm_profiles, text="Domyślny termin zadania (dni):",
    ).grid(row=6, column=0, sticky="w", padx=5, pady=5)
    ttk.Spinbox(
        frm_profiles,
        from_=1,
        to=365,
        textvariable=profiles_task_deadline_var,
        width=5,
    ).grid(row=6, column=1, sticky="w", padx=5, pady=5)


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
        frm_prod = panel_ustawien_produkty(tab4, rola)
        frm_prod.pack(fill="both", expand=True)
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
