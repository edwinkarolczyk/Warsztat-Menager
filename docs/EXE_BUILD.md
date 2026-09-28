# WM — build EXE

To jest warstwa wydania Windows. Nie zmienia logiki modułów WM ani danych użytkownika.

## Źródło wersji

Jedynym źródłem wersji aplikacji pozostaje `__version__.py`.
Numer ten trafia również do właściwości pliku `WarsztatMenager.exe`.

## Ikona

Build korzysta z `11.ico`. Plik musi być prawdziwym wielorozdzielczym ICO i zawierać co najmniej 16, 32, 48 i 256 px.
`tools/generate_windows_version_info.py` sprawdza ikonę przed buildem.

## Build lokalny

Na Windows:

1. zainstaluj Python 3.13,
2. `py -3.13 -m pip install -r requirements-exe.txt`,
3. uruchom `build_wm_exe.bat`.

Wynik:
`dist/WarsztatMenager/WarsztatMenager.exe`

Build jest typu **onedir**. Biblioteki i zasoby pozostają obok EXE. Jest to celowe przed wdrożeniem instalatora i aktualizatora.

## GitHub Actions

Workflow `WM EXE Build` tworzy kompletny build Windows, paczkę ZIP oraz SHA-256.
Na tym etapie artefakt jest testowym buildem gałęzi `Rozwiniecie`, a nie wydaniem Stable.

## Dane

Build EXE nie może być traktowany jako kopia danych użytkownika. Docelowy instalator i aktualizator muszą zachować istniejący WM_ROOT/DATA_ROOT i nie usuwać danych.
