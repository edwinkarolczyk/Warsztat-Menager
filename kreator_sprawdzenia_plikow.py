# Plik: kreator_sprawdzenia.py
# Wersja: 1.0
# Opis: Sprawdza obecność i zgodność plików programu Warsztat Menager

import os
import hashlib
from utils.path_utils import cfg_path

# Lista wymaganych plików z sumami kontrolnymi SHA256 (mogą być uzupełniane)
wymagane_pliki = {
    "start.py": None,
    "gui_logowanie.py": None,
    "gui_panel.py": None,
    "layout_prosty.py": None,
    "ustawienia_systemu.py": None,
    "uzytkownicy.json": None,
    cfg_path("config.json"): None,
}

def oblicz_sha256(nazwa):
    try:
        with open(nazwa, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return None

def sprawdz():
    print("\n🛠 Sprawdzanie plików Warsztat Menager...")
    brakujace = []
    for plik in wymagane_pliki:
        if not os.path.exists(plik):
            print(f"❌ Brakuje: {plik}")
            brakujace.append(plik)
        else:
            print(f"✅ Jest: {plik}")

    if not brakujace:
        print("\n✅ Wszystkie wymagane pliki są obecne.")
    else:
        print("\n⚠️ Uzupełnij brakujące pliki przed uruchomieniem programu.")

    print("\n(Jeśli chcesz dodać sprawdzanie sum kontrolnych, uzupełnij słownik 'wymagane_pliki')")

if __name__ == "__main__":
    sprawdz()
