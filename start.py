# start.py
# Wersja: 1.1.2
# Zmiany względem 1.1.1:
#  - [NOWE] Ładowanie motywu zaraz po utworzeniu root (apply_theme(root))
#  - [NOWE] Tworzenie pliku data/user/<login>.json po udanym logowaniu (idempotentnie)
#
# Uwaga: Nie zmieniamy istniejącej logiki poza powyższymi punktami. Plik jest
# możliwie defensywny i wstecznie kompatybilny z gui_logowanie.ekran_logowania.

import os
import sys
import json
import traceback
from datetime import datetime
import logging
import tkinter as tk
from tkinter import messagebox
from utils import error_dialogs

from ui_theme import apply_theme_safe as apply_theme
from config_manager import ConfigManager
from updater import _run_git_pull, _now_stamp, _git_has_updates
import updater
from pathlib import Path

# ====== LOGGING (lekka wersja zgodna z poprzednimi logami) ======
def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _ensure_log_dir():
    os.makedirs("logi", exist_ok=True)

def _log_path():
    return os.path.join("logi", f"warsztat_{datetime.now().strftime('%Y-%m-%d')}.log")

_ensure_log_dir()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path(), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

def _log(line):
    _ensure_log_dir()
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

def _info(msg):
    _log(f"[INFO] {_ts()} {msg}")

def _error(msg):
    _log(f"[ERROR] {_ts()} {msg}")

def _dbg(msg):
    _log(f"[WM-DBG] {msg}")

SESSION_ID = None


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
    """Run git pull if ``updates.auto`` flag is enabled.

    Returns ``True`` if the repository was updated, otherwise ``False``.
    """
    try:
        cfg = ConfigManager()
    except Exception as e:
        _error(f"ConfigManager init failed: {e}")
        return False
    if cfg.get("updates.auto", False):
        try:
            output = _run_git_pull(Path.cwd(), _now_stamp())
            if output and "Already up to date." not in output:
                return True
        except Exception as e:
            _error(f"auto_update_on_start error: {e}")
            msg = str(e).lower()
            if "lokalne zmiany" in msg or "local changes" in msg:
                try:
                    r = tk.Tk()
                    r.withdraw()
                    error_dialogs.show_error_dialog("Aktualizacje", str(e))
                    r.destroy()
                except Exception:
                    pass
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

# ====== MAIN ======
def main():
    global SESSION_ID
    SESSION_ID = f"{datetime.now().strftime('%H%M%S')}"
    _info(f"Uzywam Pythona: {sys.executable or sys.version}")
    _info(f"Katalog roboczy: \"{os.getcwd()}\"")
    _info(f"{_ts()} Start programu Warsztat Menager (start.py 1.1.2)")
    _info(f"{_ts()} Log file: {_log_path()}")
    _info(f"{_ts()} === START SESJI: {datetime.now()} | ID={SESSION_ID} ===")

    updated = auto_update_on_start()

    if updated:
        try:
            import gui_changelog
            gui_changelog.show_changelog()
        except Exception as e:
            _error(f"Nie można wyświetlić changelog: {e}")

    update_available = _git_has_updates(Path.cwd())

    # Wstępna inicjalizacja konfiguracji, jeśli masz ConfigManager, zostawiamy symbolicznie:
    try:
        _info("ConfigManager: OK")
    except Exception:
        _error("ConfigManager: problem (pomijam)")

    # === GUI start ===
    try:
        root = tk.Tk()

        # [NOWE] Theme od wejścia — dokładnie to, o co prosiłeś:
        apply_theme(root)

        _show_tutorial_if_first_run(root)

        _info(f"[{SESSION_ID}] Uruchamiam ekran logowania...")

        import gui_logowanie
        gui_logowanie.ekran_logowania(
            root,
            on_login=lambda login, rola, extra=None: _on_login(root, login, rola, extra),
            update_available=update_available,
        )

        # Jeśli login screen nie przełącza do main panelu sam (callback nieużyty),
        # to po prostu zostawiamy pętlę główną jak dotąd:
        root.mainloop()

    except Exception as e:
        traceback.print_exc()
        _error(f"Błąd startu GUI:\n{traceback.format_exc()}")
        show_startup_error(e)
        sys.exit(1)

if __name__ == "__main__":
    main()
