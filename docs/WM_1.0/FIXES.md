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
| WM10-002 | 1.0.x | WYSOKI | ID użytkowników | Sprawdzić miejsca nadal bazujące na loginie zamiast trwałego `user_id`, szczególnie historia/obecność/opinie i powiązane zapisy. | DO AUDYTU | — |
| WM10-003 | 1.0.x | WYSOKI | Grafik / zmiany | Potwierdzić jedno wspólne źródło godzin zmian i trybów grafiku, bez duplikowania konfiguracji. | DO AUDYTU | — |
| WM10-004 | 1.0.x | ŚREDNI | Profil / Brygadzista | Zweryfikować i ewentualnie poprawić przygotowanie panelu Brygadzisty po wejściu do Profilu, aby pierwszy klik nie powodował odczuwalnego budowania widoku. | DO AUDYTU | — |
| WM10-005 | 1.0.x | WYSOKI | Planista | Test pełnego przepływu Zlecenie -> Produkt -> Półprodukt -> Surowiec, zapis/restart/refresh i jednoznaczność identyfikatorów. | DO AUDYTU | — |
| WM10-006 | 1.0.x | WYSOKI | Dyspozycje / role | Potwierdzić pełne uprawnienia brygadzisty oraz ograniczenia zwykłych użytkowników przy dodawaniu i edycji dyspozycji. | DO AUDYTU | — |
| WM10-007 | 1.0.x | ŚREDNI | Maszyny | Dokończyć audyt edytora maszyny: zapis, lokalizacja, sekcje danych, zdjęcia/dokumenty i ergonomia bez przebudowy architektury. | DO AUDYTU | — |
| WM10-008 | 1.0.x | ŚREDNI | UI / lifecycle | Przejść ciężkie widoki pod kątem zbędnych pełnych refreshy, wielokrotnego skanowania katalogów oraz nieanulowanych `after()`. | DO AUDYTU | — |
| WM10-009 | 1.0.x | ŚREDNI | Pomoc `!` | Przy kolejnych poprawianych ekranach stosować wspólny mechanizm pomocy kontekstowej `!` przy istotnych polach i akcjach, maks. dwa krótkie zdania. | DO AUDYTU | — |
| WMM-001 | osobna wersja WMM | KRYTYCZNY | Współbieżność | Zabezpieczyć konflikt równoczesnej edycji tego samego rekordu przez kilku klientów; preferowane `revision`/ETag i odpowiedź 409 przy starych danych. | DO AUDYTU | — |
| WMM-002 | osobna wersja WMM | KRYTYCZNY | Zapis WM <-> WMM | Potwierdzić, że desktop WM i API nie mogą równocześnie nadpisać tego samego pliku/rekordu; dążyć do wspólnej warstwy store/service i wspólnej blokady. | DO AUDYTU | — |
| WMM-003 | osobna wersja WMM | WYSOKI | Idempotencja | Ponowienie requestu nie może tworzyć duplikatu zlecenia, zdarzenia ani zdjęcia. | DO AUDYTU | — |
| WMM-004 | osobna wersja WMM | WYSOKI | Historia | Każda operacja zapisu powinna być identyfikowalna: użytkownik, czas, operacja i — gdy potrzebne — urządzenie/sesja. | DO AUDYTU | — |
| WMM-005 | osobna wersja WMM | WYSOKI | Test współbieżny | Test 3–5 klientów WMM jednocześnie: odczyt, zmiana statusów, zdjęcia, dyspozycje i konflikt tej samej pozycji. | DO AUDYTU | — |

## Zasada zamykania fixa

Wpisu nie usuwamy po naprawie. Uzupełniamy: dokładną wersję, status `NAPRAWIONE`, commit, datę oraz test regresyjny. Dzięki temu historia napraw pozostaje czytelna bez szukania po starych rozmowach.
