# WM 1.0 — REJESTR POPRAWEK

Ten plik jest bieżącym źródłem prawdy dla stabilizacji WM 1.0.x. Stare roadmapy i tickety RC1 pozostają w `docs/` jako historia i nie są automatycznie traktowane jako aktualne.

## Statusy

- `DO AUDYTU` — temat znany, ale wymaga potwierdzenia w aktualnym kodzie.
- `DO ZROBIENIA` — problem potwierdzony i zaakceptowany do naprawy.
- `W TRAKCIE` — trwa implementacja.
- `DO TESTU` — implementacja gotowa, oczekuje na test.
- `NAPRAWIONE` — fix wdrożony i przetestowany.
- `ODRZUCONE` — świadomie nie wdrażamy.

## Rejestr

| ID | Planowana wersja | Priorytet | Obszar | Opis | Status | Commit |
|---|---:|---|---|---|---|---|
| WM10-001 | 1.0.x | KRYTYCZNY | Zapisy / ROOT | Przejść wszystkie główne moduły pod kątem niespójnych ścieżek, podwójnych zapisów, zapisu poza ROOT i trwałości po restarcie. | DO AUDYTU | — |
| WM10-001A | 1.0.1 | KRYTYCZNY | Maszyny / WMM | Zabezpieczyć wspólny plik `data/maszyny/maszyny.json`: blokada między procesami WM/WMM, pełny cykl WMM odczyt -> zmiana -> zapis pod blokadą, bez zmiany formatu JSON. | NAPRAWIONE | `54ee84bf`, `046109b3`, `c6cde038` |
| WM10-001B | 1.0.4 | KRYTYCZNY | Narzędzia / WMM | Zabezpieczyć pojedyncze `data/narzedzia/<nr>.json`: wspólna blokada WM/WMM i atomowy zapis pliku, bez zmiany formatu danych i UI. | NAPRAWIONE | `4c0ff529`, `234583b7`, `dc738f0e`, `41a33c28` |
| WM10-002 | 1.0.x | WYSOKI | ID użytkowników | Sprawdzić miejsca nadal bazujące na loginie zamiast trwałego `user_id`, szczególnie historia/obecność/opinie i powiązane zapisy. | DO AUDYTU | — |
| WM10-003 | 1.0.x | WYSOKI | Grafik / zmiany | Potwierdzić jedno wspólne źródło godzin zmian i trybów grafiku, bez duplikowania konfiguracji. | DO AUDYTU | — |
| WM10-004 | 1.0.x | ŚREDNI | Profil / Brygadzista | Zweryfikować i ewentualnie poprawić przygotowanie panelu Brygadzisty po wejściu do Profilu, aby pierwszy klik nie powodował odczuwalnego budowania widoku. | DO AUDYTU | — |
| WM10-005 | 1.0.x | WYSOKI | Planista | Test pełnego przepływu Zlecenie -> Produkt -> Półprodukt -> Surowiec, zapis/restart/refresh i jednoznaczność identyfikatorów. | DO AUDYTU | — |
| WM10-006 | 1.0.x | WYSOKI | Dyspozycje / role | Potwierdzić pełne uprawnienia brygadzisty oraz ograniczenia zwykłych użytkowników przy dodawaniu i edycji dyspozycji. | DO AUDYTU | — |
| WM10-006B | 1.0.3 | KRYTYCZNY | Dyspozycje / zapis | Zabezpieczyć `data/dyspozycje/dyspozycje.json`: wspólna blokada WM/WMM dla pełnej transakcji odczyt -> zmiana -> zapis oraz atomowy zapis `tmp -> os.replace`, bez zmiany formatu JSON. | NAPRAWIONE | `52f472f0`, `ad71b90a`, `ec5c4d87` |
| WM10-007 | 1.0.x | ŚREDNI | Maszyny | Dokończyć audyt edytora maszyny: zapis, lokalizacja, sekcje danych, zdjęcia/dokumenty i ergonomia bez przebudowy architektury. | DO AUDYTU | — |
| WM10-008 | 1.0.x | ŚREDNI | UI / lifecycle | Przejść ciężkie widoki pod kątem zbędnych pełnych refreshy, wielokrotnego skanowania katalogów oraz nieanulowanych `after()`. | DO AUDYTU | — |
| WM10-009 | 1.0.x | ŚREDNI | Pomoc `!` | Przy kolejnych poprawianych ekranach stosować wspólny mechanizm pomocy kontekstowej `!` przy istotnych polach i akcjach, maks. dwa krótkie zdania. | DO AUDYTU | — |
| WMM-001 | osobna wersja WMM | KRYTYCZNY | Współbieżność | Zabezpieczyć konflikt równoczesnej edycji tego samego rekordu przez kilku klientów; preferowane `revision`/ETag i odpowiedź 409 przy starych danych. | DO AUDYTU | — |
| WMM-002 | osobna wersja WMM | KRYTYCZNY | Zapis WM <-> WMM | Potwierdzić, że desktop WM i API nie mogą równocześnie nadpisać tego samego pliku/rekordu; fizyczne blokady Maszyn, Dyspozycji i pojedynczych plików Narzędzi są już wdrożone. | DO AUDYTU | `54ee84bf` (Maszyny), `52f472f0` (Dyspozycje), `41a33c28` (Narzędzia) |
| WMM-003 | osobna wersja WMM | WYSOKI | Idempotencja | Ponowienie requestu nie może tworzyć duplikatu zlecenia, zdarzenia ani zdjęcia. | DO AUDYTU | — |
| WMM-004 | osobna wersja WMM | WYSOKI | Historia | Każda operacja zapisu powinna być identyfikowalna: użytkownik, czas, operacja i — gdy potrzebne — urządzenie/sesja. | DO AUDYTU | — |
| WMM-005 | osobna wersja WMM | WYSOKI | Test współbieżny | Test 3–5 klientów WMM jednocześnie: odczyt, zmiana statusów, zdjęcia, dyspozycje i konflikt tej samej pozycji. | DO AUDYTU | — |

