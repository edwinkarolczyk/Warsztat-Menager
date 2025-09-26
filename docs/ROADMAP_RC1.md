# WM – Roadmapa stabilizacji RC1

Dokument śledzący etapy stabilizacji RC1 wraz z kluczowymi kamieniami milowymi.

## Założenia
- RC1 to wydanie kandydujące do publikacji produkcyjnej.
- Każda faza musi mieć przypisaną osobę odpowiedzialną.
- Raportujemy status raz w tygodniu podczas spotkania stabilizacyjnego.

## Fazy
1. **Analiza zgłoszeń** – przegląd rejestru błędów, priorytetyzacja i plan działania.
2. **Implementacja poprawek** – development, code review, smoke testy modułowe.
3. **Regresja** – testy automatyczne/manualne, sanity check środowisk.
4. **Przygotowanie releasu** – komplet dokumentacji, komunikacja z interesariuszami.
5. **Go/No-Go** – decyzja o publikacji lub kolejnym cyklu poprawek.

## Harmonogram przykładowy
| Tydzień | Zadania | Odpowiedzialny |
|---------|---------|----------------|
| T1 | Analiza backlogu, aktualizacja TICKETS_RC1 | ... |
| T2 | Poprawki krytyczne, review planu testów | ... |
| T3 | Pełna regresja, walidacja kryteriów wyjścia | ... |
| T4 | Przygotowanie releasu, komunikacja | ... |

## Ryzyka i mitigacje
- **Brak zasobów QA** – rotacja testerów, priorytetyzacja smoke testów.
- **Niestabilne środowisko testowe** – automatyczne healthchecki, monitoring.
- **Nowe zgłoszenia P0** – szybka triage, dedykowany kanał incident-response.

## Materiały powiązane
- `docs/TICKETS_RC1.md`
- Plan testów QA
- Lista właścicieli modułów oraz kontaktów awaryjnych
