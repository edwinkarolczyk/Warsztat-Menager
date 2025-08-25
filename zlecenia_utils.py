# Plik: zlecenia_utils.py
# Wersja pliku: 1.0.0

import json, os
from datetime import datetime

def przelicz_zapotrzebowanie(plik_produktu, ilosc):
    with open(plik_produktu, encoding="utf-8") as f:
        data = json.load(f)
    wynik = {}
    for el in data["komponenty"]:
        typ = el["typ"]
        total = ilosc * el["ilość_na_produkt"] * el["na_sztuke"]
        wynik[typ] = wynik.get(typ, 0) + total
    return wynik

def sprawdz_magazyn(plik_magazynu, zapotrzebowanie, prog=0.1):
    with open(plik_magazynu, encoding="utf-8") as f:
        magazyn = json.load(f)
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
    with open(os.path.join(folder, f"{numer}.json"), "w", encoding="utf-8") as f:
        json.dump(dane, f, indent=2, ensure_ascii=False)