## WM10-001A — zamknięcie

- Wersja: **1.0.1**
- Data: **2026-09-10**
- Decyzja użytkownika: zaakceptowano wyłącznie zabezpieczenie zapisu Maszyn WM <-> WMM, bez UI i bez zmian modelu danych.
- Implementacja: wspólna blokada pliku Maszyn dla procesu WM i WMM; WMM blokuje pełny cykl read-modify-write.
- Test: `tests/test_machine_file_guard.py` + pełny `ci.yml`.
- Wynik CI: **SUCCESS** dla commita `c6cde038220aed2d92eccee877bb9168896f856c`.
- Ograniczenie: wykrywanie semantycznego konfliktu starej wersji rekordu (`revision`/409) nie należy do 1.0.1 i pozostaje osobnym przyszłym fixem.

## WM10-006B — zamknięcie

- Wersja: **1.0.3**
- Data: **2026-09-11**
- Decyzja użytkownika: zaakceptowano wyłącznie zabezpieczenie zapisu Dyspozycji, zapis atomowy, test regresyjny, wersję 1.0.3 i wyrównanie rejestru stabilizacji.
- Implementacja: istniejący `file_write_lock(...)` chroni pełne transakcje `add`, `update`, `delete` i zmiany statusu; zapis kończy się atomowym `os.replace`.
- Format `dyspozycje.json` nie został zmieniony. UI i logika przejść statusów nie zostały rozszerzone.
- Test: `tests/test_dyspozycje_store_write_guard.py` sprawdza 16 równoległych zapisów bez utraty rekordów oraz zachowanie poprzedniego poprawnego JSON po błędzie `os.replace`.
- Główny CI uruchamia ten test jako osobny krok `Run disposition write guard regressions`.
- Wynik CI: **SUCCESS** dla commita `ec5c4d87aa2b4fd4e5eb35c13c6edbe95eb6503e`.
- Ograniczenie: ten fix nie rozwiązuje semantycznego konfliktu dwóch klientów edytujących ten sam rekord na podstawie starej wersji danych; `revision`/ETag/409 pozostaje osobnym zadaniem.

## WM10-001B — zamknięcie

- Wersja: **1.0.4**
- Data: **2026-09-11**
- Decyzja użytkownika: zaakceptowano zabezpieczenie fizycznych zapisów pojedynczych plików Narzędzi WM <-> WMM; historia operacji WMM i widoczna informacja „kto edytuje” zostały świadomie odłożone.
- Implementacja: `utils_json.safe_write_json(...)` rozpoznaje tylko numeryczne pliki JSON bezpośrednio w katalogu `narzedzia` i zapisuje je pod wspólnym `file_write_lock(...)` oraz atomowym `os.replace`.
- `wm_tools_helpers.save_tool_json(...)` używa tego samego chronionego writer-a, więc zapisy zadań narzędzia nie omijają blokady.
- WMM już chroniło `_update_tool(...)` tym samym mechanizmem; 1.0.4 dopięło stronę desktopowego WM.
- Plik zbiorczy `narzedzia.json`, format danych i UI nie zostały zmienione.
- Test: `tests/test_tool_file_guard.py` sprawdza oczekiwanie desktopowego zapisu na wspólną blokadę, zachowanie poprzedniego JSON po błędzie `os.replace` i użycie tej samej blokady przez WMM.
- Główny CI uruchamia ten test jako osobny krok `Run tool write guard regressions`.
- Wynik CI: **SUCCESS** dla commita `41a33c28d7c3a5e9a2af6ff6a98312741043a297`.
- Ograniczenie: fizyczna blokada nie chroni przed zapisaniem starego formularza po wcześniejszej nowszej zmianie z WMM; obsługa `revision`/ETag/409 lub soft-lock/presence pozostaje osobnym zadaniem.

## Zasada zamykania fixa

Wpisu nie usuwamy po naprawie. Uzupełniamy: dokładną wersję, status `NAPRAWIONE`, commit, datę oraz test regresyjny. Dzięki temu historia napraw pozostaje czytelna bez szukania po starych rozmowach.
