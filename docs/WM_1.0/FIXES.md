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
| WM10-002 | 1.0.7 | WYSOKI | ID użytkowników | Zachować trwałe `user_id` przy zmianie loginu: przed zmianą uzupełnić brakujące `user_id` w historycznych rekordach tej osoby bez hurtowej migracji i bez nadpisywania istniejących ID. | NAPRAWIONE | `f70d8ce1`, `9553659e`, `8f96719d`, `65aa7d24` |
| WM10-003 | 1.0.8 | WYSOKI | Grafik / zmiany | Ujednolicić godziny zmian w Logowaniu, Obecności i pasku postępu z kanonicznym `grafiki.shifts_schedule._shift_times()` oraz zabezpieczyć przed legacy nadpisaniem resolvera logowania. | NAPRAWIONE | `b21796d9`, `9e2e9d70`, `6c9182f6`, `ed394094`, `e1a581df`, `7fcd1e6d` |
| WM10-004 | 1.0.x | ŚREDNI | Profil / Brygadzista | Zweryfikować i ewentualnie poprawić przygotowanie panelu Brygadzisty po wejściu do Profilu, aby pierwszy klik nie powodował odczuwalnego budowania widoku. | DO AUDYTU | — |
| WM10-005 | 1.0.x | WYSOKI | Planista | Test pełnego przepływu Zlecenie -> Produkt -> Półprodukt -> Surowiec, zapis/restart/refresh i jednoznaczność identyfikatorów. | DO AUDYTU | — |
| WM10-005A | 1.0.5 | KRYTYCZNY | Planista / WMM | Zabezpieczyć równoczesne tworzenie zleceń przez desktop WM i WMM wspólną blokadą obejmującą generowanie ID oraz zapis zlecenia. | NAPRAWIONE | `4ec03658`, `227b9739`, `2a4467fe` |
| WM10-005B | 1.0.6 | KRYTYCZNY | Planista / Magazyn | Serializować pełne transakcje odczyt -> zmiana -> zapis kanonicznego Magazynu dla rezerwacji i pozostałych mutatorów, aby równoległe procesy nie traciły aktualizacji. | NAPRAWIONE | `b8a3fa84` |
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

## WM10-005A — zamknięcie

- Wersja: **1.0.5**
- Data: **2026-09-11**
- Decyzja użytkownika: zaakceptowano wyłącznie wspólną blokadę tworzenia zlecenia WM <-> WMM, test współbieżności oraz podbicie wersji; bez zmian UI, BOM i logiki rezerwacji.
- Implementacja: `order_create_lock(...)` korzysta ze wspólnego guarda `data/zlecenia/_order_sequence`; desktop Planisty obejmuje blokadą cały cykl tworzenia wraz ze snapshotem/rollbackiem, a WMM używa tego samego guarda.
- Test: `tests/test_order_create_guard.py` równocześnie uruchamia tworzenie zlecenia z desktopu i WMM, wymusza okno wyścigu podczas pobierania numeru i potwierdza dwa różne ID oraz dwa zapisane pliki JSON.
- Główny CI uruchamia test w kroku `Run production planning regressions`; wszystkie kroki tego workflow zakończyły się powodzeniem.
- Wynik CI: **SUCCESS** dla commita `2a4467fe9ed1921ba94ba6d0756cde989b7d08db` (run `34576085995`).
- Ograniczenie: 1.0.5 nie zmienia ogólnej współbieżności rezerwacji magazynowych ani rollbacku magazynu między niezależnymi operacjami; ten temat pozostaje osobnym fixem po 1.0.5.

## WM10-005B — zamknięcie

