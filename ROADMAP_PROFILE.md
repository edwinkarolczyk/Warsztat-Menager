# ROADMAP — Profile / Użytkownicy / Obecność

> Kierunek: rozwijać Profile małymi krokami, zachowując obecny wygląd i wspólny system pomocy `!`.
> Dane płacowe na tym etapie są wyłącznie informacją źródłową — WM nie jest jeszcze programem kadrowo-płacowym.

## Etap 1 — Obecność i rodzaje dni

- ✅ dniówki z logowania WM + decyzje Brygadzisty
- ✅ brak spóźnień jako osobnej statystyki
- ✅ nadgodziny i osobne soboty
- ✅ urlop roczny + zaległy, najstarszy wykorzystywany pierwszy
- ✅ typ dnia i procent płatności jako osobne dane
- ✅ domyślne kody: `PRACA 100%`, `UR 100%`, `UŻ 100%`, `L4 80%`, `ŚW 50%`, `NN 0%`, `UB 0%`, `BRAK 0%`
- ✅ dzień nierozstrzygnięty nie ma automatycznej wyceny i blokuje przyszłą sugestię wypłaty
- ✅ wartości procentowe są konfigurowalne; nie są na stałe zaszyte w GUI

## Etap 2 — Kalendarz Profili

- ✅ zwykły użytkownik zachowuje swój dotychczasowy kalendarz
- ✅ Brygadzista ma tryb `Mój / Zespół`
- ✅ kafelek dnia pokazuje krótki skrót zmian i nieobecności
- ✅ kliknięcie dnia w trybie Zespół otwiera pełne szczegóły
- ✅ szczegóły: `Pracownik | Zmiana | Status | Płatność`
- ✅ z dnia można przejść do odpowiedniej zakładki Profilu pracownika

## Etap 3 — Stawki i dodatki — później

- ⚪ stawka podstawowa pracownika (godzinowa / miesięczna — decyzja przy wdrożeniu)
- ⚪ historia zmian stawki z datą obowiązywania; nie nadpisywać historii
- ⚪ dodatki konfigurowalne, np. nadgodziny 50% / 100%, sobota, niedziela, święto
- ⚪ możliwość ustawienia wyjątkowego procentu dla konkretnego dnia bez zmiany globalnej definicji
- ⚪ wszystkie zmiany wyłącznie z audytem: kto / kiedy / przed → po / powód

## Etap 4 — Sugerowana wypłata — później

- ⚪ miesięczne zestawienie tylko z zatwierdzonych danych
- ⚪ wyliczenie na podstawie dniówek, procentów płatności, godzin i zatwierdzonych dodatków
- ⚪ dni `DO_DECYZJI` blokują oznaczenie miesiąca jako kompletnego
- ⚪ WM pokazuje **sugerowaną** kwotę i składniki, a nie wykonuje automatycznej listy płac
- ⚪ Brygadzista może zatwierdzić/korygować dane wejściowe przed wyliczeniem
- ⚪ eksport podsumowania do Excel/PDF dopiero po ustabilizowaniu modelu

## Etap 5 — dalsza rozbudowa Profili/Użytkowników

- ⚪ rozwijać małymi krokami bez dokładania zbędnych głównych zakładek
- ⚪ `Więcej`: umiejętności, kursy/certyfikaty, nagrody, ostrzeżenia i inne dane pomocnicze
- ⚪ historia i audyt pozostają tylko do odczytu
- ⚪ zachować stałe `user_id` jako techniczny klucz powiązań
- ⚪ wszystkie istotne nowe pola/przyciski korzystają ze wspólnego `!`, maksymalnie dwa krótkie zdania

## Zasada kolejności

1. Najpierw poprawność danych i testy.
2. Potem czytelny ekran w istniejącym stylu WM.
3. Dopiero na końcu kalkulacje finansowe i eksporty.
