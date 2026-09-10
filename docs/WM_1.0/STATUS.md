# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Aktualna wersja techniczna: **1.0.1**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy produktu: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
- Commit inicjalizujący rejestr WM 1.0: `7f82870670acb88f8ad04cfc9a67312fd41455d9`
- Ostatni przetestowany commit kodu 1.0.1: `c6cde038220aed2d92eccee877bb9168896f856c`
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
| Maszyny | STABILIZACJA | WM 1.0.1 zabezpieczyło fizyczny zapis WM/WMM; edytor i pozostałe zapisy nadal do audytu |
| Narzędzia | DO AUDYTU | zapis, powiązania, refresh |
| Dyspozycje | DO AUDYTU | uprawnienia, statusy, historia, trwałość zapisu |
| Magazyn | DO AUDYTU | źródło danych, zapis, refresh |
| ROOT / config | DO AUDYTU | jedno źródło ścieżek |
| WMM API w WM | BETA / STABILIZACJA | blokada pliku Maszyn gotowa; wykrywanie konfliktów `revision`/409 pozostaje osobnym etapem |
| WMM mobile | ROZWÓJ RÓWNOLEGŁY | test 3–5 klientów jednocześnie |

## WM 1.0.1 — wynik

- Fix: `WM10-001A`.
- Zakres: fizyczne zabezpieczenie wspólnego pliku `data/maszyny/maszyny.json` przy zapisach desktopowego WM i WMM.
- WMM obejmuje blokadą cały cykl odczyt -> modyfikacja -> zapis maszyny.
- Format danych Maszyn nie został zmieniony.
- Istniejący atomowy zapis danych pozostał zachowany.
- CI dla commita `c6cde038220aed2d92eccee877bb9168896f856c`: R07, R08 i główny `ci.yml` — **SUCCESS**.

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy kolejnego dnia. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Stan na koniec 2026-09-10

Dzień zamknięty na **WM 1.0.1**. Nie rozpoczynamy dziś kolejnego fixa; następna sesja zaczyna się od wyboru i akceptacji następnego małego zakresu stabilizacyjnego.
