# Plik: kreator_sprawdzenia.py
# Wersja: 1.1
# Opis: Sprawdza obecność plików i wersję deklarowaną w nagłówku (komentarz # Wersja pliku: ...)

import os
import re
from utils.path_utils import cfg_path

# Lista wymaganych plików i oczekiwanych wersji
wymagane_pliki = {
    "start.py": "1.4.7",
    "gui_logowanie.py": "1.4.7",
    "gui_panel.py": "1.4.8",
    "layout_prosty.py": "1.4.7",
    "ustawienia_systemu.py": "1.4.8",
    "uzytkownicy.json": None,
    cfg_path("config.json"): None,
}

def sprawdz_wersje(plik, oczekiwana):
    try:
        with open(plik, "r", encoding="utf-8") as f:
            for linia in f:
                match = re.match(r"# Wersja pliku:\s*(\S+)", linia)
                if match:
                    znaleziona = match.group(1)
                    if oczekiwana is None or znaleziona == oczekiwana:
                        return f"✅ {plik} – wersja OK ({znaleziona})"
                    else:
                        return f"⚠️ {plik} – wersja NIEZGODNA (znaleziona {znaleziona}, oczekiwana {oczekiwana})"
            return f"⚠️ {plik} – brak nagłówka wersji"
    except FileNotFoundError:
        return f"❌ Brakuje: {plik}"

def sprawdz():
    print("\n🛠 Sprawdzanie plików i wersji Warsztat Menager...")
    for plik, wersja in wymagane_pliki.items():
        wynik = sprawdz_wersje(plik, wersja)
        print(wynik)

    print("\nGotowe. Upewnij się, że wszystkie pliki są zgodne.")

if __name__ == "__main__":
    sprawdz()
