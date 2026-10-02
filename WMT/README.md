# WMT 1.0.1 — Warsztat Menager Tester

WMT jest osobnym testerem Warsztat Menager. Nie zmienia kodu WM i nie wykonuje testów na produkcyjnym `WM_ROOT`.

## Najważniejsze w 1.0.1

Dodano **Robot GUI**. WMT uruchamia prawdziwy `start.py` WM na izolowanym sandboxie i steruje realnymi kontrolkami Tkinter z zewnątrz. Użytkownik widzi, jak WM sam przechodzi przez kolejne ekrany.

Pierwszy scenariusz robota wykonuje:

- start prawdziwego WM,
- logowanie testowym brygadzistą/administratorem z kopii danych,
- przejście przez główne moduły,
- `Dyspozycje → Dodaj Dyspozycję → Zlecenie wewnętrzne → produkt → ilość → Utwórz`,
- potwierdzenie, że dane zlecenia rzeczywiście zmieniły się w testowym ROOT,
- `Narzędzia → Dodaj → Nowe (001–499) → Dalej`,
- wpisanie nazwy testowej, wybór typu i statusu,
- zapis nowego narzędzia,
- zmianę statusu na kolejny,
- sprawdzenie `narzedzia_historia/<nr>.jsonl` pod kątem `status_changed`,
- zapis końcowego snapshotu kontrolek GUI,
- po zamknięciu WM uruchomienie testów kontraktów WM ↔ WMM.

Robot nie używa sztywnych współrzędnych ekranu. W testowym procesie WM działa lokalny most WMT, który rozpoznaje kontrolki po tekstach/etykietach i wykonuje te same komendy Tk co kliknięcie przycisku. Kod WM pozostaje nietknięty.

## Poprawka 1.0.1

W WMT 1.0.0 uruchomionym jako EXE `sys.executable` wskazywał na `WMT.exe`, więc pełny test próbował wykonać `WMT.exe -m pytest`. 1.0.1 wykrywa prawdziwego Pythona 3.13 (`.venv`, `py -3.13`, `python`) i używa go do testów WM.

## Pozostałe tryby

- **Smoke** — najważniejsze istniejące testy WM.
- **Pełny test** — wszystkie `tests/` i testy `test_*.py` z repo WM.
- **WM ↔ WMM** — testy kontraktów/integracji WMM.
- **Test klikany WM** — widoczny Robot GUI opisany wyżej.
- **WM obserwowany** — tylko uruchamia WM na testowym ROOT do ręcznej obserwacji.

## Raporty

Każda sesja dostaje własny katalog z `report.json`, `report.html`, sandboxem i logami. Robot GUI dodatkowo zapisuje `wm-robot.log`, `gui-modals.jsonl` oraz `gui-final-snapshot.json`.

To jest fundament pod rosnący katalog scenariuszy. Kolejne moduły i operacje można dopisywać do WMT bez przebudowy kodu WM.
