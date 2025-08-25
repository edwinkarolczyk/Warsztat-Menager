# --- bootstrap: bezpieczny start ---
import os, sys, traceback, datetime



# Ustaw katalog roboczy na folder z tym plikiem
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Stwórz folder logów, jeśli brak
os.makedirs("logi", exist_ok=True)

_boot_log = os.path.join("logi", f"bootstrap_{datetime.date.today().isoformat()}.log")

def _safe_log(msg: str):
    try:
        with open(_boot_log, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass

_safe_log(f"[BOOT] Python: {sys.version}")
_safe_log(f"[BOOT] Executable: {sys.executable}")
_safe_log(f"[BOOT] CWD: {os.getcwd()}")
# --- koniec bootstrapu ---

# Plik: start.py
# Wersja pliku: 1.1.1
# Zmiany 1.1.1:
# - Dodano znacznik sesji (UUID skrócony) do logów
# Zmiany 1.1.0:
# - Centralne logowanie do pliku: logi/warsztat_YYYY-MM-DD.log
# - Przekierowanie stdout/stderr do pliku + konsoli (TeeLogger)
# - sys.excepthook: nieprzechwycone wyjątki trafiają do loga
#
# Poprzednio 1.0.3:
# - Nagłówek wersji (bez zmian funkcjonalnych)

import os, sys, json, datetime, traceback, uuid
from tkinter import messagebox, Tk

# === LOGI SYSTEMU (inicjalizacja na samym początku) ===========================
LOG_DIR = "logi"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"warsztat_{datetime.date.today()}.log")

class TeeLogger:
    """Pisz równolegle do wielu streamów (np. konsola + plik)."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                # Nie blokuj przy problemach z jednym streamem
                pass
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass

# Otwórz plik logów tylko raz (pozostaw otwarty do końca procesu)
_log_fp_out = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
_log_fp_err = open(LOG_FILE, "a", encoding="utf-8", buffering=1)

# Przekieruj stdout/stderr na Tee (konsola + plik)
sys.stdout = TeeLogger(sys.__stdout__, _log_fp_out)
sys.stderr = TeeLogger(sys.__stderr__, _log_fp_err)

def _log_info(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[INFO] {ts} {msg}")

def _log_error(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sys.stderr.write(f"[ERROR] {ts} {msg}\n")

def _excepthook(exc_type, exc, tb):
    """Globalny hak na nieprzechwycone wyjątki: log + ewentualny komunikat."""
    trace = "".join(traceback.format_exception(exc_type, exc, tb))
    _log_error("NIEPRZECHWYCONY WYJĄTEK:\n" + trace)

# Zarejestruj globalny hook wyjątków
sys.excepthook = _excepthook

# Znacznik sesji (do odróżniania uruchomień w jednym pliku dziennym)
SESSION_ID = uuid.uuid4().hex[:8]

_log_info("Start programu Warsztat Menager (start.py 1.1.1)")
_log_info(f"Log file: {LOG_FILE}")
_log_info(f"=== START SESJI: {datetime.datetime.now()} | ID={SESSION_ID} ===")

# =============================================================================

# Konfiguracja
try:
    from config_manager import ConfigManager
except Exception:
    ConfigManager = None

CFG = None

def init_config():
    global CFG
    try:
        if ConfigManager is None:
            raise RuntimeError("Brak modułu config_manager")
        CFG = ConfigManager()
        _log_info("ConfigManager: OK")
    except Exception as e:
        _log_error(f"ConfigManager niedostępny, tryb awaryjny: {e}")
        try:
            with open("config.defaults.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            class Tmp:
                merged = data
                def get(self, k, d=None): return d
            CFG = Tmp()
            _log_info("Załadowano config.defaults.json (awaryjnie).")
        except Exception as e2:
            _log_error(f"Nie udało się wczytać config.defaults.json: {e2}")
            # mimo to pozostaw CFG = None, program może nadal spróbować wystartować

def main():
    # Inicjalizacja configu
    init_config()

    # Start GUI – ekran logowania
    try:
        import gui_logowanie  # pokazuje fullscreen logowania
        root = Tk()
        _log_info(f"[{SESSION_ID}] Uruchamiam ekran logowania...")
        gui_logowanie.ekran_logowania(root)
        root.mainloop()
        _log_info(f"[{SESSION_ID}] Zamknięto główne okno (mainloop).")
    except Exception as e:
        # Zalogiuj pełny traceback
        _log_error("Błąd startu GUI:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))
        try:
            # awaryjny komunikat, gdy nawet Tk nie wstanie
            root = Tk(); root.withdraw()
            messagebox.showerror("Błąd startu", f"Nie udało się uruchomić GUI:\n{e}")
        except Exception as e2:
            _log_error(f"Awaria przy pokazywaniu messagebox: {e2}")
            # Ostatecznie wypisz do stderr (też trafi do loga)
            sys.stderr.write(f"Błąd startu GUI: {e}\n")
        finally:
            # domknij logi na wyjściu
            try:
                _log_fp_out.flush(); _log_fp_out.close()
                _log_fp_err.flush(); _log_fp_err.close()
            except Exception:
                pass
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    finally:
        # Bezpieczne domknięcie plików przy normalnym zakończeniu
        try:
            _log_fp_out.flush(); _log_fp_out.close()
            _log_fp_err.flush(); _log_fp_err.close()
        except Exception:
            pass
