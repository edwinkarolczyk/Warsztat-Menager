# WM-VERSION: 0.1
# version: 1.1.3
# Moduł: start
# Zmiany 1.1.3:
# - Wyłączono synchroniczne operacje Git przy starcie aplikacji, aby sieć/repozytorium nie blokowały GUI.
# - Aktualizacja repozytorium nie jest wykonywana automatycznie przed uruchomieniem okna WM.
# ⏹ KONIEC WSTĘPU

# start.py
# Zmiany względem 1.1.1:
#  - [NOWE] Ładowanie motywu zaraz po utworzeniu root (apply_theme_once(root))
#  - [NOWE] Tworzenie pliku data/user/<login>.json po udanym logowaniu (idempotentnie)
#
# Uwaga: Nie zmieniamy istniejącej logiki poza powyższymi punktami. Plik jest
# możliwie defensywny i wstecznie kompatybilny z gui_logowanie.ekran_logowania.

import os
import sys
import json
import traceback
import ctypes
import time
from datetime import datetime, timedelta
import logging
import subprocess
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, Toplevel

BOOTSTRAP_ACTIVE = True

from utils_json import ensure_json
from utils import error_dialogs
from config.paths import get_app_root, p_config, p_settings_schema
from config_manager import ConfigManager
try:
    from core import root_paths as wm_root_paths
except Exception:  # pragma: no cover - awaryjnie nie blokuj startu
    wm_root_paths = None

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")


def minimize_console():
    """Minimalizuje okno konsoli jeśli program działa w trybie konsoli."""

    try:
        hWnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hWnd:
            ctypes.windll.user32.ShowWindow(hWnd, 6)  # 6 = SW_MINIMIZE
    except Exception:
        pass


def _feature_flag_enabled(value, *, default: bool = True) -> bool:
    """Return True when a loosely-typed config flag should be considered enabled."""

    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    return bool(value)


def _auth_flag(config_manager, key: str, default: bool) -> bool:
    """Odczytaj flagę auth.* z ConfigManager z łagodnym fallbackiem."""

    try:
        if config_manager is None:
            return default
        return _feature_flag_enabled(config_manager.get(key, default), default=default)
    except Exception:
        return default


ROOT_SNAPSHOT = None


APP_ROOT = get_app_root()

def _default_config() -> dict:
    root = str(wm_root_paths.get_root_anchor()) if wm_root_paths is not None else str(APP_ROOT)
    data = str(wm_root_paths.get_data_root()) if wm_root_paths is not None else str(APP_ROOT / "data")
    logs = str(wm_root_paths.path_logs()) if wm_root_paths is not None else str(APP_ROOT / "logs")
    backup = str(wm_root_paths.path_backup()) if wm_root_paths is not None else str(APP_ROOT / "backup")
    assets = str(wm_root_paths.path_assets()) if wm_root_paths is not None else str(APP_ROOT / "assets")
    return {
        "paths": {
            "anchor_root": root,
            "data_root": data,
            "logs_dir": logs,
            "backup_dir": backup,
            "assets_dir": assets,
            "layout_dir": str(Path(data) / "layout"),
        },
        "machines": {
            "rel_path": "maszyny/maszyny.json",
        },
        "settings": {
            "require_reauth": True,
        },
    }


DEFAULT_CONFIG = _default_config()

CONFIG_MANAGER: ConfigManager | None = None
env_cfg = os.environ.get("WM_CONFIG_FILE")

if env_cfg:
    CONFIG_PATH = Path(env_cfg).expanduser()
else:
    CONFIG_PATH = APP_ROOT / "config.json"

CONFIG_PATH = CONFIG_PATH.resolve()
SETTINGS_SCHEMA_PATH = (APP_ROOT / "settings_schema.json").resolve()
_LOG_PATH: str | None = None

_POST_CONFIG_BOOTSTRAP_DONE = False


