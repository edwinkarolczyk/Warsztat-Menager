# Changelog

## Grok - Zmiany testowe (2026-05-13)

### Test commit od Groka (Code Admin)
- Dodano wpis w CHANGELOG jako test integracji z GitHub
- Potwierdzenie, że Grok może robić commity na branchu GROK

## Dzisiejsze zmiany - 2026-05-12

### ROOT / ścieżki danych
- Dodano widoczny pasek diagnostyczny pokazujący aktywne ścieżki:
  `ROOT`, `DATA` i `CONFIG`.
- Dodano pasek aktualnego modułu pokazujący, z jakiego pliku lub katalogu moduł czyta dane.
- Dodano ostrzeżenie `POZA ROOT!`, gdy moduł korzysta ze ścieżki spoza aktywnego ROOT.

### Moduły i źródła danych
- Podłączono diagnostykę źródła danych do modułów:
  Narzędzia, Maszyny, Dyspozycje / Zlecenia, Magazyn i Ustawienia.
- Naprawiono błędne źródło diagnostyczne w Dyspozycjach / Zleceniach, gdzie wcześniej używana była niezdefiniowana zmienna `storage`.
- Dyspozycje / Zlecenia pokazują teraz realną ścieżkę zwracaną przez `get_dyspozycje_path()`.

### GUI / układ programu
- Naprawiono problem, przez który moduł Maszyny wypychał dolną globalną stopkę poza widoczny obszar okna.
- Ograniczono panel Maszyn do właściwego kontenera modułu.
- Zmieniono kolejność pakowania `footer` i `content`, aby globalna stopka WM była zawsze rezerwowana na dole okna.

### Narzędzia
- Wykryto, że Narzędzia czytają plik:
  `C:\w-m\data\narzedzia\szablony_zadan.json`,
  ale plik ma `zadania=0`.
- Do dalszej naprawy pozostaje migracja albo uzupełnienie szablonów zadań w ROOT.

### Profile
- Wykryto niespójność ścieżki profili: część logiki może używać `<ROOT>\profiles.json` zamiast wymaganego `<ROOT>\data\profiles.json`.
- Do dalszej naprawy pozostaje wymuszenie aktywnej ścieżki profili na `<ROOT>\data\profiles.json`.
