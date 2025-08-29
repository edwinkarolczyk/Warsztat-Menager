# Plik: test_kreator_wersji.py
# Wersja pliku: 0.2.0
# Zmiany:
# - Porównuje plik kodu z wymaganiami wersji (zdefiniowanymi w pliku JSON lub wewnętrznie)
# - Zwraca wynik testu zamiast zapisywać do pliku
# - Używa asercji `assert` do weryfikacji wyników
#
# Autor: AI – Idea: Edwin Karolczyk

import os
from typing import Dict, List


def sprawdz_wymagania(plik: str, wymagania: List[str]) -> Dict[str, bool]:
    if not os.path.exists(plik):
        raise FileNotFoundError(f"Plik {plik} nie istnieje!")
    with open(plik, "r", encoding="utf-8") as f:
        kod = f.read()
    return {linia: linia in kod for linia in wymagania}


def test_gui_logowanie_spelnia_wymagania():
    plik = "gui/logowanie.py"
    wymagania = [
        "def ekran_logowania(root=None, on_login=None, update_available=False):",
        "entry_pin = ttk.Entry",
        "img = Image.open",
        "root.attributes(\"-fullscreen\", True)",
        "str(login_key).strip().lower() == login",
        "str(dane.get(\"pin\", \"\")).strip() == pin",
    ]
    wyniki = sprawdz_wymagania(plik, wymagania)
    brakujace = [linia for linia, ok in wyniki.items() if not ok]
    assert not brakujace, f"Brakujące wymagania: {', '.join(brakujace)}"