def _update_paths_from_manager(manager: ConfigManager) -> None:
    global CONFIG_PATH, SETTINGS_SCHEMA_PATH

    try:
        CONFIG_PATH = Path(p_config(manager))
    except Exception:
        CONFIG_PATH = Path(CONFIG_PATH)
    try:
        SETTINGS_SCHEMA_PATH = Path(p_settings_schema(manager))
    except Exception:
        SETTINGS_SCHEMA_PATH = Path(SETTINGS_SCHEMA_PATH)


def _ensure_config_manager() -> ConfigManager | None:
    global CONFIG_MANAGER

    if CONFIG_MANAGER is not None:
        return CONFIG_MANAGER

    manager: ConfigManager | None = None
    try:
        manager = ConfigManager()
    except Exception:
        manager = None

    if manager is not None:
        _update_paths_from_manager(manager)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        ensure_json(CONFIG_PATH, _default_config())
    except Exception:
        pass

    if manager is None:
        try:
            manager = ConfigManager()
        except Exception:
            manager = None
        if manager is not None:
            _update_paths_from_manager(manager)

    CONFIG_MANAGER = manager
    return CONFIG_MANAGER


def _post_config_bootstrap() -> None:
    global _POST_CONFIG_BOOTSTRAP_DONE

    if _POST_CONFIG_BOOTSTRAP_DONE:
        return

    manager = _ensure_config_manager()
    if manager is None:
        return

    try:
        profiles_data = load_profiles(manager)
        reset_admin_profile_if_needed(manager, profiles_data)
    except Exception:
        pass
    try:
        zaladuj_manifest(manager)
    except Exception:
        pass

    _POST_CONFIG_BOOTSTRAP_DONE = True


def _ensure_logging() -> str:
    global _LOG_PATH

    if _LOG_PATH is not None:
        return _LOG_PATH

    manager = _ensure_config_manager()
    if manager is not None:
        _LOG_PATH = init_logging(manager)
    else:
        _LOG_PATH = init_logging(None)
    return _LOG_PATH


try:
    from ui_theme import apply_theme_once
except Exception:
    def apply_theme_once(*_a, **_k):
        return None


try:
    from ui_theme import ensure_theme_applied
except Exception:
    def ensure_theme_applied(_win):
        return False


from gui_settings import SettingsWindow
from ustawienia_systemu import panel_ustawien
from core.logging_config import init_logging
from core.crash_handler import init_crash_handler
from profile_utils import load_profiles, reset_admin_profile_if_needed
from services import profile_service
from updater import _run_git_pull, _now_stamp, _git_has_updates
import updater
from utils.moduly import zaladuj_manifest


def _print_root_diagnostics(manager) -> None:
    """Emit podstawowe informacje diagnostyczne o ścieżkach <root>."""

    if wm_root_paths is not None:
        try:
            wm_root_paths.print_root_diagnostics(ROOT_SNAPSHOT)
        except Exception as exc:
            print(f"[WM-ROOT][WARN] Diagnostyka centralnego ROOT nieudana: {exc}")

    print("[WM ROOT DIAGNOSTICS]")
    if manager is None:
        print("  path_config  : <unavailable>")
        print("  path_data()  : <unavailable>")
        print("  path_backup(): <unavailable>")
        print("  path_logs()  : <unavailable>")
        return

    try:
        print(f"  path_anchor(): {manager.path_anchor()}")
        print(f"  path_config  : {manager.config_path()}")
        print(f"  path_data()  : {manager.path_data()}")
        print(f"  path_backup(): {manager.expanded('paths.backup_dir')}")
        print(f"  path_logs()  : {manager.expanded('paths.logs_dir')}")
    except Exception as exc:
        print(f"  [DIAG] Nie udało się pobrać ścieżek ConfigManager: {exc}")
def _log_path():
    return _ensure_logging()


def _info(msg):
    _ensure_logging()
    logging.info(msg)


def _error(msg):
    _ensure_logging()
    logging.error(msg)


def _dbg(msg):
    _ensure_logging()
    logging.debug(msg)

SESSION_ID = None


