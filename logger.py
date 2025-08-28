# Plik: logger.py
# Wersja pliku: 1.0.3
# Zmiany 1.0.3:
# - Dodano log_magazyn(akcja, dane) — zapis do logi_magazyn.txt (JSON Lines)
# - Reszta bez zmian; pozostawiono log_akcja oraz alias zapisz_log

from datetime import datetime
import json
import logging
from pathlib import Path

LOG_FILE = Path("logi_gui.txt")


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger writing to ``logi_gui.txt``."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def log_akcja(tekst: str) -> None:
    """Zapis prostych zdarzeń GUI/aplikacji do logi_gui.txt (linia tekstowa)."""
    try:
        logger = get_logger("gui")
        logger.info(tekst)
    except Exception:
        logging.getLogger(__name__).exception("log_akcja failed")


# zgodność wstecz: wiele miejsc może używać starej nazwy
zapisz_log = log_akcja


def log_magazyn(akcja: str, dane: dict) -> None:
    """
    Zapis operacji magazynowych do logi_magazyn.txt w formacie JSON Lines.
    Przykład rekordu:
    {"ts":"2025-08-18 12:34:56","akcja":"zuzycie","dane":{"item_id":"PR-30MM","ilosc":2,"by":"jan","ctx":"zadanie:..."}}
    """
    try:
        line = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "akcja": akcja,
            "dane": dane,
        }
        with open("logi_magazyn.txt", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        logging.getLogger(__name__).exception("log_magazyn failed")
