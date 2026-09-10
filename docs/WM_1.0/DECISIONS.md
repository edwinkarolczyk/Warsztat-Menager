# WM 1.0 — DECYZJE

Ten plik zapisuje ustalenia, które wpływają na sposób dalszego rozwoju. Jeżeli przed poprawką potrzebna jest decyzja użytkownika, najpierw zapisujemy pytanie, po odpowiedzi dopisujemy decyzję i dopiero wtedy zmieniamy kod.

## Podjęte decyzje

### DEC-001 — WM 1.0.0 jako nowa baza

- Data: 2026-09-10
- Decyzja: aktualny etap projektu prowadzimy jako **WM 1.0.0 / linia 1.0.x**.
- Baza repo: `Rozwiniecie`, commit `184cf180abcb5681f0e6205724ac0a3a2807b19e`.
- Cel: stabilizacja obecnego produktu przed dalszym rozwojem funkcjonalnym.

### DEC-002 — wersjonowanie każdego fixa

- Każda zaakceptowana poprawka produktu podnosi patch o `0.0.1`.
- Przykład: `1.0.0 -> 1.0.1 -> 1.0.2`.
- Do każdej wersji zapisujemy ID fixa, commit i wynik testu.

### DEC-003 — brak niezaakceptowanych zmian

- Najpierw analiza i — gdy potrzebne — pytanie/decyzja.
- Kod zmieniamy dopiero po akceptacji zakresu.
- Nie rozszerzamy poprawki o poboczne refaktoryzacje.

### DEC-004 — nie robimy wszystkiego jednego dnia

- Gdy dzienny zakres staje się za szeroki lub ryzykowny, zatrzymujemy się w bezpiecznym punkcie.
- Asystent ma wyraźnie wskazać, że na dany dzień wystarczy, podsumować stan i wskazać następny krok.
- Preferujemy 1–3 małe, sprawdzone poprawki zamiast dużego pakietu zmian.

### DEC-005 — WMM rozwijane równolegle

- WMM rozwijamy równolegle z WM.
- Nawet jeśli typowo nie będzie używane przez wielu pracowników naraz, projektujemy je bezpiecznie dla kilku klientów jednocześnie.
- Minimalny scenariusz testowy: **3–5 klientów WMM**.

### DEC-006 — bezpieczeństwo danych ważniejsze niż liczba funkcji

- W stabilizacji 1.0.x pierwszeństwo mają: zapis, ROOT, identyfikatory, refresh, lifecycle, uprawnienia, współbieżność i testy.
- Nowe duże funkcje nie są dodawane bez osobnej decyzji.

### DEC-007 — stare RC1 jest historią

- Istniejące pliki `docs/ROADMAP_RC1.md`, `docs/TICKETS_RC1.md` i pozostałe stare plany pozostają w repo.
- Nie kasujemy ich.
- Bieżącym źródłem statusu stabilizacji jest `docs/WM_1.0/`.

### DEC-008 — globalna pomoc kontekstowa `!`

- Przy kolejnych poprawianych ekranach uwzględniamy wspólny mechanizm `!` przy istotnych polach, przyciskach i opcjach.
- Tekst pomocy ma mieć maksymalnie dwa krótkie zdania i nie tworzymy osobnego mechanizmu dla każdego modułu.

## Otwarte pytania

Tutaj zapisujemy pytania wymagające decyzji przed implementacją.

| ID | Temat | Pytanie | Stan | Decyzja |
|---|---|---|---|---|
| Q-001 | Wersja aplikacji | Gdzie ma być jedno techniczne źródło numeru wersji WM, aby UI/build/logi nie rozjechały się między plikami? | OTWARTE | — |
| Q-002 | Konflikty WMM | Czy przy konflikcie 409 WMM ma tylko wymagać odświeżenia, czy pokazywać również porównanie „moja wersja / aktualna wersja”? | OTWARTE | — |
| Q-003 | WMM użytkownik | Jak dokładnie identyfikujemy pracownika w historii zmian WMM: PIN/sesja WM, wybór użytkownika czy osobne logowanie mobilne? | OTWARTE | — |

## Szablon nowej decyzji

```text
DEC-xxx
Data:
Temat:
Pytanie:
Decyzja:
Powód:
Powiązany fix:
```