# ====== AKTYWNOŚĆ UŻYTKOWNIKA ======
class _InactivityMonitor:
    """Obserwuje aktywność użytkownika i wywołuje callback po bezczynności."""

    def __init__(self, root, timeout_sec, callback):
        self.root = root
        self.timeout = timeout_sec
        self.callback = callback
        self._deadline = datetime.now() + timedelta(seconds=timeout_sec)
        self._job = None
        for seq in ("<Key>", "<Button>", "<Motion>"):
            root.bind_all(seq, self._reset, add="+")
        self._tick()

    def _reset(self, _event=None):
        self._deadline = datetime.now() + timedelta(seconds=self.timeout)

    def _tick(self):
        if datetime.now() >= self._deadline:
            self.callback()
            return
        self._job = self.root.after(1000, self._tick)

    def cancel(self):
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:  # pragma: no cover - defensywne
                pass
            self._job = None


def logout():
    """Domyślne wylogowanie wywoływane po bezczynności."""
    _info(f"[{SESSION_ID}] Wylogowanie z powodu bezczynności")
    try:
        if tk._default_root:
            tk._default_root.destroy()
    except Exception:  # pragma: no cover - defensywne
        pass


_USER_ACTIVITY_MONITOR = None


def monitor_user_activity(root, timeout_sec=300, callback=None):
    """Rozpoczyna monitorowanie aktywności użytkownika na danym ``root``.

    Zwraca obiekt monitora, który można anulować metodą ``cancel``.
    """

    global _USER_ACTIVITY_MONITOR
    if callback is None:
        callback = logout
    if _USER_ACTIVITY_MONITOR:
        _USER_ACTIVITY_MONITOR.cancel()
    _USER_ACTIVITY_MONITOR = _InactivityMonitor(root, timeout_sec, callback)
    return _USER_ACTIVITY_MONITOR


def restart_user_activity_monitor(timeout_sec):
    """Restartuje monitor aktywności z nowym timeoutem (w sekundach)."""

    global _USER_ACTIVITY_MONITOR
    if not _USER_ACTIVITY_MONITOR:
        return None
    root = _USER_ACTIVITY_MONITOR.root
    callback = _USER_ACTIVITY_MONITOR.callback
    _USER_ACTIVITY_MONITOR.cancel()
    _USER_ACTIVITY_MONITOR = _InactivityMonitor(root, timeout_sec, callback)
    return _USER_ACTIVITY_MONITOR


def show_startup_error(e):
    """Pokazuje okno z informacją o błędzie startowym.

    Wczytuje treść aktualnego logu i udostępnia trzy przyciski:
    - "Skopiuj log" – kopiuje całą zawartość logu do schowka,
    - "Przywróć kopię" – przywraca najnowszą kopię zapasową,
    - "Zamknij" – zamyka program.
    """

    log_path = _log_path()
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            log_text = f.read()
    except Exception:
        log_text = ""

    root = tk.Tk()
    ensure_theme_applied(root)
    root.title("Błąd startu")

    tk.Label(
        root,
        text=f"Wystąpił błąd: {e}\nSzczegóły w logu.",
    ).pack(padx=10, pady=10)

    text = tk.Text(root, height=20, width=80)
    text.insert("1.0", log_text)
    text.config(state="disabled")
    text.pack(padx=10, pady=10)

    def copy_log():
        root.clipboard_clear()
        root.clipboard_append(log_text)

    def restore_backup():
        try:
            backups = updater._list_backups()
            if backups:
                stamp = backups[-1]
                updater._restore_backup(stamp)
                messagebox.showinfo(
                    "Przywrócono kopię",
                    "Przywrócono kopię zapasową. Uruchom ponownie aplikację.",
                )
            else:
                messagebox.showwarning(
                    "Brak kopii", "Nie znaleziono kopii zapasowych.")
        except Exception as exc:  # pragma: no cover - defensywne
            error_dialogs.show_error_dialog("Błąd przywracania", str(exc))

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=5)

    tk.Button(btn_frame, text="Skopiuj log", command=copy_log).pack(
        side=tk.LEFT, padx=5
    )
    tk.Button(btn_frame, text="Przywróć kopię", command=restore_backup).pack(
        side=tk.LEFT, padx=5
    )
    tk.Button(btn_frame, text="Zamknij", command=root.destroy).pack(
        side=tk.LEFT, padx=5
    )

    root.mainloop()


