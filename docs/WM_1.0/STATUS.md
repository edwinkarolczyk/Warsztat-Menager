# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.8**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.8: `7fcd1e6d14a2597040e643e48f7b6f606a005ff8`
- Etap: **stabilizacja produktu**
- Nowe duże funkcje: **wstrzymane do czasu ustabilizowania obecnych modułów**
- Zgodność mobilna: **WMM 0.5.9** pozostaje kompatybilne z WM 1.0.8.

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
| Logowanie / sesja | STABILIZACJA | godziny zmian zsynchronizowane z Grafikiem w 1.0.8; pozostał końcowy smoke + lifecycle |
| Profil / Brygadzista | STABILIZACJA | `user_id` przy zmianie loginu zabezpieczone w 1.0.7; do sprawdzenia pierwszy klik Brygadzisty i refresh |
| Grafik / zmiany | STABILIZACJA | godziny Logowania, Obecności i paska postępu mają wspólne źródło; tryby 111/112/222/121/212 pozostają kanoniczne |
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
- **1.0.8** — Grafik/zmiany: wspólne godziny dla Logowania, Obecności i paska postępu zmiany.

## WM 1.0.8 — wynik

- Fix: `WM10-003`.
- Logowanie, Obecność i pasek postępu zmiany korzystają z `grafiki.shifts_schedule._shift_times()` jako wspólnego źródła godzin.
- Kanoniczny resolver logowania jest chroniony przed starszym runtime'em, który wcześniej mógł przywrócić własne zakresy 05:00–14:00 / 14:00–23:59.
- Tryby grafiku `111 / 112 / 222 / 121 / 212` nie zostały przebudowane.
- Nie zmieniono modelu danych, endpointów ani kontraktu WMM.
- Test regresyjny: `tests/test_shift_hours_sync.py` z godzinami 05:30–13:30 / 13:30–21:30.
- Główny CI dla commita `7fcd1e6d14a2597040e643e48f7b6f606a005ff8` (run `34583503458`): **SUCCESS**; workflowy R07 i R08 również **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy od kolejnego małego audytu. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na 2026-09-11

Aktualny punkt stabilizacji: **WM 1.0.8**. Najbliższe otwarte bloki: pełny Planista E2E, role Dyspozycji, Profil/Brygadzista, edytor Maszyn oraz końcowe ROOT/lifecycle.
