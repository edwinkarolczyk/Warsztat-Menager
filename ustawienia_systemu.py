# Plik: ustawienia_systemu.py
# Wersja pliku: 1.7.0
# Zmiany 1.7.0:
# - Grupowanie zakładek ustawień
# - Opisy pod przełącznikami
# ⏹ KONIEC KODU

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import subprocess
import json
from pathlib import Path

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


SCHEMA_PATH = Path(__file__).with_name("settings_schema.json")
with SCHEMA_PATH.open(encoding="utf-8") as f:
    data = json.load(f)
    _SCHEMA_DESC = {
        opt["key"]: opt.get("description", "")
        for opt in data["options"]
    }
    _SCHEMA_LIMITS = {
        opt["key"]: (opt.get("min"), opt.get("max"))
        for opt in data["options"]
        if opt.get("type") in ("int", "float")
    }


def _switch_row(parent, row, label, var, key):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=(5, 0))
    ttk.Checkbutton(parent, variable=var).grid(row=row, column=1, sticky="w", padx=5, pady=(5, 0))
    ttk.Label(parent, text=_SCHEMA_DESC.get(key, ""), font=("", 8)).grid(
        row=row + 1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5)
    )
    return row + 2

def panel_ustawien(root, frame, login=None, rola=None):
    cfg = ConfigManager()

    # wyczyść
    clear_frame(frame)

    container = ttk.Frame(frame)
    container.pack(fill="both", expand=True)

    top = container.winfo_toplevel()

    def _refresh_theme(*_):
        apply_theme(top)

    # Zastosuj motyw NA OKNIE nadrzędnym
    _refresh_theme()

    # Notebook z grupami
    if _style_exists("WM.TNotebook"):
        nb_groups = ttk.Notebook(container, style="WM.TNotebook")
    else:
        nb_groups = ttk.Notebook(container)
    nb_groups.pack(fill="both", expand=True, padx=12, pady=12)

    group_has_multi = {
        "Ogólne": False,
        "Wygląd": True,
        "Hala/Widok": True,
        "Magazyn": True,
        "Zlecenia": False,
        "Narzędzia": False,
        "Profile": True,
        "Zaawansowane": True,
    }

    group_containers = {}
    for name, multi in group_has_multi.items():
        gframe = _make_frame(nb_groups, "WM.Card.TFrame")
        nb_groups.add(gframe, text=name)
        if multi:
            nb_inner = ttk.Notebook(gframe)
            nb_inner.pack(fill="both", expand=True)
            group_containers[name] = nb_inner
        else:
            group_containers[name] = gframe

    lang_var = tk.StringVar(value=cfg.get("ui.language", "pl"))
    theme_var = tk.StringVar(value=cfg.get("ui.theme", "dark"))
    theme_var.trace_add("write", _refresh_theme)
    accent_var = tk.StringVar(value=cfg.get("ui.accent", "red"))
    accent_var.trace_add("write", _refresh_theme)
    backup_var = tk.StringVar(value=cfg.get("backup.folder", ""))
    auto_var = tk.BooleanVar(value=cfg.get("updates.auto", True))
    remote_var = tk.StringVar(value=cfg.get("updates.remote", "origin"))
    branch_var = tk.StringVar(value=cfg.get("updates.branch", "proby-rozwoju"))
    push_branch_var = tk.StringVar(value=cfg.get("updates.push_branch", "git-push"))
    feedback_url_var = tk.StringVar(value=cfg.get("feedback.url", ""))
    connection_status_var = tk.StringVar()
    magazyn_rez_var = tk.BooleanVar(value=cfg.get("magazyn_rezerwacje", True))
    magazyn_precision_var = tk.IntVar(value=cfg.get("magazyn_precision_mb", 3))
    progi_alertow_txt = "\n".join(
        str(p) for p in cfg.get("progi_alertow_pct", [100])
    )
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
        value=cfg.get("paths.maszyny", "data/maszyny.json")
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

    statusy_nowe_text = "\n".join(
        cfg.get("statusy_narzedzi_nowe") or []
    )
    statusy_stare_text = "\n".join(
        cfg.get("statusy_narzedzi_stare") or []
    )
    szablony_text = "\n".join(
        cfg.get("szablony_zadan_narzedzia") or []
    )
    szablony_stare_text = "\n".join(
        cfg.get("szablony_zadan_narzedzia_stare") or []
    )
    typy_narzedzi_text = "\n".join(
        cfg.get("typy_narzedzi") or []
    )
    zlecenia_edit_roles_text = "\n".join(cfg.get("zlecenia.edit_roles", []))

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

        def trace_add(self, _mode, callback):
            def _cb(*_):
                callback()
            self.widget.bind("<KeyRelease>", _cb)
            self.widget.bind("<<Modified>>", _cb)
            self.widget.bind("<FocusOut>", _cb)

    original_vals = {}
    dirty_keys = {}
    tracked_vars = {}

    def track(key, var, cast):
        min_val, max_val = _SCHEMA_LIMITS.get(key, (None, None))
        try:
            original_vals[key] = cast(var.get())
        except Exception:
            original_vals[key] = var.get()

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
            var.widget.bind("<KeyRelease>", _mark)
            var.widget.bind("<<Modified>>", _mark)
            var.widget.bind("<FocusOut>", _mark)
        tracked_vars[key] = (var, cast, _mark, min_val, max_val)

    track("ui.language", lang_var, str)
    track("ui.theme", theme_var, str)
    track("ui.accent", accent_var, str)
    track("backup.folder", backup_var, str)
    track("updates.auto", auto_var, bool)
    track("updates.remote", remote_var, str)
    track("updates.branch", branch_var, str)
    track("updates.push_branch", push_branch_var, str)
    track("feedback.url", feedback_url_var, str)
    track("magazyn_rezerwacje", magazyn_rez_var, bool)
    track("magazyn_precision_mb", magazyn_precision_var, int)
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
        for var, _cast, mark, _min, _max in tracked_vars.values():
            mark()
        if not dirty_keys:
            return
        if not messagebox.askyesno("Zapisz", "Czy zapisać zmiany?"):
            for key in list(dirty_keys):
                var, _c, _m, _mn, _mx = tracked_vars[key]
                var.set(original_vals[key])
            dirty_keys.clear()
            return

        changed = list(dirty_keys)
        new_vals = {}
        for key in changed:
            var, cast, _m, min_val, max_val = tracked_vars[key]
            try:
                val = cast(var.get())
            except Exception:
                messagebox.showerror("Błąd", f"Nieprawidłowa wartość dla {key}")
                return
            if min_val is not None and val < min_val:
                messagebox.showerror(
                    "Błąd", f"Wartość dla {key} musi być ≥ {min_val}"
                )
                return
            if max_val is not None and val > max_val:
                messagebox.showerror(
                    "Błąd", f"Wartość dla {key} musi być ≤ {max_val}"
                )
                return
            new_vals[key] = val

        for key, val in new_vals.items():
            cfg.set(key, val)
            original_vals[key] = val
        cfg.save_all()
        apply_theme(top)
        try:
            top.event_generate("<<ConfigUpdated>>")
        except Exception:
            pass
        if "auth.session_timeout_min" in new_vals:
            try:
                top.event_generate("<<AuthTimeoutChanged>>")
            except Exception:
                pass
        dirty_keys.clear()

    # Check for unsaved changes when switching tabs
    nb_groups.bind("<<NotebookTabChanged>>", on_exit)
    for cont in group_containers.values():
        if isinstance(cont, ttk.Notebook):
            cont.bind("<<NotebookTabChanged>>", on_exit)

    def _close():
        on_exit()
        if top.winfo_exists():
            top.destroy()

    top.protocol("WM_DELETE_WINDOW", _close)

    # --- Motyw ---
    tab_theme = _make_frame(group_containers["Wygląd"], "WM.Card.TFrame")
    group_containers["Wygląd"].add(tab_theme, text="Motyw")

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
    tab1 = group_containers["Ogólne"]

    frm = ttk.Frame(tab1)
    frm.pack(fill="x", padx=12, pady=12)
    frm.columnconfigure(1, weight=1)

    row = 0
    ttk.Label(frm, text="Język UI:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm,
        textvariable=lang_var,
        values=["pl", "en"],
        state="readonly",
    ).grid(row=row, column=1, sticky="ew", padx=5, pady=5)

    row += 1
    ttk.Label(frm, text="Katalog kopii zapasowych:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=backup_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row = _switch_row(
        frm, row + 1, "Automatyczne aktualizacje:", auto_var, "updates.auto"
    )

    ttk.Label(frm, text="Zdalne repozytorium:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=remote_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row += 1
    ttk.Label(frm, text="Gałąź aktualizacji:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=branch_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row += 1
    ttk.Label(frm, text="Gałąź git push:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=push_branch_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row += 1
    ttk.Label(frm, text="Adres wysyłania opinii:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm, textvariable=feedback_url_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row += 1
    ttk.Label(frm, textvariable=connection_status_var).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=5, pady=5
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
    tab_auth = _make_frame(group_containers["Profile"], "WM.Card.TFrame")
    group_containers["Profile"].add(
        tab_auth, text="Logowanie/Autoryzacja"
    )
    frm_auth = ttk.Frame(tab_auth)
    frm_auth.pack(fill="x", padx=12, pady=12)
    frm_auth.columnconfigure(1, weight=1)

    row = 0
    row = _switch_row(
        frm_auth, row, "Wymagaj logowania:", auth_required_var, "auth.required"
    )

    ttk.Label(frm_auth, text="Limit bezczynności (min):").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_auth, from_=1, to=480, textvariable=auth_timeout_var, width=5
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)

    row += 1
    ttk.Label(frm_auth, text="Długość PIN:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_auth, from_=4, to=8, textvariable=auth_pin_var, width=5
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)

    row = _switch_row(
        frm_auth, row + 1, "Logowanie brygadzisty bez PIN:",
        pinless_brygadzista_var, "auth.pinless_brygadzista"
    )

    # --- Ścieżki danych ---
    tab_paths = _make_frame(group_containers["Zaawansowane"], "WM.Card.TFrame")
    group_containers["Zaawansowane"].add(tab_paths, text="Ścieżki danych")
    frm_paths = ttk.Frame(tab_paths)
    frm_paths.pack(fill="x", padx=12, pady=12)
    frm_paths.columnconfigure(1, weight=1)

    ttk.Label(frm_paths, text="data/maszyny.json:").grid(
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
    tab_modules = _make_frame(group_containers["Hala/Widok"], "WM.Card.TFrame")
    group_containers["Hala/Widok"].add(tab_modules, text="Moduły i widoki")
    frm_modules = ttk.Frame(tab_modules)
    frm_modules.pack(fill="x", padx=12, pady=12)
    frm_modules.columnconfigure(1, weight=1)

    row = 0
    ttk.Label(frm_modules, text="Widok startowy:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Combobox(
        frm_modules,
        textvariable=start_view_var,
        values=["dashboard", "hala", "narzedzia", "zlecenia"],
        state="readonly",
    ).grid(row=row, column=1, sticky="ew", padx=5, pady=5)

    row = _switch_row(
        frm_modules,
        row + 1,
        "Moduł serwisowy włączony:",
        module_service_var,
        "modules.service.enabled",
    )
    row = _switch_row(
        frm_modules,
        row,
        "Mini-widok hali w Dashboard:",
        mini_hall_var,
        "dashboard.mini_hall.enabled",
    )

    # --- Wygląd i rozdzielczość ---
    tab_display = _make_frame(group_containers["Wygląd"], "WM.Card.TFrame")
    group_containers["Wygląd"].add(tab_display, text="Wygląd i rozdzielczość")
    frm_display = ttk.Frame(tab_display)
    frm_display.pack(fill="x", padx=12, pady=12)
    frm_display.columnconfigure(1, weight=1)

    row = _switch_row(
        frm_display,
        0,
        "Pełny ekran przy starcie:",
        fullscreen_var,
        "local.fullscreen_on_start",
    )
    ttk.Label(frm_display, text="Skalowanie UI (%):").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_display, from_=80, to=150, textvariable=ui_scale_var, width=5
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)
    row += 1
    ttk.Label(frm_display, text="Siatka hali (px):").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_display, from_=1, to=20, textvariable=hall_grid_var, width=5
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)

    # --- Zlecenia ---
    tab_zlec = group_containers["Zlecenia"]
    frm_zlec = ttk.Frame(tab_zlec)
    frm_zlec.pack(fill="both", expand=True, padx=12, pady=12)
    frm_zlec.columnconfigure(1, weight=1)

    ttk.Label(frm_zlec, text="Role mogące edytować:").grid(row=0, column=0, sticky="nw", padx=5, pady=5)
    txt_zlec_roles = tk.Text(frm_zlec, height=4)
    txt_zlec_roles.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    txt_zlec_roles.insert("1.0", zlecenia_edit_roles_text)
    txt_zlec_roles.configure(state="normal")

    zlec_roles_var = _TextWrapper(txt_zlec_roles)
    track("zlecenia.edit_roles", zlec_roles_var, lambda x: x)

    # --- Narzędzia ---
    tab_tools = group_containers["Narzędzia"]
    frm_tools = ttk.Frame(tab_tools)
    frm_tools.pack(fill="both", expand=True, padx=12, pady=12)
    frm_tools.columnconfigure(1, weight=1)

    ttk.Label(frm_tools, text="Statusy – NOWE:").grid(
        row=0, column=0, sticky="nw", padx=5, pady=5
    )
    txt_statusy_nowe = tk.Text(frm_tools, height=5)
    txt_statusy_nowe.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_tools, text="Statusy – STARE:").grid(
        row=1, column=0, sticky="nw", padx=5, pady=5
    )
    txt_statusy_stare = tk.Text(frm_tools, height=5)
    txt_statusy_stare.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_tools, text="Szablony zadań:").grid(
        row=2, column=0, sticky="nw", padx=5, pady=5
    )
    txt_szablony = tk.Text(frm_tools, height=5)
    txt_szablony.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_tools, text="Szablony serwisowe STARE:").grid(
        row=3, column=0, sticky="nw", padx=5, pady=5
    )
    txt_szablony_stare = tk.Text(frm_tools, height=5)
    txt_szablony_stare.grid(row=3, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(frm_tools, text="Typy narzędzi:").grid(
        row=4, column=0, sticky="nw", padx=5, pady=5
    )
    txt_typy = tk.Text(frm_tools, height=5)
    txt_typy.grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    def reset_tools_defaults():
        txt_statusy_nowe.delete("1.0", tk.END)
        txt_statusy_nowe.insert("1.0", statusy_nowe_text)
        txt_statusy_stare.delete("1.0", tk.END)
        txt_statusy_stare.insert("1.0", statusy_stare_text)
        txt_szablony.delete("1.0", tk.END)
        txt_szablony.insert("1.0", szablony_text)
        txt_szablony_stare.delete("1.0", tk.END)
        txt_szablony_stare.insert("1.0", szablony_stare_text)
        txt_typy.delete("1.0", tk.END)
        txt_typy.insert("1.0", typy_narzedzi_text)

    reset_tools_defaults()

    ttk.Button(
        frm_tools,
        text="Przywróć domyślne",
        command=reset_tools_defaults,
    ).grid(row=5, column=1, sticky="e", padx=5, pady=5)

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
    tab_profiles = _make_frame(group_containers["Profile"], "WM.Card.TFrame")
    group_containers["Profile"].add(
        tab_profiles, text="Profile użytkowników"
    )
    frm_profiles = ttk.Frame(tab_profiles)
    frm_profiles.pack(fill="x", padx=12, pady=12)
    frm_profiles.columnconfigure(1, weight=1)

    row = 0
    row = _switch_row(
        frm_profiles,
        row,
        "Włącz kartę \"Profil użytkownika\":",
        profiles_tab_enabled_var,
        "profiles.tab_enabled",
    )
    row = _switch_row(
        frm_profiles,
        row,
        "Pokaż zalogowanego w nagłówku:",
        profiles_show_name_var,
        "profiles.show_name_in_header",
    )

    ttk.Label(frm_profiles, text="Folder z avatarami:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Entry(frm_profiles, textvariable=profiles_avatar_dir_var).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    row += 1
    ttk.Label(frm_profiles, text="Pola widoczne w profilu:").grid(
        row=row, column=0, sticky="nw", padx=5, pady=5
    )
    txt_fields_visible = tk.Text(frm_profiles, height=4)
    txt_fields_visible.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
    txt_fields_visible.insert("1.0", profiles_fields_visible_text)

    row += 1
    ttk.Label(frm_profiles, text="Pola edytowalne w profilu:").grid(
        row=row, column=0, sticky="nw", padx=5, pady=5
    )
    txt_fields_editable = tk.Text(frm_profiles, height=4)
    txt_fields_editable.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
    txt_fields_editable.insert("1.0", profiles_fields_editable_text)

    fields_visible_var = _TextWrapper(txt_fields_visible)
    track("profiles.fields_visible", fields_visible_var, lambda x: x)
    fields_editable_var = _TextWrapper(txt_fields_editable)
    track("profiles.fields_editable_by_user", fields_editable_var, lambda x: x)

    row = _switch_row(
        frm_profiles,
        row + 1,
        "Pozwól użytkownikowi zmieniać PIN",
        profiles_allow_pin_change_var,
        "profiles.allow_pin_change",
    )

    ttk.Label(
        frm_profiles, text="Domyślny termin zadania (dni):",
    ).grid(row=row, column=0, sticky="w", padx=5, pady=5)
    ttk.Spinbox(
        frm_profiles,
        from_=1,
        to=365,
        textvariable=profiles_task_deadline_var,
        width=5,
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)


    # --- Użytkownicy ---
    tab2 = _make_frame(group_containers["Profile"], "WM.Card.TFrame")
    group_containers["Profile"].add(tab2, text="Użytkownicy")
    ustawienia_uzytkownicy.make_tab(tab2, rola)

    # --- Magazyn ---
    tab_opts = _make_frame(group_containers["Magazyn"], "WM.Card.TFrame")
    group_containers["Magazyn"].add(tab_opts, text="Opcje")
    frm_opts = ttk.Frame(tab_opts)
    frm_opts.pack(fill="x", padx=12, pady=12)
    frm_opts.columnconfigure(1, weight=1)
    row = 0
    row = _switch_row(
        frm_opts,
        row,
        "Włącz rezerwacje:",
        magazyn_rez_var,
        "magazyn_rezerwacje",
    )
    ttk.Label(frm_opts, text="Miejsca po przecinku:").grid(
        row=row, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Spinbox(
        frm_opts,
        from_=0,
        to=6,
        textvariable=magazyn_precision_var,
        width=5,
    ).grid(row=row, column=1, sticky="w", padx=5, pady=5)
    ttk.Label(
        frm_opts,
        text=_SCHEMA_DESC.get("magazyn_precision_mb", ""),
        font=("", 8),
    ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))
    row += 2
    ttk.Label(frm_opts, text="Progi alertów (%):").grid(
        row=row, column=0, sticky="nw", padx=5, pady=5
    )
    txt_progi = tk.Text(frm_opts, height=4)
    txt_progi.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
    txt_progi.insert("1.0", progi_alertow_txt)
    ttk.Label(
        frm_opts,
        text=_SCHEMA_DESC.get("progi_alertow_pct", ""),
        font=("", 8),
    ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))
    progi_alertow_var = _TextWrapper(txt_progi)
    track(
        "progi_alertow_pct",
        progi_alertow_var,
        lambda x: [float(p) for p in x if p],
    )

    tab_mag = _make_frame(group_containers["Magazyn"], "WM.Card.TFrame")
    group_containers["Magazyn"].add(tab_mag, text="Magazyn")
    try:
        panel_ustawien_magazyn(tab_mag)
    except Exception as e:
        ttk.Label(tab_mag, text=f"Panel Magazynu – błąd: {e}").pack(padx=10, pady=10)

    # --- Produkty (BOM) ---
    tab_prod = _make_frame(group_containers["Magazyn"], "WM.Card.TFrame")
    group_containers["Magazyn"].add(tab_prod, text="Produkty (BOM)")
    try:
        frm_prod = panel_ustawien_produkty(tab_prod, rola)
        frm_prod.pack(fill="both", expand=True)
    except Exception as e:
        ttk.Label(tab_prod, text=f"Panel Produktów (BOM) – błąd: {e}").pack(padx=10, pady=10)

    # --- Grafiki zmian ---
    tab_sh = _make_frame(group_containers["Hala/Widok"], "WM.Card.TFrame")
    group_containers["Hala/Widok"].add(tab_sh, text="Grafiki zmian")
    ShiftsSettingsFrame(tab_sh).pack(fill="both", expand=True)

    # --- Aktualizacje ---
    tab5 = UpdatesUI(group_containers["Zaawansowane"])
    group_containers["Zaawansowane"].add(tab5, text="Aktualizacje")

# ⏹ KONIEC KODU