# ====== AUTO UPDATE ======
def auto_update_on_start():
    """Automatyczna aktualizacja przy starcie jest celowo wyłączona.

    Aktualizacje Git wykonywane synchronicznie podczas startu potrafią zablokować
    główny wątek aplikacji (np. oczekiwanie na sieć, Git lub blokadę repozytorium).
    Zostawiamy updater dostępny dla późniejszego uruchomienia ręcznego/asynchronicznego.
    """
    return False

# ====== USER FILE (NOWE) ======
def _ensure_user_file(login, rola):
    """
    Tworzy plik data/user/<login>.json przy pierwszym logowaniu (idempotentnie).
    Nie nadpisuje istniejącego pliku.
    """
    try:
        if not login:
            return
        if wm_root_paths is not None:
            base = str(wm_root_paths.get_data_root() / "user")
        else:
            base = os.path.join("data", "user")
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, f"{login}.json")
        if not os.path.exists(path):
            data = {
                "login": str(login),
                "rola": str(rola or ""),
                "stanowisko": "",
                "dzial": "",
                "zmiana": "I",
                "zmiana_godz": "06:00-14:00",
                "avatar": "",
                "urlop": 0,
                "l4": 0
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[WM-ROOT][USER] file={path}")
            _info(f"[{SESSION_ID}] Utworzono plik użytkownika: {path}")
    except Exception as e:
        _error(f"[{SESSION_ID}] Błąd tworzenia pliku użytkownika: {e}")

# ====== KONTEXT PANELU ======
def _open_main_panel(root, ctx):
    """
    Uruchamia główny panel po udanym logowaniu.
    ctx: dict zawierający co najmniej: {'login': <str>, 'rola': <str>}
    """
    login = str((ctx or {}).get("login", ""))
    rola = str((ctx or {}).get("rola", ""))

    # Pobierz preferencje użytkownika
    try:
        import profile_utils
        user = profile_utils.get_user(login) or {}
    except Exception:
        traceback.print_exc()
        _error("Nie można pobrać profilu użytkownika.")
        user = {}

    pref = user.get("preferencje", {}).get("widok_startowy", "panel")
    _dbg(f"[START] widok_startowy={pref}")

    if pref == "dashboard":
        # Uruchom dashboard w osobnym głównym oknie
        try:
            root.destroy()
        except Exception:
            pass
        try:
            import dashboard_demo_fs
            dash = dashboard_demo_fs.WMDashboard(login=login, rola=rola)
            dash.mainloop()
        except Exception:
            traceback.print_exc()
            _error("Błąd uruchamiania dashboardu.")
        return

    # Domyślnie uruchom panel
    try:
        import gui_panel
    except Exception:
        traceback.print_exc()
        _error("Nie można zaimportować gui_panel.")
        return

    try:
        _dbg(f"[PANEL] uruchamiam z kontekstem {ctx}")
        gui_panel.uruchom_panel(root, login, rola)
    except Exception:
        traceback.print_exc()
        _error("Błąd uruchamiania panelu.")


def open_settings_window(root):
    print("[WM-DBG] open_settings_window()")
    _ensure_config_manager()

    def _resolve_login() -> str | None:
        for attr in ("active_login", "current_user", "username", "_wm_login"):
            value = getattr(root, attr, None)
            if value:
                return str(value)
        return None

    def _resolve_role() -> str | None:
        for attr in ("_wm_rola", "rola", "current_role", "active_role"):
            value = getattr(root, attr, None)
            if value:
                return str(value)
        return None

    container = None
    for attr in ("content", "main_content"):
        candidate = getattr(root, attr, None)
        if isinstance(candidate, tk.Misc) and candidate.winfo_exists():
            container = candidate
            break

    if container is not None:
        panel_ustawien(
            root,
            container,
            login=_resolve_login(),
            rola=_resolve_role(),
            config_path=str(CONFIG_PATH),
            schema_path=str(SETTINGS_SCHEMA_PATH),
        )
        try:
            root.update_idletasks()
        except Exception:
            pass
        return container

    win = Toplevel(root)
    win.title("Ustawienia – Warsztat Menager")
    apply_theme_once(win)
    SettingsWindow(
        win,
        config_path=str(CONFIG_PATH),
        schema_path=str(SETTINGS_SCHEMA_PATH),
    )

    try:
        win.update_idletasks()
        screen_h = win.winfo_screenheight()
        screen_w = win.winfo_screenwidth()
        req_w = win.winfo_reqwidth()
        req_h = win.winfo_reqheight()

        max_w = int(screen_w * 0.9)
        max_h = int(screen_h * 0.9)
        width = min(max(req_w, 640), max_w)
        height = min(max(req_h, 480), max_h)

        win.geometry(f"{width}x{height}")
        win.minsize(min(width, 800), min(height, 600))
    except Exception:
        win.geometry("1000x680")
    return win
# ====== TUTORIAL ======
def _show_tutorial_if_first_run(root):
    """Wyświetla instrukcje przy pierwszym uruchomieniu."""
    try:
        cfg = ConfigManager()
        if not cfg.get("tutorial_completed", False):
            steps = [
                "Witaj w Warsztat Menager!",
                "Tu zobaczysz, jak korzystać z aplikacji.",
                "Powodzenia!",
            ]
            for text in steps:
                messagebox.showinfo("Instrukcje", text, parent=root)
            cfg.set("tutorial_completed", True)
            cfg.save_all()
    except Exception as e:  # pragma: no cover - defensywne
        _error(f"Błąd tutorialu: {e}")

# ====== CALLBACK LOGOWANIA (jeśli gui_logowanie go wspiera) ======
def _on_login(root, login, rola, extra=None):
    """
    Domyślny callback przekazywany do gui_logowanie (o ile obsługuje).
    """
    try:
        _info(f"[{SESSION_ID}] Zalogowano: login={login}, rola={rola}")
        # NOWE: utwórz plik użytkownika
        _ensure_user_file(login, rola)

        # Zbuduj ctx (zachowujemy minimalny zestaw, żeby nie wprowadzać zmian)
        ctx = {"login": str(login), "rola": str(rola)}
        if isinstance(extra, dict):
            ctx.update(extra)

        _open_main_panel(root, ctx)
    except Exception:
        traceback.print_exc()
        _error("Błąd w _on_login.")


def _auto_login_if_enabled(root) -> bool:
    """Attempt automatic login if configured in settings."""

    try:
        cfg = ConfigManager()
    except Exception:
        return False

    try:
        enabled = bool(cfg.get("auth.auto_login_enabled", False))
    except Exception:
        enabled = False
    if not enabled:
        return False

    try:
        profile_id = str(cfg.get("auth.auto_login_profile", "") or "").strip()
    except Exception:
        profile_id = ""

    if not profile_id:
        _info(f"[{SESSION_ID}] Auto-logowanie pominięte – brak profilu w konfiguracji")
        return False

    try:
        user = profile_service.get_user(profile_id)
    except Exception as exc:
        _error(f"[{SESSION_ID}] Auto-logowanie nieudane (błąd pobierania profilu): {exc}")
        return False

    if not user:
        _info(f"[{SESSION_ID}] Auto-logowanie nieudane – profil '{profile_id}' nie istnieje")
        return False

    if not user.get("active", True):
        _info(f"[{SESSION_ID}] Auto-logowanie pominięte – profil '{profile_id}' jest nieaktywny")
        return False

    login = str(user.get("login", profile_id)).strip()
    rola = str(user.get("rola", "") or "")
    _info(f"[{SESSION_ID}] Auto-logowanie profilu {login} (rola={rola or 'brak'})")
    extra = {"auto_login": True}
    _on_login(root, login, rola, extra)
    return True


def _wm_git_check_on_start(
    preferred_branch: str | None = None,
):
    """Automatyczny check aktualizacji z repozytorium."""

    if preferred_branch is None:
        try:
            preferred_branch = (
                CONFIG_MANAGER.get("updates.push_branch", "Rozwiniecie")
                if CONFIG_MANAGER
                else "Rozwiniecie"
            )
        except Exception:
            preferred_branch = "Rozwiniecie"

    try:
        if not shutil.which("git"):
            print("[WM-DBG][GIT] git.exe nie znaleziony – pomijam check.")
            return

        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        subprocess.run(
            ["git", "fetch", "origin", preferred_branch],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        cp = subprocess.run(
            [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...origin/{preferred_branch}",
            ],
            capture_output=True,
            text=True,
        )

        ahead, behind = 0, 0
        if cp.returncode == 0 and cp.stdout.strip():
            parts = cp.stdout.strip().split()
            if len(parts) >= 2:
                ahead, behind = int(parts[0]), int(parts[1])

        print(f"[WM-DBG][GIT] ahead={ahead} behind={behind}")

        if behind > 0:
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
            )
            if status_proc.returncode == 0 and status_proc.stdout.strip():
                print(
                    "[WM-DBG][GIT] skipped: local changes (commit or stash required)"
                )
            else:
                print(
                    "[WM-DBG][GIT] Wykryto nowsze commity w origin, wykonuję git pull --rebase..."
                )
                pull_proc = subprocess.run(
                    ["git", "pull", "--rebase", "origin", preferred_branch],
                    check=False,
                )
                if pull_proc.returncode == 0:
                    print("[WM-DBG][GIT] Aktualizacja lokalnego repo zakończona.")
                else:
                    print(
                        "[WM-DBG][GIT] git pull --rebase zakończony kodem "
                        f"{pull_proc.returncode}."
                    )
        else:
            print("[WM-DBG][GIT] Repozytorium aktualne, brak zmian.")

        if ahead > 0:
            print(
                "[WM-DBG][GIT] Lokalny branch jest przed origin – brak automatycznych akcji."
            )

    except Exception as exc:
        print(f"[WM-DBG][GIT] Wyjątek w _wm_git_check_on_start: {exc}")


# ====== MAIN ======
def main():
    global SESSION_ID, BOOTSTRAP_ACTIVE
    init_crash_handler()
    # Opcjonalnie wycisz WARNING Qt
    # "Untested Windows version 10.0 detected!" – porządkuje logi.
    SESSION_ID = f"{datetime.now().strftime('%H%M%S')}"
    global ROOT_SNAPSHOT, CONFIG_MANAGER, CONFIG_PATH

    if wm_root_paths is not None:
        try:
            # Tu wolno pokazać wybór folderu ROOT, bo startuje właściwa aplikacja.
            ROOT_SNAPSHOT = wm_root_paths.install_environment(prompt=True)
            CONFIG_MANAGER = None
            try:
                os.environ["WM_ROOT"] = str(wm_root_paths.get_root_anchor())
                os.environ["WM_DATA_ROOT"] = str(wm_root_paths.get_data_root())
                os.environ["WM_CONFIG_FILE"] = str(wm_root_paths.path_config())
            except Exception:
                pass
            env_cfg = os.environ.get("WM_CONFIG_FILE")
            if env_cfg:
                CONFIG_PATH = Path(env_cfg).expanduser().resolve()
            try:
                print(f"[WM-ROOT][START] CONFIG_PATH={CONFIG_PATH}")
                print(f"[WM-ROOT][START] WM_ROOT={os.environ.get('WM_ROOT')}")
                print(f"[WM-ROOT][START] WM_DATA_ROOT={os.environ.get('WM_DATA_ROOT')}")
                print(
                    f"[WM-ROOT][START] WM_CONFIG_FILE={os.environ.get('WM_CONFIG_FILE')}"
                )
            except Exception:
                pass
            wm_root_paths.print_root_diagnostics(ROOT_SNAPSHOT)
        except Exception as exc:
            print(f"[WM-ROOT][WARN] Bootstrap ROOT w main() nieudany: {exc}")

    manager = _ensure_config_manager()
    _print_root_diagnostics(manager)
    _post_config_bootstrap()
    _info(f"Uzywam Pythona: {sys.executable or sys.version}")
    _info(f"Katalog roboczy: \"{os.getcwd()}\"")
    _info("Start programu Warsztat Menager (start.py 1.1.2)")
    _info(f"Log file: {_log_path()}")
    if manager is not None:
        try:
            _info(f"path_anchor(): {manager.path_anchor()}")
            _info(f"path_config  : {manager.get_config_path()}")
            _info(f"path_data()  : {manager.path_data()}")
            _info(f"path_backup(): {manager.path_backup()}")
            _info(f"path_logs()  : {manager.path_logs()}")
            for ensured_path in (
                manager.path_anchor(),
                manager.path_data(),
                manager.path_backup(),
                manager.path_logs(),
            ):
                try:
                    os.makedirs(ensured_path, exist_ok=True)
                except Exception as exc:
                    logging.warning(
                        "[PORTABLE] Nie mogę utworzyć katalogu %s: %s",
                        ensured_path,
                        exc,
                    )
        except Exception as exc:
            _error(f"Diagnostyka ścieżek nieudana: {exc}")
    _info(f"=== START SESJI: {datetime.now()} | ID={SESSION_ID} ===")

    # UWAGA: minimalizacja działa tylko w wersji .py, nie przeszkadza w EXE.
    time.sleep(0.3)
    minimize_console()

    updated = auto_update_on_start()

    if updated:
        try:
            import gui_changelog
            gui_changelog.show_changelog()
        except Exception as e:
            _error(f"Nie można wyświetlić changelog: {e}")

    # Nie wykonujemy sieciowego Git check podczas startu GUI.
    update_available = False

    # Wstępna inicjalizacja konfiguracji, jeśli masz ConfigManager, zostawiamy symbolicznie:
    try:
        _info("ConfigManager: OK")
        try:
            # Stary backend.bootstrap_root mieszał APP_ROOT z WM_ROOT i potrafił
            # ponownie pytać o folder albo tworzyć strukturę poza wybranym ROOT.
            # Centralnym mechanizmem ROOT jest teraz core.root_paths.install_environment().
            if wm_root_paths is not None:
                try:
                    wm_root_paths.ensure_root_tree()
                except Exception as exc:
                    _error(f"Root bootstrap ensure_root_tree failed: {exc}")
            _info("Root bootstrap: OK")
        except Exception as e:  # pragma: no cover - startup warning only
            try:
                messagebox.showwarning(
                    "Problem ze ścieżkami WM",
                    "Nie udało się przygotować głównego folderu danych WM.\n\n"
                    "Wskaż ROOT danych w ustawieniach lub usuń wm_root.json i uruchom program ponownie.\n\n"
                    f"Szczegóły: {e}",
                    parent=None,
                )
            except Exception:
                pass
            _error("Root bootstrap failed", str(e))
    except Exception:
        _error("ConfigManager: problem (pomijam)")

    jarvis_stop_fn = None
    try:
        from core.jarvis_engine import run_jarvis_background, stop_jarvis as _stop_jarvis
        from services.profile_service import ProfileService

        cfg_for_jarvis = ConfigManager()
        try:
            active_login = ProfileService.ensure_active_user_or_none()
        except Exception:
            active_login = None

        jarvis_stop_fn = _stop_jarvis
        if cfg_for_jarvis.get("jarvis.enabled", False) and active_login:
            run_jarvis_background()
    except Exception as exc:
        print("[JARVIS] init skipped:", exc)

    # === GUI start ===
    try:
        root = tk.Tk()
        ensure_theme_applied(root)

        # [NOWE] Theme od wejścia — dokładnie to, o co prosiłeś:
        apply_theme_once(root)
        try:
            import rc1_audit_hook
        except Exception:
            pass
        try:
            cfg_manager = ConfigManager()
            hotfix_raw = cfg_manager.get("rc1.hotfix.enabled", None)
        except Exception:
            hotfix_raw = None
        if _feature_flag_enabled(hotfix_raw, default=False):
            try:
                import rc1_hotfix_actions   # RC1: akcje BOM + Audyt (dispatcher)
            except Exception:
                pass

        try:
            import rc1_theme_fix        # RC1: kontrast napisów (TButton)
        except Exception:
            pass

        try:
            import rc1_data_bootstrap   # RC1: pliki danych wg paths.* / configu (magazyn, BOM, narzędzia)
        except Exception:
            pass

        try:
            import rc1_profiles_bootstrap  # RC1: profiles.json + przypominajka o haśle admina
        except Exception:
            pass

        def _on_root_close() -> None:
            try:
                if jarvis_stop_fn:
                    jarvis_stop_fn()
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass

        try:
            root.protocol("WM_DELETE_WINDOW", _on_root_close)
        except Exception:
            pass

        _show_tutorial_if_first_run(root)

        _info(f"[{SESSION_ID}] Uruchamiam ekran logowania...")

        returned_root = root
        auto_logged = False
        try:
            auto_logged = _auto_login_if_enabled(root)
        except Exception:
            traceback.print_exc()
            _error("Błąd auto-logowania – przechodzę do standardowego ekranu logowania")

        embedded_login = _auth_flag(CONFIG_MANAGER, "auth.embedded_login", False)
        guest_start = _auth_flag(CONFIG_MANAGER, "auth.guest_start", True)

        if embedded_login and guest_start and not auto_logged:
            try:
                import gui_panel
                gui_panel.uruchom_panel(root, login="Gość", rola="guest")
            except Exception:
                traceback.print_exc()
                _error("Błąd uruchomienia trybu gościa – przechodzę do pełnego logowania")
                embedded_login = False

        if not auto_logged and not (embedded_login and guest_start):
            import gui_logowanie

            returned_root = gui_logowanie.ekran_logowania(
                root,
                on_login=lambda login, rola, extra=None: _on_login(
                    root, login, rola, extra
                ),
                update_available=update_available,
            )

        if returned_root is not None and returned_root is not root:
            root = returned_root

        try:
            cm = ConfigManager()
            timeout = int(cm.get("auth.session_timeout_min", 30)) * 60
        except Exception:
            timeout = 30 * 60
        monitor_user_activity(root, timeout)

        try:
            BOOTSTRAP_ACTIVE = False
        except Exception:
            pass

        # Jeśli login screen nie przełącza do main panelu sam (callback nieużyty),
        # to po prostu zostawiamy pętlę główną jak dotąd:
        root.mainloop()

        if jarvis_stop_fn:
            try:
                jarvis_stop_fn()
            except Exception:
                pass

    except Exception as e:
        traceback.print_exc()
        _error(f"Błąd startu GUI:\n{traceback.format_exc()}")
        show_startup_error(e)
        sys.exit(1)

if __name__ == "__main__":
    # --- Integracja manifestu modułów (lekka) ---
    try:
        from utils.moduly import (
            zaladuj_manifest,
            lista_modulow,
            sprawdz_reguly,
            tag_logu,
        )

        _mod_tag = tag_logu("rdzen")
        print(f"{_mod_tag} Ładuję manifest modułów…")
        _manifest = zaladuj_manifest(CONFIG_MANAGER)
        _lista = lista_modulow(_manifest)
        print(f"{_mod_tag} Moduły zdefiniowane w manifeście: {', '.join(_lista)}")
        _kom = sprawdz_reguly(_manifest)
        for k in _kom:
            print(k)
    except Exception as e:
        print(f"[ERROR] Problem z manifestem modułów: {e}")
    # --- Koniec integracji manifestu ---
    # Git check/pull przy starcie wyłączony: nie blokujemy uruchamiania WM.
    main()

# ⏹ KONIEC KODU
