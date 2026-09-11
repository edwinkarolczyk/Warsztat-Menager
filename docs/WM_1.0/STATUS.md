# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.11**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.11: `2280ebeb51339f334ff8f3663f6951bf67c64731`
- Etap: **stabilizacja produktu / remont UI**
- Nowe duże funkcje: **wstrzymane do czasu ustabilizowania obecnych modułów**
- Zgodność mobilna: **WMM 0.5.9** pozostaje kompatybilne z WM 1.0.11.

## Cel

Doprowadzić WM do stanu, w którym obecne funkcje są szybkie, przewidywalne i bezpieczne dla danych. WMM jest rozwijane równolegle jako klient mobilny, ale nie może obniżać stabilności WM.

## Zasady wersjonowania

- Każda zaakceptowana poprawka produktu podnosi wersję o `0.0.1`.
- Przykład: `1.0.9 -> 1.0.10 -> 1.0.11`.
- Dokumentacja administracyjna sama w sobie nie zużywa numeru wersji; numer przypisujemy do konkretnej poprawki produktu.
- Większe nowe funkcje są odkładane poza bieżący etap stabilizacji i wymagają osobnej decyzji.
- Każdy fix otrzymuje ID `WM10-xxx`; poprawki WMM otrzymują ID `WMM-xxx`.
- Jeśli jedna poprawka dotyczy obu projektów, zapisujemy oba ID.

## Stan obszarów

| Obszar | Stan | Następny krok |
|---|---|---|
| Logowanie / sesja | STABILIZACJA | godziny zmian zsynchronizowane z Grafikiem w 1.0.8; komunikat remontowy działa po zalogowaniu; pozostał końcowy smoke + lifecycle |
| Profil / Brygadzista | STABILIZACJA | `user_id` zabezpieczone w 1.0.7; Obecność dostała kosmetykę i edycję grupową w 1.0.9; w 1.0.11 tabele ponawiają autofit po pokazaniu zakładki; do sprawdzenia pierwszy klik Brygadzisty i pozostałe refresh'e |
| Grafik / zmiany | STABILIZACJA | godziny mają wspólne źródło; od 1.0.10 kanoniczne tryby to 11/22/12/21 z cyklem dwutygodniowym; 1.0.11 dodaje kalendarz tygodnia bazowego |
| Planista / Zlecenia | STABILIZACJA | numeracja WM/WMM i rezerwacje zabezpieczone; pozostał pełny test E2E + restart/refresh |
| Maszyny | STABILIZACJA | blokada zapisu WM/WMM gotowa; edytor i ergonomia nadal do audytu |
| Narzędzia | STABILIZACJA | blokada pojedynczych plików WM/WMM i zapis atomowy gotowe; konflikt starej wersji danych pozostaje osobnym etapem |
| Dyspozycje | STABILIZACJA | bezpieczny zapis gotowy; role/uprawnienia i historia do audytu funkcjonalnego |
| Magazyn | STABILIZACJA | pełny read-modify-write dla rezerwacji zabezpieczony w 1.0.6; ROOT/refresh do audytu |
| ROOT / config | DO AUDYTU | domknąć jedno źródło ścieżek i pozostałe zapisy |
| UI / lifecycle | STABILIZACJA | 1.0.9 usunęło zbędne zamykanie profilu po zapisie Obecności; 1.0.11 poprawia szerokości tabel po pokazaniu ukrytych zakładek; nadal do audytu ciężkie refresh'e, skanowanie katalogów i `after()`/destroy |
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
- **1.0.10** — Grafik: poprawiony model zmian na 11/22/12/21; 12 i 21 są przeciwstawnym cyklem dwutygodniowym, stare kody działają jako aliasy zgodności.
- **1.0.11** — Profil/Grafik + Brygadzista UI: kalendarz dla tygodnia bazowego oraz ponowny autofit tabel po pokazaniu zakładki.

## WM 1.0.11 — wynik

- `Profil pracownika -> Grafik -> Tydzień bazowy` korzysta ze wspólnego `open_date_picker(...)`; pole jest tylko do odczytu, a wybrany dzień zostaje sprowadzony do poniedziałku tego tygodnia.
- Tabele tworzone w `Profil -> Brygadzista` ponawiają dopasowanie szerokości przy zdarzeniu `<Map>`, dzięki czemu ukryta wcześniej zakładka nie wymaga ręcznego poruszenia separatora kolumny.
- Nie zmieniono danych, kolejności kolumn, modelu Grafiku, JSON-ów ani API WMM.
- Test regresyjny: `tests/test_profile_ui_refresh_1011.py`; został dopięty do `Run profile workforce regressions`.
- Główny CI dla commita `2280ebeb51339f334ff8f3663f6951bf67c64731` (run `34592160771`): **SUCCESS**; R07 `34592160770` i R08 `34592160783` również **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy od kolejnego małego audytu. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na 2026-09-11

Aktualny punkt stabilizacji: **WM 1.0.11**. Najbliższe otwarte bloki: pełny Planista E2E, role Dyspozycji, Profil/Brygadzista, edytor Maszyn oraz końcowe ROOT/lifecycle. Remont UI kontynuujemy małymi, widocznymi krokami bez rozszerzania modelu danych bez potrzeby.
