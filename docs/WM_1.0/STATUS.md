# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.3**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.3: `ec5c4d87aa2b4fd4e5eb35c13c6edbe95eb6503e`
- Etap: **stabilizacja produktu**
- Nowe duże funkcje: **wstrzymane do czasu ustabilizowania obecnych modułów**

## Cel

Doprowadzić WM do stanu, w którym obecne funkcje są szybkie, przewidywalne i bezpieczne dla danych. WMM jest rozwijane równolegle jako klient mobilny, ale nie może obniżać stabilności WM.

## Zasady wersjonowania

- Każda zaakceptowana poprawka produktu podnosi wersję o `0.0.1`.
- Przykład: `1.0.0 -> 1.0.1 -> 1.0.2`.
- Dokumentacja administracyjna sama w sobie nie zużywa numeru wersji; numer przypisujemy do konkretnej poprawki produktu.
- Większe nowe funkcje są odkładane poza bieżący etap stabilizacji i wymagają osobnej decyzji.
- Każdy fix otrzymuje ID `WM10-xxx`; poprawki WMM otrzymują ID `WMM-xxx`.
- Jeśli jedna poprawka dotyczy obu projektów, zapisujemy oba ID.

## Stan obszarów

| Obszar | Stan | Następny krok |
|---|---|---|
| Logowanie / sesja | DO AUDYTU | smoke test + lifecycle |
| Profil / Brygadzista | DO AUDYTU | ładowanie, uprawnienia, refresh |
| Planista / Zlecenia | DO AUDYTU | zapis, restart, identyfikatory, rezerwacje |
| Maszyny | STABILIZACJA | blokada zapisu WM/WMM gotowa; edytor i pozostałe zapisy nadal do audytu |
| Narzędzia | DO AUDYTU | zapis, powiązania, refresh |
| Dyspozycje | STABILIZACJA | WM 1.0.3 zabezpieczyło pełne transakcje zapisu; uprawnienia/statusy/historia nadal do dalszego audytu funkcjonalnego |
| Magazyn | DO AUDYTU | źródło danych, zapis, refresh |
| ROOT / config | DO AUDYTU | jedno źródło ścieżek |
| WMM API w WM | BETA / STABILIZACJA | blokady plików Maszyn i Dyspozycji gotowe; wykrywanie konfliktów `revision`/409 pozostaje osobnym etapem |
| WMM mobile | ROZWÓJ RÓWNOLEGŁY | test 3–5 klientów jednocześnie |

## WM 1.0.1 — wynik

- Fix: `WM10-001A`.
- Zakres: fizyczne zabezpieczenie wspólnego pliku `data/maszyny/maszyny.json` przy zapisach desktopowego WM i WMM.
- WMM obejmuje blokadą cały cykl odczyt -> modyfikacja -> zapis maszyny.
- Format danych Maszyn nie został zmieniony.
- Istniejący atomowy zapis danych pozostał zachowany.
- CI dla commita `c6cde038220aed2d92eccee877bb9168896f856c`: R07, R08 i główny `ci.yml` — **SUCCESS**.

## WM 1.0.2 — wynik

- Wersja została podniesiona po stabilizacji integracji WMM.
- Commit wersji: `37bbc7f4b671bbc0641e6ca4cefafcf9ebf869ff`.
- Rejestr stabilizacji nie został wtedy wyrównany i został uzupełniony przy zamknięciu 1.0.3.

## WM 1.0.3 — wynik

- Fix: `WM10-006B`.
- Zakres: bezpieczny zapis `data/dyspozycje/dyspozycje.json` przy równoległych operacjach WM/WMM.
- `add`, `update`, `delete` i zmiana statusu obejmują wspólną blokadą cały cykl odczyt -> modyfikacja -> zapis.
- Zapis jest atomowy: plik tymczasowy w tym samym katalogu, następnie `os.replace`.
- Format JSON Dyspozycji nie został zmieniony.
- Dodano regresję `tests/test_dyspozycje_store_write_guard.py` i uruchamianie jej w głównym CI.
- Commit implementacji: `52f472f0cb34a5fcb1f0a0365a0e6f042802a70e`.
- Commit z zielonym głównym CI: `ec5c4d87aa2b4fd4e5eb35c13c6edbe95eb6503e` — **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy kolejnego dnia. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na 2026-09-11

Aktualny punkt stabilizacji: **WM 1.0.3**. Następny fix wybieramy dopiero po osobnej analizie i akceptacji zakresu.
