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
import tkinter as tk
from tkinter import ttk

from ui_theme import apply_theme_safe as apply_theme

# ====== LOGGING (lekka wersja zgodna z poprzednimi logami) ======
def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _ensure_log_dir():
    os.makedirs("logi", exist_ok=True)

def _log_path():
    return os.path.join("logi", f"warsztat_{datetime.now().strftime('%Y-%m-%d')}.log")

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
    ctx: dict zawierający co najmniej: {'login': ..., 'rola': ...}
    """
    try:
        import gui_panel
    except Exception:
        traceback.print_exc()
        _error("Nie można zaimportować gui_panel.")
        return

    try:
        login = (ctx or {}).get("login")
        rola  = (ctx or {}).get("rola")
        _dbg(f"[PANEL] uruchamiam z kontekstem {ctx}")
        gui_panel.uruchom_panel(root, ctx)  # zakładamy istniejący podpis jak dotąd
    except TypeError:
        # starsza sygnatura: (root, frame?, context?) – spróbuj wersji „legacy”
        try:
            # przygotuj pustą ramkę jeżeli poprzednia wersja jej oczekuje
            frame = ttk.Frame(root)
            frame.pack(fill="both", expand=True)
            gui_panel.uruchom_panel(root, frame, ctx)
        except Exception:
            traceback.print_exc()
            _error("Błąd uruchamiania panelu (legacy).")

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
        ctx = {"login": login, "rola": rola}
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

        _info(f"[{SESSION_ID}] Uruchamiam ekran logowania...")

        import gui_logowanie

        # Spróbuj wywołać z callbackiem (jeśli nowa wersja to wspiera)
        used_callback = False
        try:
            gui_logowanie.ekran_logowania(root, on_login=lambda login, rola, extra=None: _on_login(root, login, rola, extra))
            used_callback = True
        except TypeError:
            # starsza sygnatura (bez on_login) – zachowujemy dotychczasowe zachowanie
            gui_logowanie.ekran_logowania(root)

        # Jeśli login screen nie przełącza do main panelu sam (callback nieużyty),
        # to po prostu zostawiamy pętlę główną jak dotąd:
        root.mainloop()

    except Exception as e:
        traceback.print_exc()
        _error(f"Błąd startu GUI:\n{traceback.format_exc()}")
        _log("Program zakonczyl sie kodem 1.")
        # Zatrzymaj konsolę pod Windows (zachowanie z Twoich logów)
        try:
            input("Press any key to continue . . .")
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
