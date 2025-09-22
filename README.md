# Warsztat Menager (WM)
👉 Zobacz plan rozwoju: [ROADMAP.md](./ROADMAP.md)

Ciemny, desktopowy system do zarządzania warsztatem (Python/Tkinter).
Moduły: **Maszyny, Narzędzia, Zlecenia, Magazyn, Serwis, Ustawienia**.
Narzędzia mogą mieć przypisane zdjęcie oraz plik DXF z automatycznie
generowaną miniaturą.

Profile użytkowników mogą zawierać listę `disabled_modules`, która
pozwala ukryć wybrane moduły panelu dla danego loginu.

Formularze zarządzania surowcami, półproduktami i produktami znajdują się
bezpośrednio w zakładce **Ustawienia → Magazyn i BOM**, bez potrzeby
otwierania dodatkowego okna.

## Szybki start (dev)
```bash
py -3 start.py
```

## Instalacja
```bash
pip install -r requirements.txt
py -3 start.py
```

Plik `requirements.txt` zawiera minimalny zestaw bibliotek potrzebnych do uruchomienia aplikacji.

## Struktura katalogów (skrót)
```
.
├── start.py
├── gui_*.py
├── data/
├── logi/
└── README.md
```

> Uwaga: `config.json` nie trafia do repo (jest w `.gitignore`). Komitujemy `config.sample.json` z bezpiecznymi wartościami.

## Ustawienia
- Okno ustawień otworzysz z menu wybierając **Ustawienia...**.
- Schemat opcji znajduje się w pliku `settings_schema.json`.
- Kopie zapasowe pliku `config.json` trafiają do katalogu `backup_wersji/`.

## Konfiguracja zmian
Plik `config.json` obsługuje pola:
- `zmiana_rano_start` / `zmiana_rano_end`
- `zmiana_pop_start` / `zmiana_pop_end`
- `rotacja_anchor_monday`

## Licencja
Wewnętrzny projekt (prywatny repozytorium) – do użytku w zespole.
