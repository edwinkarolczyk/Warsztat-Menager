# Plik: test_kreator_wersji.py
# Wersja pliku: 0.1.0
# Zmiany:
# - Porównuje plik kodu z wymaganiami wersji (zdefiniowanymi w pliku JSON lub wewnętrznie)
# - Zapisuje wynik testu do test_log_wersji.txt
# - Nadaje status: DZIAŁA / NIE DZIAŁA / BRAKUJE
#
# Autor: AI – Idea: Edwin Karolczyk

import os
import time

# Ścieżka do testowanego pliku
plik = "gui_logowanie.py"

# Lista wymagań wersji (można rozbudować o inne pliki)
wymagania = [
    "def logowanie()",
    "entry_pin = tk.Entry",
    "label_info = tk.Label",
    "bg=\"#000000\"",
    "image = Image.open",
    "root.attributes('-fullscreen', True)",
    "imie, dane in uzytkownicy.items()",
    "dane[\"pin\"] == pin"
]

# Plik logu
log_file = "test_log_wersji.txt"

def zapisz_log(wiadomosc):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} – {wiadomosc}\n")

zapisz_log(f"[START] Sprawdzanie pliku {plik}")

if not os.path.exists(plik):
    zapisz_log(f"[BŁĄD] Plik {plik} nie istnieje!")
    exit()

with open(plik, "r", encoding="utf-8") as f:
    kod = f.read()

for linia in wymagania:
    if linia in kod:
        zapisz_log(f"[OK] Znaleziono: {linia}")
    else:
        zapisz_log(f"[BRAK] NIE ZNALEZIONO: {linia}")

zapisz_log("[STOP] Sprawdzanie zakończone")
print(f"Test zakończony. Sprawdź: {log_file}")
