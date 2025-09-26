# Plik: logger.py
# Wersja pliku: 1.0.3
# Zmiany 1.0.3:
# - Dodano log_magazyn(akcja, dane) — zapis do logi_magazyn.txt (JSON Lines)
# - Reszta bez zmian; pozostawiono log_akcja oraz alias zapisz_log

from datetime import datetime
import json
import logging
import os

from config.paths import get_path, join_path


def _ensure_logs_dir() -> str:
    """Zapewnia istnienie katalogu logów i zwraca jego ścieżkę."""

    logs_dir = get_path("paths.logs_dir")
    if not logs_dir:
        return ""
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except Exception as exc:  # pragma: no cover - awaryjne środowiska
        print(f"[Błąd loggera] Nie można utworzyć katalogu logów {logs_dir!r}: {exc}")
    return logs_dir


def _ensure_app_handler() -> None:
    """Dodaje do logowania globalnego handler zapisujący do pliku aplikacji."""

    root_logger = logging.getLogger()
    log_file = join_path("paths.logs_dir", "app.log")
    if not log_file:
        return

    _ensure_logs_dir()

    level = logging.DEBUG if os.getenv("WM_DEBUG") else logging.INFO
    if root_logger.level != level:
        root_logger.setLevel(level)

    target_path = os.path.abspath(log_file)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if os.path.abspath(getattr(handler, "baseFilename", "")) == target_path:
                    return
            except Exception:
                continue

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root_logger.addHandler(file_handler)


_ensure_app_handler()

def log_akcja(tekst: str) -> None:
    """Zapis prostych zdarzeń GUI/aplikacji do logi_gui.txt (linia tekstowa)."""
    log_gui_file = join_path("paths.logs_dir", "logi_gui.txt")
    if not log_gui_file:
        return

    _ensure_logs_dir()
    try:
        with open(log_gui_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {tekst}\n")
    except Exception as e:
        # awaryjnie do konsoli – nie podnosimy wyjątku, żeby nie wywalać GUI
        print(f"[Błąd loggera] {e}")

# zgodność wstecz: wiele miejsc może używać starej nazwy
zapisz_log = log_akcja

def log_magazyn(akcja: str, dane: dict) -> None:
    """
    Zapis operacji magazynowych do logi_magazyn.txt w formacie JSON Lines.
    Przykład rekordu:
    {"ts":"2025-08-18 12:34:56","akcja":"zuzycie","dane":{"item_id":"PR-30MM","ilosc":2,"by":"jan","ctx":"zadanie:..."}}
    """
    log_magazyn_file = join_path("paths.logs_dir", "logi_magazyn.txt")
    if not log_magazyn_file:
        return

    _ensure_logs_dir()
    try:
        line = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "akcja": akcja,
            "dane": dane
        }
        with open(log_magazyn_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as e:
        # awaryjnie do konsoli – nie przerywamy działania
        print(f"[Błąd log_magazyn] {e}")
