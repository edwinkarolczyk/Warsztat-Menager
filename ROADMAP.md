# Roadmap

## Wprowadzenie
Roadmapa projektu **Warsztat Menager** określa plan działania dla dalszego rozwoju i usprawniania aplikacji, bazując na wynikach audytu gałęzi `Rozwiniecie`. Celem dokumentu jest uporządkowanie prac – od pilnych poprawek jakości kodu po wdrożenie nowych funkcjonalności – tak, aby przygotować projekt do integracji z gałęzią `main` i zapewnić stabilny rozwój.

## Priorytety
- **Wysoki priorytet**
  - **Stabilność i bezpieczeństwo kodu** – usunięcie niebezpiecznych konstrukcji, poprawa obsługi wyjątków, porządek zależności.
  - **Testy i automatyzacja (CI)** – testy jednostkowe/integracyjne dla kluczowych funkcji, działający pipeline CI na każdy push/PR.
- **Średni priorytet**
  - **Architektura i jakość kodu** – wydzielenie warstwy serwisowej, standaryzacja stylu (lint/format), pre-commit.
  - **UX/UI** – potrójne potwierdzanie usunięcia, centralny motyw w `ui_theme.py`, czytelne komunikaty błędów.
  - **Dokumentacja** – README/USER_GUIDE/CONTRIBUTING, opis architektury.
- **Niski priorytet**
  - **Porządki w repo** – usunięcie starych backupów/artefaktów, aktualizacja `.gitignore`, ewent. reorganizacja katalogów.
  - **Drobne TODO/FIXME** – kosmetyka czytelności i spójności.

## Zadania szczegółowe

### 1) Stabilność i bezpieczeństwo (wysoki)
- Zastąpić `eval/exec` bezpiecznymi mechanizmami.
- Zastąpić `except:` na konkretne wyjątki + dodać logowanie.
- Rozciąć cykliczne importy; uporządkować warstwy (core/service vs GUI).
- Dodać testy krytycznych przypadków.
- Ustawić GitHub Actions: instalacja zależności → lint/format → testy.

### 2) Architektura i jakość (średni)
- Wydzielić moduł serwisowy (logika biznesowa) od GUI; komunikacja event-bus.
- Ujednolicić nagłówki i stopki plików (`# Plik: …`, `# Wersja: …`, `# ⏹ KONIEC KODU`).
- Pre-commit: Black + isort + Ruff/Flake8 (fail pipeline przy błędach).
- Walidacja JSON (JSON Schema) dla `config.json`, `maszyny.json`, `uzytkownicy.json`.
- Tkinter: jedna `mainloop()`, kontrola `.after()`, nie mieszać `pack`/`grid` w jednym kontenerze.

### 3) UX/UI (średni)
- Potrójne potwierdzenie kasowania (modal, opcj. timeout i ESC).
- Centralny motyw w `ui_theme.py`; zero „magic values” w widokach.
- Czytelne dialogi błędów, walidacje, spójne etykiety.

### 4) Dokumentacja (średni)
- `README.md`/`USER_GUIDE.md`: instalacja, uruchomienie, scenariusze.
- `CONTRIBUTING.md`: workflow gałęzi, konwencje commitów, jak uruchomić testy/CI.
- Docstringi w publicznych klasach/funkcjach; komentarze dla złożonych fragmentów.

### 5) Porządki w repo (niski)
- Usunąć/wykluczyć backupy, logi, build-artefakty; zaktualizować `.gitignore`.
- Dodać `config.sample.json` (bez sekretów) i opisać sposób użycia.
- (Opcjonalnie) uporządkować katalogi: `service/`, `gui/`, itd.

## Kamienie milowe
- **CI zielone na Rozwiniecie** – testy i lint przechodzą na push/PR.
- **Gotowość do merge z `main`** – stabilny kod, testy zielone, minimalny dług techniczny.
- **Pełna dokumentacja** – README/USER_GUIDE/CONTRIBUTING i opis architektury.
- **Wydanie 1.0** – tag, artefakt (np. EXE/Docker), nota wydania.

## W toku / Zrobione
- **W toku:** _(dopisywać bieżące zadania i osoby)_
- **Zrobione:** _(przenosić zadań po domknięciu, z datą i numerem commita/PR)_
