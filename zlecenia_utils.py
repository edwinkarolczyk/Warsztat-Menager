# Plik: zlecenia_utils.py
# Wersja pliku: 1.0.0

import os
from io_utils import read_json, write_json
from datetime import datetime

def przelicz_zapotrzebowanie(plik_produktu, ilosc):
    data = read_json(plik_produktu) or {}
    wynik = {}
    for el in data["komponenty"]:
        typ = el["typ"]
        total = ilosc * el["ilość_na_produkt"] * el["na_sztuke"]
        wynik[typ] = wynik.get(typ, 0) + total
    return wynik

def sprawdz_magazyn(plik_magazynu, zapotrzebowanie, prog=0.1):
    magazyn = read_json(plik_magazynu) or {}
    alerty = []
    zuzycie = []
    for typ, potrzebne in zapotrzebowanie.items():
        if typ not in magazyn:
            alerty.append(f"{typ} (brak w magazynie)")
            continue
        dostepne = magazyn[typ]["ilość"] * magazyn[typ]["długość_sztuki"]
        if potrzebne > dostepne:
            alerty.append(f"{typ} (potrzeba {potrzebne}, dostępne {dostepne})")
        elif (dostepne - potrzebne) < dostepne * prog:
            zuzycie.append(f"{typ} – UWAGA: niski stan po zużyciu")
    return (len(alerty) == 0), ", ".join(alerty), ", ".join(zuzycie)

def zapisz_zlecenie(folder, produkt, ilosc):
    numer = f"ZL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    dane = {
        "numer": numer,
        "typ": "produkcja",
        "produkt": produkt,
        "ilość": ilosc,
        "status": "oczekujące",
        "data_start": datetime.now().strftime("%Y-%m-%d"),
        "data_koniec": "",
        "użytkownik": "Edwin",
        "komentarze": []
    }
    write_json(os.path.join(folder, f"{numer}.json"), dane)
