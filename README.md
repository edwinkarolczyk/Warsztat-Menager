# Warsztat Menager (WM)

Ciemny, desktopowy system do zarządzania warsztatem (Python/Tkinter).
Moduły: **Maszyny, Narzędzia, Zlecenia, Magazyn, Serwis, Ustawienia**.

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

## Konfiguracja zmian
Plik `config.json` obsługuje pola:
- `zmiana_rano_start` / `zmiana_rano_end`
- `zmiana_pop_start` / `zmiana_pop_end`
- `rotacja_anchor_monday`

## Licencja
Wewnętrzny projekt (prywatny repozytorium) – do użytku w zespole.
