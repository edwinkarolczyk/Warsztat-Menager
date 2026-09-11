# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.9**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.9: `f762fa2b7ca8f0260798cade3f8a72415585d9cf`
- Etap: **stabilizacja produktu / remont UI**
- Nowe duże funkcje: **wstrzymane do czasu ustabilizowania obecnych modułów**
- Zgodność mobilna: **WMM 0.5.9** pozostaje kompatybilne z WM 1.0.9.

## Cel

Doprowadzić WM do stanu, w którym obecne funkcje są szybkie, przewidywalne i bezpieczne dla danych. WMM jest rozwijane równolegle jako klient mobilny, ale nie może obniżać stabilności WM.

## Zasady wersjonowania

- Każda zaakceptowana poprawka produktu podnosi wersję o `0.0.1`.
- Przykład: `1.0.7 -> 1.0.8 -> 1.0.9`.
- Dokumentacja administracyjna sama w sobie nie zużywa numeru wersji; numer przypisujemy do konkretnej poprawki produktu.
- Większe nowe funkcje są odkładane poza bieżący etap stabilizacji i wymagają osobnej decyzji.
- Każdy fix otrzymuje ID `WM10-xxx`; poprawki WMM otrzymują ID `WMM-xxx`.
- Jeśli jedna poprawka dotyczy obu projektów, zapisujemy oba ID.

## Stan obszarów

| Obszar | Stan | Następny krok |
|---|---|---|
| Logowanie / sesja | STABILIZACJA | godziny zmian zsynchronizowane z Grafikiem w 1.0.8; komunikat remontowy działa po zalogowaniu; pozostał końcowy smoke + lifecycle |
| Profil / Brygadzista | STABILIZACJA | `user_id` zabezpieczone w 1.0.7; Obecność dostała kosmetykę i edycję grupową w 1.0.9; do sprawdzenia pierwszy klik Brygadzisty i pozostałe refresh'e |
| Grafik / zmiany | STABILIZACJA | godziny Logowania, Obecności i paska postępu mają wspólne źródło; tryby 111/112/222/121/212 pozostają kanoniczne |
| Planista / Zlecenia | STABILIZACJA | numeracja WM/WMM i rezerwacje zabezpieczone; pozostał pełny test E2E + restart/refresh |
| Maszyny | STABILIZACJA | blokada zapisu WM/WMM gotowa; edytor i ergonomia nadal do audytu |
| Narzędzia | STABILIZACJA | blokada pojedynczych plików WM/WMM i zapis atomowy gotowe; konflikt starej wersji danych pozostaje osobnym etapem |
| Dyspozycje | STABILIZACJA | bezpieczny zapis gotowy; role/uprawnienia i historia do audytu funkcjonalnego |
| Magazyn | STABILIZACJA | pełny read-modify-write dla rezerwacji zabezpieczony w 1.0.6; ROOT/refresh do audytu |
| ROOT / config | DO AUDYTU | domknąć jedno źródło ścieżek i pozostałe zapisy |
| UI / lifecycle | STABILIZACJA | 1.0.9 usunęło zbędne zamykanie profilu po zapisie Obecności; nadal do audytu ciężkie refresh'e, skanowanie katalogów i `after()`/destroy |
| WMM API w WM | BETA / STABILIZACJA | fizyczne blokady głównych zapisów gotowe; `revision`/409 i pełna historia WMM później |
| WMM mobile | ROZWÓJ RÓWNOLEGŁY | historia operacji i test wielu klientów pozostają osobno |

## Zamknięte etapy

- **1.0.1** — Maszyny WM/WMM: wspólna blokada zapisu.
- **1.0.2** — stabilizacja integracji WMM i bump wydania.
- **1.0.3** — Dyspozycje: pełna transakcja + atomowy zapis.
- **1.0.4** — Narzędzia: wspólna blokada pojedynczych plików + zapis atomowy.
- **1.0.5** — Planista: wspólna blokada tworzenia zlecenia WM/WMM i unikalne ID.
- **1.0.6** — Magazyn/Planista: serializacja pełnego read-modify-write dla rezerwacji.
- **1.0.7** — Profil/tożsamość: ochrona trwałego `user_id` przy zmianie loginu oraz targeted backfill rekordów legacy tej osoby.
- **1.0.8** — Grafik/zmiany: wspólne godziny dla Logowania, Obecności i paska postępu zmiany.
- **1.0.9** — Profil/Obecność + UI: lokalny refresh po zapisie, wielozaznaczenie dni, czytelniejsze kolumny i wyłączalny komunikat o remoncie z wejściem do `Wyślij opinię`.

## WM 1.0.9 — wynik

- Fix: `WM10-010`.
- `Zapisz wszystko` w Obecności nie propaguje już zapisu do przebudowy nadrzędnego panelu; bieżące okno pracownika pozostaje otwarte i odświeża własną tabelę.
- Tabela Obecności obsługuje wielozaznaczenie `Ctrl/Shift + klik`. Przy zapisie grupowym zmieniane są tylko pola, które użytkownik faktycznie zmienił po zaznaczeniu wielu dni; data i pierwsze logowanie każdego dnia pozostają indywidualne.
- Szerokości kolumn Obecności zostały dopasowane bez zmiany modelu danych.
- Po zalogowaniu główny panel może pokazać komunikat o remoncie WM podpisany `Edwin K.`; przycisk `Wyślij opinię` uruchamia istniejący formularz. Komunikat można wyłączyć w `Ustawienia -> Ogólne`.
- Dla nowych elementów użyto wspólnego mechanizmu pomocy `!`.
- Nie zmieniono JSON-ów, endpointów ani kontraktu WMM.
- Test regresyjny: `tests/test_wm_ui_renovation_runtime.py`.
- Główny CI dla commita `f762fa2b7ca8f0260798cade3f8a72415585d9cf` (run `34585823490`): **SUCCESS**; R07 `34585823569` i R08 `34585823555` również **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy od kolejnego małego audytu. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na 2026-09-11

Aktualny punkt stabilizacji: **WM 1.0.9**. Najbliższe otwarte bloki: pełny Planista E2E, role Dyspozycji, Profil/Brygadzista, edytor Maszyn oraz końcowe ROOT/lifecycle. Remont UI kontynuujemy małymi, widocznymi krokami bez rozszerzania modelu danych bez potrzeby.
