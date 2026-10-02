# WMT 1.0 — Warsztat Menager Tester

WMT jest osobnym programem kontrolnym dla Warsztat Menager. Nie zmienia kodu WM i nie wykonuje testów na produkcyjnym `WM_ROOT`.

## WMT 1.0 robi

- wykrywa repozytorium WM i zapisuje do raportu branch/commit Git,
- tworzy osobny `sandbox_root` dla każdej sesji,
- uruchamia WM z `WM_ROOT`, `WM_DATA_ROOT` i `WM_CONFIG_FILE` wskazującymi wyłącznie sandbox,
- sprawdza składnię wszystkich plików Python,
- sprawdza poprawność wszystkich plików JSON,
- uruchamia istniejące testy WM (`pytest`) i zamienia każdy test JUnit na osobny punkt raportu,
- ma osobny tryb testów kontraktów/integracji WMM,
- zapisuje raport `report.json` oraz czytelny `report.html`,
- porównuje wynik z poprzednią sesją i pokazuje nowe regresje,
- pozwala uruchomić WM w trybie obserwowanym na testowym ROOT.

## Tryby

- **Smoke** — krytyczne testy ROOT, narzędzi, zleceń, Planisty i WMM.
- **Pełny test** — wszystkie `tests/` oraz testy `test_*.py` z katalogu głównego repo.
- **WM ↔ WMM** — testy `test_wmm_*.py` oraz kontrakty Planisty/WMM.
- **WM obserwowany** — uruchamia prawdziwy `start.py` WM na izolowanym ROOT, widocznym normalnie na ekranie.

## Ważne

WMT 1.0 jest fundamentem pod automatycznego robota GUI. Obecny tryb „WM obserwowany” uruchamia prawdziwy WM na bezpiecznej kopii danych, ale nie klika jeszcze samodzielnie całego GUI. Automatyczne scenariusze GUI będą dokładane jako osobna warstwa bez zmiany istniejącego silnika raportów.

## Kod źródłowy na gałęzi WMT-1.0

Ze względów technicznych źródło testera jest przechowywane jako `WMT.py.gz.b64`. `build_wmt.bat` i GitHub Actions automatycznie odtwarzają `WMT.py` przed buildem.

## Budowa WMT.exe

Uruchom `build_wmt.bat`. Wymagany Python 3.13. Skrypt odtwarza źródło, instaluje PyInstaller i tworzy `dist\WMT.exe`.
