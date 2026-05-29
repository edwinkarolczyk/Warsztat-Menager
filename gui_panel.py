# WM-VERSION: 0.1
# Plik: gui_panel.py
# version: 1.0
# Zmiany 1.6.17:
# - Dodano przycisk w stopce otwierający changelog.
# - Zapamiętywanie czasu ostatniego obejrzenia changeloga.
# Poprzednio (1.6.16):
# - Dodano przycisk „Magazyn” (wymaga gui_magazyn.open_panel_magazyn)
# - Pasek nagłówka pokazuje kto jest zalogowany (label po prawej)
# - Reszta bez zmian względem 1.6.15
#
# Poprzednio (1.6.15):
# - Adapter zgodności do panelu zleceń.

import json
import os
import re
import traceback
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import tkinter as tk
from tkinter import TclError, messagebox, ttk

from services.profile_service import ProfileService, get_user, save_user
from wm_perf import PerfFlow, perf_span

from ui_theme import apply_theme_safe as apply_theme
from ui_theme import ensure_theme_applied
from utils.gui_helpers import clear_frame

# --- CHAT (Messenger beta) ---
try:  # pragma: no cover - moduł opcjonalny
    from chat_store import append_message, read_messages, get_unread_count, mark_read
except Exception:  # pragma: no cover
    append_message = read_messages = get_unread_count = mark_read = None  # type: ignore
# [PR-1165-MERGE-FIX] unikajmy zbyt szerokiego importu z start (ryzyko cyklu)
from start import CONFIG_MANAGER
import gui_changelog
from logger import log_akcja
from profile_utils import ADMIN_ROLE_NAMES, SIDEBAR_MODULES, can_access_jarvis
from ustawienia_systemu import panel_ustawien
from utils.moduly import module_active, zaladuj_manifest
from wm_access import (
    get_disabled_modules_for,
    get_effective_allowed_modules,
    is_module_allowed_for_user,
    normalize_module_name,
    normalize_role_name,
)
from gui.widgets_user_footer import (
    _shift_bounds,
    _shift_progress,
    _current_shift_label,
)

# Lokalny dodatek: Chat jako moduł (bez ruszania profile_utils).
try:
    _SIDEBAR_BASE = list(SIDEBAR_MODULES)
except Exception:
    _SIDEBAR_BASE = []
SIDEBAR_MODULES_EXT = _SIDEBAR_BASE + (
    [("chat", "Chat")] if ("chat", "Chat") not in _SIDEBAR_BASE else []
)

try:  # pragma: no cover - zależne od środowiska GUI
    from gui_notifications import register_notification_root as _register_notification_root
except Exception:  # pragma: no cover - fallback dla trybu headless
    _register_notification_root = None  # type: ignore[assignment]


def _warn(msg: str):
    try:
        from ui_theme import warn_banner  # type: ignore[attr-defined]

        warn_banner(msg)
    except Exception:
        print(f"[WARN] {msg}")


try:
    import gui_narzedzia  # noqa: F401
except Exception as e:  # pragma: no cover - fallback logging
    _warn(f"Panel narzędzi (fallback) – błąd importu gui_narzedzia: {e!s}")
    gui_narzedzia = None  # type: ignore

try:
    import gui_zlecenia  # noqa: F401
except Exception as e:  # pragma: no cover - fallback logging
    _warn(f"Panel Dyspozycji (fallback) – błąd importu gui_zlecenia: {e!s}")
    gui_zlecenia = None  # type: ignore

try:
    import gui_planowanie  # noqa: F401
except Exception as e:  # pragma: no cover - fallback logging
    _warn(f"Panel planowania (fallback) – błąd importu gui_planowanie: {e!s}")
    gui_planowanie = None  # type: ignore

# --- PROFIL: nowy widok ---
try:
    from gui_profile import ProfileView
except Exception as e:  # pragma: no cover - import fallback
    print(
        f"[ERROR][PROFILE] Nie można zaimportować ProfileView z gui_profile.py: {e}"
    )
    ProfileView = None


def _get_app_version() -> str:
    """Zwróć numer wersji z ``__version__.py`` lub ``pyproject.toml``."""
    try:
        from __version__ import __version__  # type: ignore
        return __version__
    except Exception:
        try:
            import tomllib  # type: ignore
            with open("pyproject.toml", "rb") as fh:
                data = tomllib.load(fh)
            return data.get("project", {}).get("version", "dev")
        except Exception:
            return "dev"


APP_VERSION = _get_app_version()


def _wm_get_current_theme() -> str:
    try:
        cm = globals().get("CONFIG_MANAGER")
        if cm is not None:
            value = cm.get("ui.theme", None)
            if value:
                return str(value)
            value = cm.get("theme", None)
            if value:
                return str(value)
    except Exception:
        pass
    return "default"


def _wm_save_theme(theme_name: str) -> bool:
    theme = str(theme_name or "").strip() or "default"
    try:
        cm = globals().get("CONFIG_MANAGER")
        if cm is None:
            return False
        if hasattr(cm, "set"):
            cm.set("ui.theme", theme)
        elif hasattr(cm, "set_path"):
            cm.set_path("ui.theme", theme)
        else:
            data = cm.load()
            if not isinstance(data, dict):
                data = {}
            ui = data.setdefault("ui", {})
            if isinstance(ui, dict):
                ui["theme"] = theme
        if hasattr(cm, "save"):
            cm.save()
        return True
    except Exception:
        return False


def _wm_theme_values() -> list[str]:
    values = ["default", "dark", "light"]
    try:
        cm = globals().get("CONFIG_MANAGER")
        raw = cm.get("ui.available_themes", None) if cm is not None else None
        if isinstance(raw, (list, tuple)):
            out = [str(x).strip() for x in raw if str(x).strip()]
            if out:
                return out
    except Exception:
        pass
    return values


def _wm_short_path(path: str | None, max_len: int = 95) -> str:
    """Skróć długą ścieżkę do paska statusu bez zmiany samej wartości."""
    text = str(path or "").strip()
    if not text:
        return "BRAK"
    if len(text) <= max_len:
        return text
    return "…" + text[-max_len:]


def _wm_path_exists(path: str | None) -> bool:
    """Bezpiecznie sprawdź istnienie ścieżki."""
    try:
        return bool(path and os.path.exists(path))
    except Exception:
        return False


