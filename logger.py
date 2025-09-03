# Plik: logger.py
# Wersja pliku: 1.0.3
# Zmiany 1.0.3:
# - Dodano log_magazyn(akcja, dane) — zapis do logi_magazyn.txt (JSON Lines)
# - Reszta bez zmian; pozostawiono log_akcja oraz alias zapisz_log

from datetime import datetime
import json

def log_akcja(tekst: str) -> None:
    """Zapis prostych zdarzeń GUI/aplikacji do logi_gui.txt (linia tekstowa)."""
    try:
        with open("logi_gui.txt", "a", encoding="utf-8") as f:
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
    {"ts":"2025-08-18 12:34:56","akcja":"zuzycie","dane":{"item_id":"PR-30MM","stan":2,"by":"jan","ctx":"zadanie:..."}}
    """
    try:
        line = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "akcja": akcja,
            "dane": dane
        }
        with open("logi_magazyn.txt", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as e:
        # awaryjnie do konsoli – nie przerywamy działania
        print(f"[Błąd log_magazyn] {e}")
