# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.7**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.7: `65aa7d24da06018dc99473d94c90cd8a9a667599`
- Etap: **stabilizacja produktu**
- Nowe duże funkcje: **wstrzymane do czasu ustabilizowania obecnych modułów**
- Zgodność mobilna: **WMM 0.5.9** pozostaje kompatybilne z WM 1.0.7.

## Cel

Doprowadzić WM do stanu, w którym obecne funkcje są szybkie, przewidywalne i bezpieczne dla danych. WMM jest rozwijane równolegle jako klient mobilny, ale nie może obniżać stabilności WM.

## Zasady wersjonowania

- Każda zaakceptowana poprawka produktu podnosi wersję o `0.0.1`.
- Przykład: `1.0.6 -> 1.0.7 -> 1.0.8`.
- Dokumentacja administracyjna sama w sobie nie zużywa numeru wersji; numer przypisujemy do konkretnej poprawki produktu.
- Większe nowe funkcje są odkładane poza bieżący etap stabilizacji i wymagają osobnej decyzji.
- Każdy fix otrzymuje ID `WM10-xxx`; poprawki WMM otrzymują ID `WMM-xxx`.
- Jeśli jedna poprawka dotyczy obu projektów, zapisujemy oba ID.

## Stan obszarów

| Obszar | Stan | Następny krok |
|---|---|---|
| Logowanie / sesja | DO AUDYTU | końcowy smoke + lifecycle |
| Profil / Brygadzista | STABILIZACJA | `user_id` przy zmianie loginu zabezpieczone w 1.0.7; do sprawdzenia pierwszy klik Brygadzisty i refresh |
| Grafik / zmiany | DO AUDYTU | potwierdzić jedno źródło godzin i trybów |
| Planista / Zlecenia | STABILIZACJA | numeracja WM/WMM i rezerwacje zabezpieczone; pozostał pełny test E2E + restart/refresh |
| Maszyny | STABILIZACJA | blokada zapisu WM/WMM gotowa; edytor i ergonomia nadal do audytu |
| Narzędzia | STABILIZACJA | blokada pojedynczych plików WM/WMM i zapis atomowy gotowe; konflikt starej wersji danych pozostaje osobnym etapem |
| Dyspozycje | STABILIZACJA | bezpieczny zapis gotowy; role/uprawnienia i historia do audytu funkcjonalnego |
| Magazyn | STABILIZACJA | pełny read-modify-write dla rezerwacji zabezpieczony w 1.0.6; ROOT/refresh do audytu |
| ROOT / config | DO AUDYTU | domknąć jedno źródło ścieżek i pozostałe zapisy |
| UI / lifecycle | DO AUDYTU | ciężkie refresh, skanowanie katalogów, `after()`/destroy |
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

## WM 1.0.7 — wynik

- Fix: `WM10-002`.
- Nowe wpisy Obecności i Urlopów już wcześniej używały `user_id`; nie wykonano więc hurtowej migracji.
- Przed faktyczną zmianą loginu WM uzupełnia brakujące `user_id` tylko w historycznych rekordach tej osoby: Opinie, Urlopy, wnioski urlopowe, Obecność, audit Obecności i historia administracyjna Profilu.
- Istniejące `user_id` nie są nadpisywane, a stary login pozostaje snapshotem historycznym.
- Nie zmieniono UI ani kontraktu API WMM.
- Test regresyjny: `tests/test_profile_identity_runtime.py`.
- Główny CI dla commita `65aa7d24da06018dc99473d94c90cd8a9a667599`: **SUCCESS**; workflowy R07 i R08 również **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy od kolejnego małego audytu. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na 2026-09-11

Aktualny punkt stabilizacji: **WM 1.0.7**. Najbliższe otwarte bloki: Grafik/zmiany, pełny Planista E2E, role Dyspozycji, Profil/Brygadzista, edytor Maszyn oraz końcowe ROOT/lifecycle.