def _wm_runtime_paths_snapshot() -> dict:
    """Zwróć aktualne ścieżki runtime widoczne dla GUI.

    To jest tylko diagnostyka. Funkcja niczego nie ustawia i nie zmienia.
    """
    root_path = os.environ.get("WM_ROOT")
    data_root = os.environ.get("WM_DATA_ROOT")
    config_file = os.environ.get("WM_CONFIG_FILE")
    try:
        from core import root_paths as wm_root_paths
        if not root_path:
            root_path = str(wm_root_paths.get_root_anchor())
        if not data_root:
            data_root = str(wm_root_paths.get_data_root())
        if not config_file:
            config_file = str(wm_root_paths.path_config())
    except Exception:
        pass
    try:
        cm = globals().get("CONFIG_MANAGER")
        cfg = getattr(cm, "merged", None) if cm is not None else None
        if cfg:
            from config_manager import get_root, resolve_rel
            if not root_path:
                root_path = get_root(cfg)
            if not data_root:
                data_root = resolve_rel(cfg, "root")
            if not config_file and hasattr(cm, "config_path"):
                config_file = str(cm.config_path)
    except Exception:
        pass
    return {
        "root": os.path.normpath(root_path) if root_path else "",
        "data": os.path.normpath(data_root) if data_root else "",
        "config": os.path.normpath(config_file) if config_file else "",
    }


def _wm_build_root_status_text() -> tuple[str, bool]:
    """Zbuduj tekst paska ROOT/DATA/CONFIG.

    Zwraca:
        (tekst, czy_jest_ostrzezenie)
    """
    paths = _wm_runtime_paths_snapshot()
    root_ok = _wm_path_exists(paths.get("root"))
    data_ok = _wm_path_exists(paths.get("data"))
    config_ok = _wm_path_exists(paths.get("config"))
    warn = not (root_ok and data_ok and config_ok)
    prefix = "⚠ ROOT" if warn else "ROOT"
    text = (
        f"{prefix}: {_wm_short_path(paths.get('root'))} | "
        f"DATA: {_wm_short_path(paths.get('data'))} | "
        f"CONFIG: {_wm_short_path(paths.get('config'))}"
    )
    return text, warn


def wm_set_module_source(root, module_name: str, source_path: str | None = None) -> None:
    """Ustaw tekst 'Aktualnie' w górnym pasku z nazwą modułu i źródłem danych.

    Funkcja jest celowo odporna na brak etykiety, żeby moduły mogły ją wołać
    bez ryzyka wywalenia GUI.
    """
    try:
        var = getattr(root, "wm_current_source_var", None)
        if var is None:
            return
        module = str(module_name or "—").strip() or "—"
        if source_path:
            source_norm = os.path.normcase(os.path.abspath(str(source_path)))
            root_path = _wm_runtime_paths_snapshot().get("root") or ""
            root_norm = os.path.normcase(os.path.abspath(root_path)) if root_path else ""
            outside_root = bool(root_norm and not source_norm.startswith(root_norm))
            prefix = "⚠ " if outside_root else ""
            suffix = " | POZA ROOT!" if outside_root else ""
            var.set(
                f"{prefix}Aktualnie: {module} | czytam: "
                f"{_wm_short_path(source_path)}{suffix}"
            )
        else:
            var.set(f"Aktualnie: {module} | czytam: —")
    except Exception:
        pass