- Wersja: **1.0.6**
- Data: **2026-09-11**
- Decyzja użytkownika: zaakceptowano podbicie stopki/wersji i kolejny fix stabilizacyjny; bez zmian UI, modelu danych i kontraktu API WMM.
- Kompatybilność: **WMM 0.5.9** pozostaje zgodne z WM 1.0.6; nie zmieniono endpointów, payloadów ani formatu danych używanego przez aplikację mobilną.
- Implementacja: `warehouse_transaction_lock(...)` serializuje pełny cykl odczyt -> zmiana -> zapis kanonicznego Magazynu. Publiczne mutatory magazynowe instalowane przez runtime Planisty korzystają ze wspólnej blokady między procesami.
- Test: `tests/test_planista_stock_runtime.py::test_parallel_reservations_share_one_cross_process_transaction_lock` uruchamia dwa osobne procesy, które równocześnie próbują zarezerwować po 6 z dostępnych 10 jednostek; wynik musi wynieść 6 + 4, a końcowa rezerwacja dokładnie 10.
- Główny CI przeszedł krok `Run production planning regressions` oraz wszystkie pozostałe kroki.
- Wynik CI: **SUCCESS** dla commita `b8a3fa8427db9572d346b06381b8b83d5fc88a7f` (run `34577264917`); workflowy R07 i R08 również zakończyły się **SUCCESS**.
- Ograniczenie: 1.0.6 nie wprowadza semantycznego wersjonowania rekordów (`revision`/ETag/409) dla konfliktów edycji; to pozostaje osobnym zadaniem.

## WM10-002 — zamknięcie

- Wersja: **1.0.7**
- Data: **2026-09-11**
- Decyzja użytkownika: po raporcie stabilizacji zaakceptowano dalszą pracę nad spójnością `user_id` vs login bez zmian UI i bez hurtowej migracji danych.
- Audyt potwierdził, że nowe wpisy Obecności i Urlopów już zapisują trwałe `user_id` oraz `login_snapshot`; luka dotyczyła głównie starszych rekordów i danych zapisanych historycznie po loginie.
- Implementacja: przed faktyczną zmianą loginu `profile_identity_runtime.py` uzupełnia brakujący `user_id` tylko w rekordach tej jednej osoby: Opinie, Urlopy, wnioski urlopowe, Obecność, audit Obecności i historia administracyjna Profilu. Stary login pozostaje jako snapshot/czytelna historia.
- Istniejący `user_id` nigdy nie jest nadpisywany. Nie wykonywana jest migracja całej bazy przy starcie programu.
- Test: `tests/test_profile_identity_runtime.py` sprawdza dopisanie `USR-0042` do rekordów legacy oraz ochronę istniejącego obcego ID.
- Test został dopięty do głównego kroku `Run profile workforce regressions`.
- Wynik CI: **SUCCESS** dla commita `65aa7d24da06018dc99473d94c90cd8a9a667599` (run `34579591256`); R07 i R08 również **SUCCESS**.
- Kompatybilność: zmiana nie rusza endpointów ani formatu komunikacji WMM; WMM 0.5.9 pozostaje zgodne.

## WM10-003 — zamknięcie

- Wersja: **1.0.8**
- Data: **2026-09-11**
- Decyzja użytkownika: zaakceptowano wyłącznie wspólne źródło godzin dla Logowania, Obecności i paska postępu zmiany, test niestandardowych godzin oraz podbicie wersji; bez zmian modelu danych, trybów grafiku i WMM.
- Implementacja: `services/attendance_service.py`, `gui_logowanie.py` i `gui/widgets_user_footer.py` pobierają granice zmian z `grafiki.shifts_schedule._shift_times()`.
- Resolver `_slot_now()` na ekranie logowania jest oznaczony jako kanoniczny, dzięki czemu starszy runtime Profilu nie zastępuje go własnymi godzinami 05:00/14:00/23:59.
- Test: `tests/test_shift_hours_sync.py` sprawdza wspólne zachowanie dla godzin 05:30–13:30 oraz 13:30–21:30, w tym granice zmian i 50% postępu pierwszej zmiany o 09:30.
- Test został dopięty do głównego kroku `Run profile workforce regressions`.
- Wynik CI: **SUCCESS** dla commita `7fcd1e6d14a2597040e643e48f7b6f606a005ff8` (run `34583503458`); R07 i R08 również **SUCCESS**.
- Ograniczenie: 1.0.8 nie zmienia nazw istniejących etykiet paska (`RANO`, `POŁUDNIE`, `NOC`) ani wyglądu UI; ujednolica wyłącznie godziny i logikę ich użycia.

## Zasada zamykania fixa

Wpisu nie usuwamy po naprawie. Uzupełniamy: dokładną wersję, status `NAPRAWIONE`, commit, datę oraz test regresyjny. Dzięki temu historia napraw pozostaje czytelna bez szukania po starych rozmowach.
