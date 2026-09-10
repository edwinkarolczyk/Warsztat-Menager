# WM 1.0 — CHECKLISTA TESTÓW

Nie oznaczamy testu jako zaliczony bez wykonania go na aktualnej wersji. Na starcie WM 1.0.0 wszystkie poniższe pozycje wymagają świeżej weryfikacji.

## Smoke / lifecycle

| ID | Test | Stan |
|---|---|---|
| WM10-T001 | Start WM bez nieobsłużonych wyjątków | DO TESTU |
| WM10-T002 | Logowanie PIN i wejście do panelu | DO TESTU |
| WM10-T003 | Przejście kolejno przez główne moduły bez błędów Tcl/Tk | DO TESTU |
| WM10-T004 | Zamknięcie WM bez pozostawionych timerów/wyjątków | DO TESTU |
| WM10-T005 | Ponowne uruchomienie WM po normalnym zapisie danych | DO TESTU |

## Dane i zapisy

| ID | Test | Stan |
|---|---|---|
| WM10-T010 | Dodaj rekord -> restart -> rekord nadal poprawny | DO TESTU |
| WM10-T011 | Edytuj rekord -> restart -> zmiana nadal poprawna | DO TESTU |
| WM10-T012 | Refresh nie przywraca starej wartości | DO TESTU |
| WM10-T013 | Zapis trafia wyłącznie do poprawnego WM_ROOT | DO TESTU |
| WM10-T014 | Brak duplikatu po pojedynczej operacji użytkownika | DO TESTU |
| WM10-T015 | Uszkodzony/niepełny zapis nie niszczy poprzedniej poprawnej wersji danych | DO TESTU |
| WM10-T030 | Blokada zapisu Maszyn serializuje równoległe wejścia, a aktualizacja WMM zachowuje strukturę dokumentu i pozostałe rekordy | ZALICZONY — 1.0.1 CI |

## Moduły

| ID | Test | Stan |
|---|---|---|
| WM10-T020 | Profil / Brygadzista — otwarcie, refresh, uprawnienia | DO TESTU |
| WM10-T021 | Planista — nowe zlecenie i ponowny odczyt po restarcie | DO TESTU |
| WM10-T022 | Planista — Produkt -> Półprodukt -> Surowiec | DO TESTU |
| WM10-T023 | Maszyna — edycja podstawowych danych i ponowny odczyt | DO TESTU |
| WM10-T024 | Narzędzie — edycja, status, powiązania | DO TESTU |
| WM10-T025 | Dyspozycja — dodanie/edycja jako brygadzista | DO TESTU |
| WM10-T026 | Magazyn — odczyt, zapis, refresh, restart | DO TESTU |

## WM + WMM

| ID | Test | Stan |
|---|---|---|
| WMM-T001 | WMM łączy się z właściwym WM API | DO TESTU |
| WMM-T002 | Zmiana wykonana w WMM jest widoczna w WM po kontrolowanym refreshu | DO TESTU |
| WMM-T003 | Zdjęcie dodane z WMM trafia do właściwego rekordu | DO TESTU |
| WMM-T004 | Dwóch klientów edytuje różne rekordy jednocześnie bez utraty danych | DO TESTU |
| WMM-T005 | Dwóch klientów edytuje ten sam rekord — brak cichego nadpisania | DO TESTU |
| WMM-T006 | 3–5 klientów wykonuje równoległe operacje przez API | DO TESTU |
| WMM-T007 | Ponowiony request nie tworzy duplikatu | DO TESTU |
| WMM-T008 | WM desktop i WMM próbują zapisać ten sam obszar danych — brak utraty zmian/uszkodzenia JSON | DO TESTU |
| WMM-T009 | Restart WM/API w trakcie pracy klienta kończy się kontrolowanym błędem i poprawnym stanem danych | DO TESTU |

## Wynik CI dla WM 1.0.1

Commit kodu: `c6cde038220aed2d92eccee877bb9168896f856c`.

- `R07 Smoke` (`r07_smoke.yml`): **SUCCESS**.
- `R08 Smoke`: **SUCCESS**.
- Główny `R07 Smoke` (`ci.yml`): **SUCCESS**.
- Kompilacja całego repo: **SUCCESS**.
- Regresje Profil/obecności: **SUCCESS**.
- ROOT i DATA_ROOT: **SUCCESS**.
- Planista: **SUCCESS**.
- Integracja hali i Maszyn, wraz z `tests/test_machine_file_guard.py`: **SUCCESS**.
- Static checks: **SUCCESS**.

Nie oznacza to jeszcze zaliczenia scenariusza rzeczywistych dwóch procesów WM/WMM edytujących ten sam rekord z różnymi wersjami danych. Ten scenariusz pozostaje do osobnego testu i przyszłej obsługi konfliktów `revision`/409.

## Warunek wydania

WM 1.0.x uznajemy za stabilny dopiero wtedy, gdy wszystkie testy krytyczne są zielone, a pozostałe nie mają otwartych błędów o wysokim ryzyku utraty danych.