def _load_last_visit(login: str) -> datetime:
    """Odczytaj datę ostatniej wizyty z profilu użytkownika."""
    user = get_user(login) or {}
    ts = user.get("ostatnia_wizyta")
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _save_last_visit(login: str, dt: datetime) -> None:
    """Zapisz datę ostatniej wizyty w profilu użytkownika."""
    user = get_user(login) or {"login": login}
    user["ostatnia_wizyta"] = (
        dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    save_user(user)


def wm_get_logged_login(app) -> str | None:
    """Zwraca login aktualnie zalogowanego użytkownika."""
    candidates = [
        ("auth", "current_user", "login"),
        ("auth", "user", "login"),
        ("session", "user", "login"),
        ("session", "login"),
        ("current_user", "login"),
        ("logged_user", "login"),
        ("user_login",),
        ("active_login",),
        ("username",),
        ("_wm_login",),
        ("login",),
    ]
    for path in candidates:
        cur = app
        ok = True
        for attr in path:
            if not hasattr(cur, attr):
                ok = False
                break
            cur = getattr(cur, attr)
        if ok and isinstance(cur, str) and cur.strip():
            return cur.strip()
    active = ProfileService.ensure_active_user_or_none()
    if active:
        return str(active).strip()
    return None


def _active_login(self) -> str:
    """Zwraca aktualny login użytkownika na potrzeby nagłówka profilu."""
    return wm_get_logged_login(self) or "uzytkownik"


def _center_container(self):
    """Zwraca główny kontener na widoki (centralny panel)."""
    for attr in ("content", "main_content", "content_frame", "body"):
        if hasattr(self, attr):
            container = getattr(self, attr)
            if container is not None:
                return container
    return self


def open_profile_for_login(self, login: str) -> None:
    """Wstawia nowy widok profilu do centralnego kontenera i wymusza reload."""
    login = str(login or "").strip()
    if not login:
        messagebox.showerror("Profil", "Brak loginu zalogowanego użytkownika.")
        return
    if ProfileView is None:
        print("[ERROR][PROFILE] Brak klasy ProfileView – sprawdź gui_profile.py")
        try:
            container = _center_container(self)
        except Exception:
            return
        if container is self:
            return
        try:
            for widget in container.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
            ttk.Label(
                container,
                text="Widok profilu jest niedostępny.",
                foreground="#e53935",
            ).pack(pady=20)
        except Exception:
            pass
        return
    try:
        container = _center_container(self)
        if container is self:
            raise RuntimeError("Nie znaleziono kontenera centralnego dla profilu")
        try:
            for widget in container.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        view = ProfileView(container, login=login)
        try:
            if hasattr(view, "forced_login"):
                view.forced_login = login
            if hasattr(view, "load_by_login"):
                view.load_by_login(login)
            elif hasattr(view, "refresh"):
                view.refresh()
        except Exception as exc:
            log_akcja(f"[WM-DBG][PROFILE] load_by_login failed: {exc}")
        try:
            if hasattr(self, "_show"):
                self._show(view)
            else:
                view.pack(fill="both", expand=True)
        except Exception:
            view.pack(fill="both", expand=True)

        print(f"[WM-DBG][PROFILE] Załadowano nowy widok profilu dla: {login}")
    except Exception as exc:
        print(f"[ERROR][PROFILE] Nie udało się otworzyć widoku profilu: {exc}")


def open_profile_for_logged_user(self) -> None:
    login = wm_get_logged_login(self)
    print(f"[WM-DBG][PROFIL] klik Profil -> login_sesji={login}")
    if not login:
        messagebox.showerror("Profil", "Brak loginu zalogowanego użytkownika.")
        return
    open_profile_for_login(self, login)


try:
    from logger import log_akcja
except Exception:
    def log_akcja(msg: str):
        print(f"[LOG] {msg}")

# --- IMPORT DYSPozycji (na bazie panelu zleceń, adapter zgodności) ---
try:
    # oryginalna funkcja z gui_zlecenia: panel_zlecenia(parent, root=None, app=None, notebook=None)
    from gui_zlecenia import panel_zlecenia as _panel_zl_src

    def panel_zlecenia(root, frame, login=None, rola=None):
        """Adapter: zachowuje sygnaturę (root, frame, ...),
        a wewnątrz woła panel_zlecenia(parent, root, None, None) i pakuje wynik do frame.
        """
        # wyczyść miejsce docelowe
        clear_frame(frame)
        try:
            setattr(root, "_wm_login", login)
            setattr(root, "_wm_rola", rola)
        except Exception:
            pass
        try:
            tab = _panel_zl_src(frame, root, None, None)
        except TypeError:
            # fallback dla starszych wersji przyjmujących samo parent
            tab = _panel_zl_src(frame)
        # jeżeli panel zwraca ramkę – spakuj ją do content
        if isinstance(tab, (tk.Widget, ttk.Frame)):
            try:
                tab.pack(fill="both", expand=True)
            except Exception:
                pass
        else:
            # awaryjnie pokaż etykietę, żeby nie było pusto
            ttk.Label(frame, text="Panel Dyspozycji – załadowano").pack(pady=12)
except Exception:
    def panel_zlecenia(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel Dyspozycji (fallback) – błąd importu gui_zlecenia").pack(pady=20)

# --- IMPORT NARZĘDZI Z CZYTELNYM TRACEBACKIEM ---
try:
    from gui_narzedzia import panel_narzedzia as _panel_narzedzia_stable
    _PANEL_NARZ_STABLE_ERR = None
except Exception:
    _PANEL_NARZ_STABLE_ERR = traceback.format_exc()
    _panel_narzedzia_stable = None  # type: ignore

try:
    from gui_narzedzia_v2_beta import panel_narzedzia as _panel_narzedzia_beta
    _PANEL_NARZ_BETA_ERR = None
except Exception:
    _PANEL_NARZ_BETA_ERR = traceback.format_exc()
    _panel_narzedzia_beta = None  # type: ignore


def _tools_panel_variant() -> str:
    cm = globals().get("CONFIG_MANAGER")
    choice = "stable"
    if cm is not None:
        try:
            value = cm.get("tools.panel_variant", "stable")
            if isinstance(value, str) and value.strip():
                choice = value.strip().lower()
        except Exception:
            choice = "stable"
    return "beta" if choice == "beta" else "stable"


def panel_narzedzia(root, frame, login=None, rola=None):
    variant = _tools_panel_variant()
    if variant == "beta" and _panel_narzedzia_beta is not None:
        try:
            return _panel_narzedzia_beta(root, frame, login, rola)
        except Exception:
            traceback.print_exc()
    if _panel_narzedzia_stable is not None:
        return _panel_narzedzia_stable(root, frame, login, rola)

    clear_frame(frame)
    messages = []
    if variant == "beta" and _PANEL_NARZ_BETA_ERR:
        messages.append("Błąd importu gui_narzedzia_v2_beta.py:\n" + _PANEL_NARZ_BETA_ERR)
    if _PANEL_NARZ_STABLE_ERR:
        messages.append("Błąd importu gui_narzedzia.py:\n" + _PANEL_NARZ_STABLE_ERR)
    if not messages:
        messages.append("Panel narzędzi jest niedostępny.")
    tk.Label(
        frame,
        text="\n\n".join(messages),
        fg="#e53935",
        justify="left",
        anchor="w",
    ).pack(fill="x", padx=12, pady=12)

try:
    from gui_maszyny import panel_maszyny
except Exception:
    def panel_maszyny(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel maszyn").pack(pady=20)

try:
    from gui_uzytkownicy import panel_uzytkownicy
except Exception:
    def panel_uzytkownicy(root, frame, login=None, rola=None):
        clear_frame(frame)
        ttk.Label(frame, text="Panel użytkowników").pack(pady=20)

# --- IMPORT MAGAZYNU ---
from gui_magazyn import open_panel_magazyn

try:
    from panel_jarvis import JarvisPanel as _JarvisPanel
    _JARVIS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - diagnostyka GUI
    _JarvisPanel = None
    _JARVIS_IMPORT_ERROR = exc


def panel_magazyn(root, frame, login=None, rola=None):
    """Adapter do ``open_panel_magazyn`` osadzający widok w kontenerze."""
    open_panel_magazyn(root, container=frame)


def panel_jarvis(root, frame, login=None, rola=None):
    """Wstaw panel Jarvisa do głównego kontenera."""

    clear_frame(frame)

    if _JarvisPanel is None:
        ttk.Label(
            frame,
            text=(
                "Panel Jarvis jest niedostępny."
                if _JARVIS_IMPORT_ERROR is None
                else f"Błąd importu panelu Jarvis: {_JARVIS_IMPORT_ERROR}"
            ),
            foreground="#e53935",
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=16, pady=20)
        return

    panel = _JarvisPanel(frame)
    panel.pack(fill="both", expand=True)




def panel_planowanie(root, frame, login=None, rola=None):
    if gui_planowanie and hasattr(gui_planowanie, "panel_planowanie"):
        return gui_planowanie.panel_planowanie(root, frame, login, rola)
    ttk.Label(frame, text="Panel Planowanie (fallback) – błąd importu gui_planowanie").pack(pady=20)

def panel_chat(root, frame, login=None, rola=None):
    """Prosty chat (ala messenger) – lokalny MVP.

    FIX: zabezpieczenie timera after() przed TclError gdy panel zostanie zamknięty
    (invalid command name ...listbox).
    """
    clear_frame(frame)

    if append_message is None or read_messages is None:
        # chat_store nie jest dostępny – pokazujemy informację zamiast crasha
        info = ttk.Label(
            frame,
            text="Chat jest niedostępny: brak chat_store.py (lub błąd importu).",
        )
        info.pack(padx=12, pady=12, anchor="w")
        return

    frm_top = ttk.Frame(frame)
    frm_top.pack(fill="x", padx=10, pady=(10, 0))
    ttk.Label(frm_top, text="Chat (lokalny) – użytkownik: " + (login or "---")).pack(
        side="left"
    )
    unread_var = tk.StringVar(value="")
    ttk.Label(frm_top, textvariable=unread_var).pack(side="right")

    # Filtry (MVP)
    only_bryg = tk.BooleanVar(value=False)
    only_me = tk.BooleanVar(value=False)
    frm_filters = ttk.Frame(frame)
    frm_filters.pack(fill="x", padx=10, pady=(0, 6))
    ttk.Checkbutton(
        frm_filters,
        text="Tylko brygadzista",
        variable=only_bryg,
        command=lambda: _reload(False),
    ).pack(side="left")
    ttk.Checkbutton(
        frm_filters,
        text="Tylko moja zmiana",
        variable=only_me,
        command=lambda: _reload(False),
    ).pack(side="left", padx=(12, 0))

    frm_mid = ttk.Frame(frame)
    frm_mid.pack(fill="both", expand=True, padx=10, pady=10)

    lst = tk.Listbox(frm_mid, height=18)
    scr = ttk.Scrollbar(frm_mid, orient="vertical", command=lst.yview)
    lst.configure(yscrollcommand=scr.set)
    lst.pack(side="left", fill="both", expand=True)
    scr.pack(side="right", fill="y")

    frm_bottom = ttk.Frame(frame)
    frm_bottom.pack(fill="x", padx=10, pady=(0, 10))

    entry = ttk.Entry(frm_bottom)
    entry.pack(side="left", fill="x", expand=True)

    btn_send = ttk.Button(frm_bottom, text="Wyślij")
    btn_send.pack(side="left", padx=(8, 0))

    def _fmt(m: dict) -> str:
        ts = str(m.get("ts", "") or "")
        frm = str(m.get("from", "") or "")
        txt = str(m.get("text", "") or "")
        if len(txt) > 500:
            txt = txt[:500] + "…"
        return f"[{ts}] {frm}: {txt}"

    def _reload(mark_as_read: bool = False):
        # GUARD: panel został zamknięty / widżety zniszczone (po zmianie modułu)
        try:
            if not frame.winfo_exists():
                return
            if not lst.winfo_exists():
                return
        except Exception:
            return

        try:
            lst.delete(0, "end")
        except tk.TclError:
            return

        msgs = read_messages(limit=300)

        # Zastosuj filtry
        if only_me.get() and login:
            login_n = login.strip().lower()
            msgs = [
                m
                for m in msgs
                if str(m.get("from", "") or "").strip().lower() == login_n
            ]

        if only_bryg.get():
            msgs = [
                m
                for m in msgs
                if str(m.get("role", "") or "").strip().lower() == "brygadzista"
            ]
        for m in msgs:
            try:
                lst.insert("end", _fmt(m))
            except tk.TclError:
                return

        try:
            lst.yview_moveto(1.0)
        except Exception:
            pass

        if login and get_unread_count and mark_read:
            try:
                unread = get_unread_count(login)
                unread_var.set(f"Nieprzeczytane: {unread}" if unread else "")
                if mark_as_read:
                    mark_read(login)
                    unread_var.set("")
            except Exception:
                pass

    def _send(_event=None):
        txt = entry.get().strip()
        if not txt:
            return
        try:
            append_message(login or "anon", txt, role=(rola or ""))
        except Exception:
            pass
        entry.delete(0, "end")
        _reload(mark_as_read=True)

    btn_send.configure(command=_send)
    entry.bind("<Return>", _send)

    _reload(mark_as_read=True)

    # auto-refresh co 3 sekundy
    job = {"id": None}

    def _tick():
        # GUARD: jeśli panel/Lista nie istnieje, kończymy i nie planujemy kolejnego ticka
        try:
            if not frame.winfo_exists() or not lst.winfo_exists():
                job["id"] = None
                return
        except Exception:
            job["id"] = None
            return

        try:
            _reload(mark_as_read=False)
        except tk.TclError:
            job["id"] = None
            return

        job["id"] = root.after(3000, _tick)

    job["id"] = root.after(3000, _tick)

    def _on_destroy(_event=None):
        _id = job.get("id")
        if _id:
            try:
                root.after_cancel(_id)
            except Exception:
                pass
        job["id"] = None

    frame.bind("<Destroy>", _on_destroy, add=True)


# ---------- Główny panel ----------

def uruchom_panel(root, login, rola):
    if not ensure_theme_applied(root):
        apply_theme(root)
    root.title(
        f"Warsztat Menager v{APP_VERSION} - zalogowano jako {login} ({rola})"
    )
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        try:
            root.state("zoomed")
        except Exception:
            pass
    try:
        root.bind("<Escape>", lambda _event: root.attributes("-fullscreen", False))
        root.bind("<F11>", lambda _event: root.attributes("-fullscreen", not bool(root.attributes("-fullscreen"))))
    except Exception:
        pass
    clear_frame(root)
    if _register_notification_root is not None:
        try:
            _register_notification_root(root)
        except Exception:
            pass
    setattr(root, "current_shift", _current_shift_label(datetime.now()))

    last_visit = _load_last_visit(login)
    profile = get_user(login) or {}
    modules_disabled = set()
    if isinstance(profile, dict):
        modules_disabled = set(profile.get("modules_disabled", []))
    disabled_modules: set[str] = set()
    markers: list[tk.Widget] = []
    def _clear_markers() -> None:
        nonlocal last_visit
        for dot in markers:
            try:
                dot.destroy()
            except Exception:
                pass
        markers.clear()
        last_visit = datetime.now(timezone.utc)
        _save_last_visit(login, last_visit)

    def _maybe_mark_button(widget: tk.Widget) -> None:
        lm = getattr(widget, "last_modified", None)
        if isinstance(lm, datetime) and lm > last_visit:
            try:
                bg = widget.cget("background")
            except tk.TclError:
                try:
                    bg = widget.master.cget("bg")
                except Exception:
                    bg = None
            dot_kwargs = {"text": "\u25CF", "fg": "#e53935"}
            if bg is not None:
                dot_kwargs["bg"] = bg
            dot = tk.Label(widget, **dot_kwargs)
            dot.place(relx=1, x=-4, y=4, anchor="ne")
            markers.append(dot)

    def _is_guest_role(role_value) -> bool:
        return str(role_value or "").strip().lower() in {"guest", "gość", "gosc", ""}

    is_guest = _is_guest_role(rola)
    normalized_role = normalize_role_name(rola)

    def _show_access_denied(module_label: str) -> None:
        messagebox.showwarning(
            "Brak dostępu",
            f"Moduł '{module_label}' jest wyłączony dla Twojej rangi albo dla Twojego konta.",
        )

    side  = ttk.Frame(root, style="WM.Side.TFrame", width=220); side.pack(side="left", fill="y")
    main  = ttk.Frame(root, style="WM.TFrame");               main.pack(side="right", fill="both", expand=True)

    header  = ttk.Frame(main, style="WM.TFrame");      header.pack(fill="x", padx=12, pady=(10,6))
    ttk.Label(header, text="Panel główny", style="WM.H1.TLabel").pack(side="left")
    # NOWE: czytelny login/rola po prawej stronie nagłówka
    session_wrap = ttk.Frame(header, style="WM.TFrame")
    session_wrap.pack(side="right")
    session_var = tk.StringVar(
        master=root,
        value="Niezalogowany / Gość" if is_guest else f"{login} ({rola})",
    )
    ttk.Label(session_wrap, textvariable=session_var, style="WM.Muted.TLabel").pack(
        side="left", padx=(0, 8)
    )
    ttk.Label(session_wrap, text="Motyw:", style="WM.Muted.TLabel").pack(
        side="left", padx=(8, 4)
    )
    theme_var = tk.StringVar(master=root, value=_wm_get_current_theme())
    theme_box = ttk.Combobox(
        session_wrap,
        textvariable=theme_var,
        values=_wm_theme_values(),
        state="readonly",
        width=12,
    )
    theme_box.pack(side="left", padx=(0, 8))

    def _on_quick_theme_change(_event=None):
        selected = theme_var.get().strip() or "default"
        saved = _wm_save_theme(selected)
        try:
            apply_theme(root)
        except Exception:
            pass
        try:
            ensure_theme_applied(root)
        except Exception:
            pass
        try:
            root.event_generate("<<ThemeChanged>>", when="tail")
        except Exception:
            pass
        if not saved:
            try:
                messagebox.showwarning(
                    "Motyw",
                    "Motyw został zastosowany tylko tymczasowo. "
                    "Nie udało się zapisać configu.",
                    parent=root,
                )
            except Exception:
                pass

    theme_box.bind("<<ComboboxSelected>>", _on_quick_theme_change)

    root_status_text, root_status_warn = _wm_build_root_status_text()
    root_status_var = tk.StringVar(master=root, value=root_status_text)
    root_status_label = ttk.Label(
        main, textvariable=root_status_var, style="WM.Muted.TLabel"
    )
    root_status_label.pack(fill="x", padx=12, pady=(0, 2))
    if root_status_warn:
        try:
            root_status_label.configure(foreground="#e53935")
        except Exception:
            pass
    setattr(root, "wm_root_status_var", root_status_var)

    current_action_var = tk.StringVar(
        master=root,
        value="Aktualnie: Panel główny | czytam: —",
    )
    current_action_label = ttk.Label(
        main, textvariable=current_action_var, style="WM.Muted.TLabel"
    )
    current_action_label.pack(fill="x", padx=12, pady=(0, 6))
    setattr(root, "wm_current_source_var", current_action_var)

    footer  = ttk.Frame(main, style="WM.TFrame");      footer.pack(side="bottom", fill="x", padx=12, pady=(6, 10))
    footer_btns = ttk.Frame(footer, style="WM.TFrame"); footer_btns.pack(side="right")

    content = ttk.Frame(main, style="WM.Card.TFrame"); content.pack(side="top", fill="both", expand=True, padx=12, pady=6)
    setattr(root, "content", content)
    setattr(root, "main_content", content)
    setattr(root, "active_login", login)
    setattr(root, "current_user", login)
    setattr(root, "username", login)

    # prawa część: stałe przyciski
    def _logout():
        """Wylogowanie do trybu gościa."""
        try:
            from presence import heartbeat
            heartbeat(login, rola, logout=True)
        except Exception:
            pass
        uruchom_panel(root, login="Gość", rola="guest")

    def _open_login_popup():
        try:
            import gui_logowanie
            gui_logowanie.open_login_popup(
                root,
                on_success=lambda login_new, rola_new, extra=None: uruchom_panel(
                    root, login_new, rola_new
                ),
            )
        except Exception as exc:
            messagebox.showerror("Logowanie", f"Nie można otworzyć okna logowania: {exc}")
    changelog_win = {"ref": None}
    btn_changelog = None

    def _has_unseen_changelog(last_seen: str | None) -> bool:
        try:
            seen_dt = datetime.fromisoformat(last_seen) if last_seen else datetime.min
        except ValueError:
            seen_dt = datetime.min
        try:
            with open("CHANGELOG.md", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("##"):
                        m = re.search(r"-\s*(\d{4}-\d{2}-\d{2})", line)
                        if m:
                            try:
                                dt = datetime.fromisoformat(m.group(1))
                            except ValueError:
                                dt = None
                            if dt and dt > seen_dt:
                                return True
        except Exception:
            return False
        return False

    def _close_changelog(_event=None):
        win = changelog_win.get("ref")
        if win is not None and win.winfo_exists():
            try:
                win.destroy()
            except Exception:
                pass
        changelog_win["ref"] = None
        if btn_changelog and btn_changelog.winfo_exists():
            btn_changelog.config(text="Pokaż zmiany")
        _clear_markers()
        try:
            CONFIG_MANAGER.set(
                "changelog.last_viewed",
                datetime.now().isoformat(timespec="seconds"),
                who=login,
            )
            CONFIG_MANAGER.save_all()
        except Exception:
            pass

    def _toggle_changelog(auto: bool = False):
        win = changelog_win.get("ref")
        if win is not None and win.winfo_exists():
            _close_changelog()
            return
        last_seen = None
        try:
            last_seen = CONFIG_MANAGER.get("changelog.last_viewed")
        except Exception:
            last_seen = None
        if auto and not _has_unseen_changelog(last_seen):
            return
        try:
            win = gui_changelog.show_changelog(
                master=root, last_seen=last_seen
            )
            changelog_win["ref"] = win
            if btn_changelog and btn_changelog.winfo_exists():
                btn_changelog.config(text="Ukryj zmiany")
            win.protocol("WM_DELETE_WINDOW", _close_changelog)
            for child in win.winfo_children():
                if isinstance(child, tk.Button) and child.cget("text") == "Zamknij":
                    child.config(command=_close_changelog)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć changeloga: {e}")

    ttk.Button(
        footer_btns, text="Zamknij program", command=root.quit, style="WM.Side.TButton"
    ).pack(side="right")
    btn_changelog = ttk.Button(
        footer_btns,
        text="Pokaż zmiany",
        command=_toggle_changelog,
        style="WM.Side.TButton",
    )
    btn_changelog.last_modified = datetime(2025, 9, 1, tzinfo=timezone.utc)
    btn_changelog.pack(side="right", padx=(6, 0))
    _maybe_mark_button(btn_changelog)
    root.after(100, lambda: _toggle_changelog(auto=True))
    session_btn_text = "Zaloguj" if is_guest else "Wyloguj"
    session_btn_cmd = _open_login_popup if is_guest else _logout
    ttk.Button(
        session_wrap, text=session_btn_text, command=session_btn_cmd, style="WM.Side.TButton"
    ).pack(side="left")
    # --- licznik automatycznego wylogowania ---
    try:
        cm = globals().get("CONFIG_MANAGER")
        _logout_min = int(cm.get("auth.session_timeout_min", 30)) if cm else 30
    except Exception:
        _logout_min = 30
    _logout_total = max(0, _logout_min * 60)
    _logout_deadline = datetime.now() + timedelta(seconds=_logout_total)
    logout_job = {"id": None}
    # label pokazujący czas pozostały do automatycznego wylogowania
    def _logout_tick():
        if not logout_label.winfo_exists():
            logout_job["id"] = None
            return
        remaining = int((_logout_deadline - datetime.now()).total_seconds())
        if remaining <= 0:
            logout_label.config(text="Automatyczne wylogowanie za: 0 min")
            logout_job["id"] = None
            _logout()
            return
        minutes = max(0, remaining // 60)
        logout_label.config(
            text=f"Automatyczne wylogowanie za: {minutes} min"
        )
        logout_job["id"] = root.after(1000, _logout_tick)

    def _on_logout_destroy(_e=None):
        if logout_job["id"]:
            try:
                root.after_cancel(logout_job["id"])
            except Exception:
                pass
            logout_job["id"] = None

    def _reset_logout_timer(_event=None):
        nonlocal _logout_deadline
        try:
            cm = globals().get("CONFIG_MANAGER")
            new_min = int(cm.get("auth.session_timeout_min", 30)) if cm else 30
        except Exception:
            new_min = 30
        total = max(0, new_min * 60)
        _logout_deadline = datetime.now() + timedelta(seconds=total)
        if logout_job["id"]:
            try:
                root.after_cancel(logout_job["id"])
            except Exception:
                pass
            logout_job["id"] = None
        _logout_tick()
        try:
            from start import restart_user_activity_monitor
            restart_user_activity_monitor(total)
        except Exception:
            pass

    btn_reset = ttk.Button(
        footer_btns,
        text="Zresetuj licznik",
        command=_reset_logout_timer,
        style="WM.Side.TButton",
    )
    btn_reset.pack(side="right", padx=(6, 0))
    logout_label = ttk.Label(footer_btns, text="", style="WM.Muted.TLabel")
    logout_label.pack(side="right", padx=(0, 6))

    _logout_tick()
    logout_label.bind("<Destroy>", _on_logout_destroy)
    root.bind("<<AuthTimeoutChanged>>", _reset_logout_timer, add="+")

    # nawigacja
    def wyczysc_content():
        clear_frame(content)

    def otworz_panel(funkcja, nazwa):
        flow = None
        if funkcja is panel_narzedzia:
            flow = PerfFlow("TOOLS_OPEN")
            flow.mark("clicked")
        wyczysc_content(); log_akcja(f"Kliknięto: {nazwa}")
        current_action_var.set(f"Aktualnie: {nazwa}")
        try:
            if flow:
                with perf_span("TOOLS_OPEN:create_window"):
                    funkcja(root, content, login, rola)
                flow.mark("window_created")
                flow.mark("initial_load_called")
            else:
                funkcja(root, content, login, rola)
        except Exception as e:
            log_akcja(f"Błąd przy otwieraniu panelu {nazwa}: {e}")
            ttk.Label(content, text=f"Błąd otwierania panelu: {e}", foreground="#e53935").pack(pady=20)
        finally:
            if flow:
                flow.end()

    # --- role helpers + quick open profile ---
    def _is_admin_role(r):
        admin_like = ADMIN_ROLE_NAMES | {"kierownik", "brygadzista", "lider"}
        return str(r).lower() in admin_like

    def _open_profile_entry():
        setattr(root, "content", content)
        setattr(root, "main_content", content)
        setattr(root, "active_login", login)
        setattr(root, "current_user", login)
        setattr(root, "username", login)
        current_action_var.set("Aktualnie: Profil")
        try:
            open_profile_for_logged_user(root)
        except Exception as e:
            log_akcja(f"Błąd otwierania panelu profilu: {e}")
            clear_frame(content)
            ttk.Label(
                content,
                text=f"Błąd otwierania panelu: {e}",
                foreground="#e53935",
            ).pack(pady=20)

    def _open_feedback():
        current_action_var.set("Aktualnie: Wyślij opinię")
        win = tk.Toplevel(root)
        win.title("Wyślij opinię")
        ttk.Label(win, text="Twoja opinia:").pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        txt = tk.Text(win, width=60, height=10)
        txt.pack(padx=10, pady=6)

        def _submit():
            message = txt.get("1.0", "end").strip()
            if not message:
                messagebox.showwarning("Brak treści", "Wpisz treść opinii.")
                return
            payload = {
                "login": login,
                "rola": rola,
                "ts": datetime.now().isoformat(),
                "message": message,
            }
            sent = False
            try:
                import requests

                cm = globals().get("CONFIG_MANAGER")
                url = cm.get("feedback.url", "").strip() if cm else ""
                if url:
                    resp = requests.post(url, json=payload, timeout=5)
                    resp.raise_for_status()
                    sent = True
            except Exception:
                sent = False
            if not sent:
                try:
                    data_root = CONFIG_MANAGER.path_data()
                except Exception:
                    data_root = "data"
                os.makedirs(data_root, exist_ok=True)
                path = os.path.join(data_root, "opinie.json")
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    data = []
                data.append(payload)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Dziękujemy", "Twoja opinia została przesłana."
            )
            win.destroy()

        ttk.Button(win, text="Wyślij", command=_submit).pack(pady=(0, 10))

    def _load_mag_alerts():
        """Lista pozycji magazynowych poniżej progu."""
        try:
            with open("data/magazyn/surowce.json", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return []
        out = []
        if isinstance(data, dict):
            items = ((k, v) for k, v in data.items() if isinstance(v, dict))
        else:
            items = (
                (rec.get("kod"), rec)
                for rec in data
                if isinstance(rec, dict)
            )
        for kod, rec in items:
            if not kod:
                continue
            try:
                stan = float(rec.get("stan", 0))
                prog = float(rec.get("prog_alertu", 0))
            except Exception:
                continue
            if stan <= prog:
                nm = rec.get("nazwa", "")
                out.append(f"{kod} ({nm})")
        return out

    def _load_jarvis_alerts(limit: int = 5):
        try:
            from core import jarvis_engine as _jarvis_engine
        except Exception:
            return []

        get_notifications = getattr(_jarvis_engine, "get_notifications", None)
        get_status = getattr(_jarvis_engine, "get_status", None)

        entries: list[tuple[str, str]] = []

        status_snapshot = {}
        if callable(get_status):
            try:
                status_snapshot = get_status()
            except Exception:
                status_snapshot = {}
        if isinstance(status_snapshot, dict) and status_snapshot.get("offline"):
            reason = str(status_snapshot.get("offline_reason") or "").strip()
            if reason:
                entries.append(("warning", reason))

        if callable(get_notifications):
            try:
                raw_notifications = list(get_notifications())
            except Exception:
                raw_notifications = []
            for item in reversed(raw_notifications):
                if not isinstance(item, dict):
                    continue
                message = str(item.get("message") or "").strip()
                if not message:
                    continue
                try:
                    raw_level = int(item.get("level", 0))
                except Exception:
                    raw_level = 0
                if raw_level >= 4:
                    level_name = "error"
                elif raw_level >= 3:
                    level_name = "warning"
                else:
                    level_name = "info"
                entries.append((level_name, message))
                if len(entries) >= limit:
                    break

        return entries

    # przyciski boczne
    start_panel = None
    start_name = ""
    admin_roles = ADMIN_ROLE_NAMES | {"kierownik", "lider"}
    is_admin = str(rola).strip().lower() in admin_roles

    def _format_modules(modules) -> str:
        items = list(modules)
        return "[" + ",".join(f"'{item}'" for item in items) + "]"

    sidebar_entries = []
    module_shortcuts: dict[str, tuple] = {}
    for raw_key, raw_label in SIDEBAR_MODULES_EXT:
        norm_key = normalize_module_name(raw_key)
        if not norm_key:
            continue
        if norm_key == "uzytkownicy":
            # Zakładka "Użytkownicy" WYŁĄCZONA (decyzja projektowa)
            continue
        sidebar_entries.append((norm_key, raw_label))

    # Rejestr dla badge chatu (minimalnie, bez przeróbek architektury)
    try:
        _chat_badge_btn  # noqa: B018
    except Exception:
        _chat_badge_btn = None  # type: ignore

    def _build_sidebar(initial: bool = False) -> None:
        nonlocal profile, disabled_modules, start_panel, start_name, modules_disabled
        clear_frame(side)
        profile = get_user(login) or {}
        modules_disabled = set()
        if isinstance(profile, dict):
            modules_disabled = set(profile.get("modules_disabled", []))

        try:
            manifest = zaladuj_manifest(CONFIG_MANAGER)
        except Exception:
            manifest = None

        def _module_is_active(module_key: str) -> bool:
            try:
                return module_active(module_key, manifest=manifest, cfg=CONFIG_MANAGER)
            except Exception:
                return True

        module_shortcuts.clear()

        raw_disabled = []
        profile_disabled = profile.get("disabled_modules")
        if isinstance(profile_disabled, (list, tuple, set)):
            raw_disabled.extend(profile_disabled)
        raw_disabled.extend(modules_disabled)
        raw_disabled.extend(get_disabled_modules_for(login))

        normalized_disabled = []
        seen_disabled = set()
        for module in raw_disabled:
            normalized = normalize_module_name(module)
            if not normalized or normalized in seen_disabled:
                continue
            normalized_disabled.append(normalized)
            seen_disabled.add(normalized)

        disabled_modules = set(normalized_disabled)

        all_sidebar_keys = [key for key, _label in sidebar_entries]
        allowed_modules_list = [
            module
            for module in get_effective_allowed_modules(login, all_sidebar_keys)
            if module not in disabled_modules
        ]
        allowed_modules = set(allowed_modules_list)

        log_akcja(
            f"[PANEL][ACCESS] disabled_modules(login={login})="
            f"{_format_modules(normalized_disabled)}"
        )

        start_panel = None
        start_name = ""
        shown_modules: list[str] = []

        for key, label in sidebar_entries:
            pad = (12, 6) if start_panel is None else 6
            def _locked_command(module_label=label):
                return lambda: _show_access_denied(module_label)

            def _button_text(module_label: str, enabled_flag: bool) -> str:
                return module_label if enabled_flag else f"{module_label}  🔒"

            def _button_command(panel_func, module_label: str, enabled_flag: bool):
                if enabled_flag:
                    return lambda f=panel_func, l=module_label: otworz_panel(f, l)
                return _locked_command(module_label)

            module_allowed = is_module_allowed_for_user(login, normalized_role, key)
            if key == "jarvis":
                module_allowed = module_allowed and can_access_jarvis(profile)
            enabled = (
                _module_is_active(key)
                and module_allowed
            )

            button_label = "Dyspozycje" if key == "zlecenia" else label
            if key == "zlecenia":
                btn = ttk.Button(
                    side,
                    text=_button_text("Dyspozycje", enabled),
                    style="WM.Side.TButton",
                    command=_button_command(panel_zlecenia, "Dyspozycje", enabled),
                    state="normal",
                )
                btn.last_modified = datetime(2025, 8, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    if start_panel is None:
                        start_panel = panel_zlecenia
                        start_name = "Dyspozycje (start)"
            elif key == "narzedzia":
                btn = ttk.Button(
                    side,
                    text=_button_text(button_label, enabled),
                    style="WM.Side.TButton",
                    command=_button_command(panel_narzedzia, label, enabled),
                    state="normal",
                )
                btn.last_modified = datetime(2025, 7, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    module_shortcuts["narzedzia"] = (panel_narzedzia, label)
                    if start_panel is None:
                        start_panel = panel_narzedzia
                        start_name = f"{label} (start)"
            else:
                panel_func = {
                    "maszyny": panel_maszyny,
                    "magazyn": panel_magazyn,
                    "planowanie": panel_planowanie,
                    "jarvis": panel_jarvis,
                    "uzytkownicy": panel_uzytkownicy,
                    "ustawienia": panel_ustawien,
                    "profile": lambda r, f, login=login, rola=rola: open_profile_for_logged_user(root),
                    "chat": panel_chat,
                }.get(key)
                if panel_func is not None:
                    btn = ttk.Button(
                        side,
                        text=_button_text(button_label, enabled),
                        command=_button_command(panel_func, button_label, enabled),
                        style="WM.Side.TButton",
                        state="normal",
                    )
                    btn.pack(padx=10, pady=pad, fill="x")
                    if enabled:
                        _maybe_mark_button(btn)
                    continue
            if key == "maszyny":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_maszyny, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 6, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    module_shortcuts["maszyny"] = (panel_maszyny, label)
                    if start_panel is None:
                        start_panel = panel_maszyny
                        start_name = f"{label} (start)"
            elif key == "planowanie":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_planowanie, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2026, 5, 12, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    module_shortcuts["planowanie"] = (panel_planowanie, label)
                    if start_panel is None:
                        start_panel = panel_planowanie
                        start_name = f"{label} (start)"
            elif key == "magazyn":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_magazyn, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 5, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    if start_panel is None:
                        start_panel = panel_magazyn
                        start_name = f"{label} (start)"
            elif key == "chat":
                btn = ttk.Button(
                    side,
                    text=button_label,  # badge updater może podmienić na "Chat (N)"
                    command=lambda f=panel_chat, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 12, 29, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)

                # zapamiętaj przycisk do aktualizacji badge
                _chat_badge_btn = btn  # type: ignore

                # badge co 5 sekund (tylko jeśli mamy login + get_unread_count)
                if enabled and get_unread_count and root:
                    try:
                        _chat_badge_job  # noqa: B018
                    except Exception:
                        _chat_badge_job = {"id": None}  # type: ignore

                    def _chat_badge_tick():
                        # jeśli UI zniknęło -> kończymy
                        try:
                            if not side.winfo_exists():
                                _chat_badge_job["id"] = None  # type: ignore
                                return
                            if _chat_badge_btn is None:
                                _chat_badge_job["id"] = None  # type: ignore
                                return
                            if not _chat_badge_btn.winfo_exists():  # type: ignore[union-attr]
                                _chat_badge_job["id"] = None  # type: ignore
                                return
                        except Exception:
                            _chat_badge_job["id"] = None  # type: ignore
                            return

                        # login aktywnego profilu
                        try:
                            active_login = (
                                profile.get("login") or profile.get("nazwa") or ""
                            ).strip()
                        except Exception:
                            active_login = ""

                        try:
                            n = get_unread_count(active_login) if active_login else 0
                        except Exception:
                            n = 0

                        try:
                            if n > 0:
                                _chat_badge_btn.configure(  # type: ignore
                                    text=f"{button_label} ({n})"
                                )
                            else:
                                _chat_badge_btn.configure(text=button_label)  # type: ignore
                        except TclError:
                            _chat_badge_job["id"] = None  # type: ignore
                            return

                        _chat_badge_job["id"] = root.after(  # type: ignore
                            5000, _chat_badge_tick
                        )

                    if _chat_badge_job["id"] is None:  # type: ignore
                        _chat_badge_job["id"] = root.after(  # type: ignore
                            1000, _chat_badge_tick
                        )
            elif key == "jarvis":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_jarvis, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 10, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    if start_panel is None:
                        start_panel = panel_jarvis
                        start_name = f"{label} (start)"
            elif key == "feedback":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=_open_feedback,
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 3, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
            elif key == "ustawienia":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_ustawien, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 1, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    if start_panel is None:
                        start_panel = panel_ustawien
                        start_name = f"{label} (start)"
            elif key == "profile":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=_open_profile_entry,
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 1, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    if start_panel is None:
                        start_panel = lambda r, f, l, ro: _open_profile_entry()
                        start_name = f"{label} (start)"
            elif key == "uzytkownicy":
                btn = ttk.Button(
                    side,
                    text=button_label,
                    command=lambda f=panel_uzytkownicy, l=label: otworz_panel(f, l),
                    style="WM.Side.TButton",
                    state="normal" if enabled else "disabled",
                )
                btn.last_modified = datetime(2025, 4, 1, tzinfo=timezone.utc)
                btn.pack(padx=10, pady=pad, fill="x")
                if enabled:
                    _maybe_mark_button(btn)
                    module_shortcuts["uzytkownicy"] = (panel_uzytkownicy, label)
                    if start_panel is None:
                        start_panel = panel_uzytkownicy
                        start_name = "Dyspozycje (start)"

            shown_modules.append(key)

        hidden_modules = [module for module in all_sidebar_keys if module not in shown_modules]
        log_akcja(
            f"[PANEL][ACCESS] login={login} shown={_format_modules(shown_modules)} "
            f"hidden={_format_modules(hidden_modules)}"
        )

        alerts = _load_mag_alerts() if "magazyn" not in disabled_modules else []
        if alerts:
            frm_alert = ttk.Frame(side, style="WM.Card.TFrame")
            frm_alert.pack(padx=10, pady=6, fill="x")
            ttk.Label(
                frm_alert, text="Alerty magazynowe", style="WM.Card.TLabel"
            ).pack(anchor="w", padx=8, pady=(6, 0))
            for a in alerts:
                ttk.Label(frm_alert, text=a, style="WM.Muted.TLabel").pack(
                    anchor="w", padx=8
                )

        jarvis_alerts = _load_jarvis_alerts()
        if jarvis_alerts:
            frm_jarvis_alerts = ttk.Frame(side, style="WM.Card.TFrame")
            frm_jarvis_alerts.pack(padx=10, pady=6, fill="x")
            ttk.Label(
                frm_jarvis_alerts,
                text="Alerty Jarvisa",
                style="WM.Card.TLabel",
            ).pack(anchor="w", padx=8, pady=(6, 0))
            color_map = {
                "error": "#d32f2f",
                "warning": "#f57c00",
                "info": "#1976d2",
            }
            for level_name, message in jarvis_alerts:
                foreground = color_map.get(level_name, "#495057")
                ttk.Label(
                    frm_jarvis_alerts,
                    text=f"[{level_name.upper()}] {message}",
                    foreground=foreground,
                    wraplength=180,
                    justify="left",
                ).pack(anchor="w", padx=8, pady=(0, 2))
        root.update_idletasks()
        if initial and start_panel is not None:
            otworz_panel(start_panel, start_name)
        root.update_idletasks()

    _build_sidebar(initial=True)
    root.bind("<<SidebarReload>>", lambda _e: _build_sidebar(initial=False))

    def _should_ignore_shortcut(event) -> bool:
        widget = getattr(event, "widget", None)
        try:
            state = getattr(event, "state", 0)
            if state & 0x0004 or state & 0x0008 or state & 0x0010:
                return True
        except Exception:
            pass
        if widget is None:
            return False
        try:
            widget_class = widget.winfo_class()
        except Exception:
            return False
        text_like = {
            "Entry",
            "TEntry",
            "Spinbox",
            "TSpinbox",
            "Text",
            "TText",
            "Combobox",
            "TCombobox",
        }
        return widget_class in text_like

    def _open_module_from_shortcut(module_key: str) -> bool:
        entry = module_shortcuts.get(module_key)
        if not entry:
            return False
        func, label = entry
        try:
            otworz_panel(func, label)
        except Exception as exc:
            log_akcja(
                f"[PANEL][SHORTCUT] Błąd otwierania modułu {module_key}: {exc}"
            )
            return False
        return True

    def _bind_shortcuts_once() -> None:
        if getattr(root, "_wm_shortcuts_bound", False):
            return
        setattr(root, "_wm_shortcuts_bound", True)

        def _factory(module_key: str, fallback=None):
            def _handler(event):
                if _should_ignore_shortcut(event):
                    return None
                opened = module_key and _open_module_from_shortcut(module_key)
                if opened:
                    return "break"
                if fallback is not None:
                    fallback()
                    return "break"
                return None

            return _handler

        root.bind_all("<KeyPress-n>", _factory("narzedzia"), add="+")
        root.bind_all("<KeyPress-N>", _factory("narzedzia"), add="+")
        root.bind_all("<KeyPress-m>", _factory("maszyny"), add="+")
        root.bind_all("<KeyPress-M>", _factory("maszyny"), add="+")
        root.bind_all(
            "<KeyPress-p>",
            _factory("uzytkownicy", fallback=_open_profile_entry),
            add="+",
        )
        root.bind_all(
            "<KeyPress-P>",
            _factory("uzytkownicy", fallback=_open_profile_entry),
            add="+",
        )

    _bind_shortcuts_once()

# eksportowane dla logowania
__all__ = ["uruchom_panel", "_shift_bounds", "_shift_progress", "_current_shift_label"]

# ⏹ KONIEC KODU
