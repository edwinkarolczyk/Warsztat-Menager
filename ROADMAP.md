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

<!-- START: TRYB NAPRAWCZY Q4-2025 -->
## TRYB NAPRAWCZY (Q4-2025) — bez nowych funkcji
> Data: 2025-09-30 (Europe/Warsaw)  
> Cel: naprawy, dopięcie logiki, pełna spójność; **żadnych nowych funkcji**.  
> Zasady wersjonowania: mała `*.*.+1`, średnia `*. +1 .0`, duża `+1.0.0`.  
> Logi: **konsola + `logs/wm.log` z rotacją 5×5 MB**.

### 🔔 ALERT
🔴 **STOP dla nowych funkcji.** Pracujemy wyłącznie nad naprawami, ładem i spójnością gałęzi **Rozwiniecie**.

---

### 0) Rdzeń / Ustawienia / Logowanie — 🟡 70%
- [ ] Zbiorczy fix `_TclError` (scroll/`after()` na zniszczonych widgetach)
- [ ] Zawężenie `except Exception` + stałe logowanie `[WM-ERR]/[WM-DBG]`
- [ ] **Motywy** – pełna spójność (Logowanie, Panel, wszystkie dialogi)
- [ ] Logi: konsola + `logs/wm.log` (rotacja 5×5 MB)
**Definition of Done:** start bez wyjątków; motywy spójne; wszystkie błędy/akcje → log; gdzie trzeba okna błędów.

### 1) Narzędzia — 🟠 65%
- [ ] Walidacja formularzy (puste pola → okno błędu)
- [ ] Każdy błąd dod/edycja → **messagebox.showerror** + log
- [ ] Historia NN↔SN: zabezpieczenie anty-duplikat (gdy występują)
**DoD:** brak duplikatów; jasne komunikaty; pełne logowanie.

### 2) Magazyn — 🟠 60%
- [ ] **Źródło prawdy** z Ustawień → jednolite ładowanie stanów
- [ ] Błąd wczytania → **okno + log**
- [ ] (Jeśli potrzebne) informacja „Trwa przetwarzanie…” bez blokowania GUI
**DoD:** stabilne odświeżanie; przewidywalne komunikaty.

### 3) Maszyny — 🔴 50% (PRIORYTET)
- [ ] **Źródło prawdy** (klucz w Ustawieniach) wskazuje **jedyny** plik danych
- [ ] **Scalenie duplikatów** (po ustalonym polu) i **usunięcie** zbędnych plików
- [ ] Brak renderera „hali” → **okno błędu + log** (bez crasha)
**DoD:** jedno źródło danych; poprawna edycja/ładowanie; błędy widoczne.

### 4) Zlecenia — 🟢 75%
- [ ] Walidacja kreatora (puste pola → okno)
- [ ] Bezpieczne odświeżanie listy (zwalnianie `after()` przy zamknięciu)
- [ ] Każdy błąd → okno + log
**DoD:** lista i detale działają stabilnie.

### 5) Profile / Role — 🟡 55%
- [ ] „Profil” widoczny **dla wszystkich ról**
- [ ] „Ustawienia” widoczne **dla Admin + Brygadzista**
**DoD:** spójna widoczność akcji w całym GUI.

---

### Wyłączenia (deprecjacje/usunięcia)
- [x] **Serwis** — **usunąć** moduł z kodu i manifestów
- [x] **Hala** — **usunąć** (pozostaje tylko „Maszyny”)
**DoD:** brak importów/odwołań; brak pozycji w menu/manifeście.

### Porządki repo
- [ ] Usunąć zdublowane dane maszyn po scaleniu (zostaje jeden plik)
- [ ] Uzupełnić `.gitignore` (logi, tymczasowe, lokalne konfigi)
- [ ] Przenieść/wyciąć stare logi/backupy/README_DEBUG/PATCH (jeśli obecne)

---

### Paczki naprawcze (kolejność realizacji)
1. **#R-00 – Usunięcia**: Serwis/Hala (manifest, importy, menu) — *średnia*
2. **#R-01 – Rdzeń/Ustawienia/Logowanie**: `_TclError` + motywy + logi — *średnia*
3. **#R-03 – Maszyny**: źródło prawdy + scalenie duplikatów — *średnia/duża*
4. **#R-05 – Zlecenia**: walidacje + odświeżanie + okna błędów — *mała/średnia*
5. **#R-06 – Narzędzia**: walidacje + okna błędów + historia — *średnia*

> Aktualizujemy ten blok po każdym zaakceptowanym pakiecie (checklisty, % i notatki).
<!-- END: TRYB NAPRAWCZY Q4-2025 -->
