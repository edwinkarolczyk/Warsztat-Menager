# WM 1.0 — STATUS

## Stan bazowy

- Produkt: Warsztat Menager
- Linia wersji: **WM 1.0.x**
- Wersja bazowa: **1.0.0**
- Data przyjęcia bazy: **2026-09-10**
- Gałąź robocza: `Rozwiniecie`
- Commit bazowy: `184cf180abcb5681f0e6205724ac0a3a2807b19e`
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
| Maszyny | DO AUDYTU | zapis, edytor, lokalizacja, serwis |
| Narzędzia | DO AUDYTU | zapis, powiązania, refresh |
| Dyspozycje | DO AUDYTU | uprawnienia, statusy, historia |
| Magazyn | DO AUDYTU | źródło danych, zapis, refresh |
| ROOT / config | DO AUDYTU | jedno źródło ścieżek |
| WMM API w WM | BETA / DO AUDYTU | konflikty zapisu i współbieżność |
| WMM mobile | ROZWÓJ RÓWNOLEGŁY | test 3–5 klientów jednocześnie |

## Reguła pracy dziennej

Nie robimy zmian na siłę. Jeżeli zakres jednego dnia zaczyna obejmować zbyt wiele modułów, danych lub zależności, zatrzymujemy się w bezpiecznym punkcie, zapisujemy stan i kontynuujemy kolejnego dnia. Preferowane jest 1–3 małe, przetestowane poprawki zamiast dużego pakietu zmian.

## Następny krok

1. Audyt krytyczny bez zmian w kodzie.
2. Uporządkowanie listy w `FIXES.md`.
3. Wybór pierwszej zaakceptowanej poprawki.
4. Pierwszy fix produktu otrzyma wersję **1.0.1**.
