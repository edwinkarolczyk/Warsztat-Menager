# ROADMAP — Warsztat Menager

> **Aktualizacja:** 2026-09-03  
> **Gałąź robocza:** `Rozwiniecie`  
> **Cel bieżący:** stabilizacja WM + dopięcie rzeczy wynikających z codziennego użycia programu.  
> **Zasada:** najpierw rdzeń, spójność danych i niezawodność; dopiero potem nowe duże funkcje.

## Status oznaczeń

- ✅ **Gotowe / działa w kodzie**
- 🟡 **Częściowo gotowe / wymaga dopięcia**
- 🔴 **Do wykonania**
- ⚪ **Później / po stabilizacji**

---

# P0 — NAJPILNIEJSZE POPRAWKI 2026-09-03 🔴 PRIORYTET ABSOLUTNY

Te punkty wykonujemy **przed pozostałymi zadaniami z Fazy A**. Są to poprawki spójności danych i finalnego UI, a nie nowe funkcje.

## P0.1 Planista → Zlecenia — rozdzielenie zlecenia wewnętrznego i warsztatowego

- 🔴 dodać nową kolumnę **„Zlecenie wew”** przed obecną kolumną numeru zlecenia
- 🔴 `Zlecenie wew` ma pobierać wartość wyłącznie z istniejącego pola `zlec_wew`
- 🔴 obecną kolumnę **„Zlecenie”** zmienić na **„Zlecenie warsztatowe”**
- 🔴 `Zlecenie warsztatowe` ma nadal pokazywać dotychczasowy numer/identyfikator warsztatowy i nie może ponownie używać `zlec_wew`
- 🔴 zwęzić kolumnę `Zlecenie warsztatowe`, pozostawiając numer czytelny
- 🔴 docelowy początek tabeli: `Zlecenie wew` → `Zlecenie warsztatowe` → `Produkt` → `Zamówienie`
- 🔴 zachować kolumnę **„Wersja BOM”** oraz wszystkie pozostałe istniejące kolumny
- 🔴 poprawić faktyczne miejsce budujące końcową tabelę, w tym runtime; nie zostawiać dwóch sprzecznych konfiguracji kolumn
- 🔴 nie zmieniać formularza/edytora zleceń ani modelu danych; nie tworzyć nowego pola
- 🔴 dodać test regresyjny potwierdzający poprawne źródła obu kolumn i obecność `Wersja BOM`

**DoD:** użytkownik widzi dwa różne numery w dwóch jednoznacznych kolumnach, a finalny runtime nie nadpisuje poprawnej konfiguracji tabeli.

## P0.2 Surowce → Półprodukty — jedno źródło prawdy i automatyczna nazwa

- 🔴 lista `Półprodukt → Surowiec` ma być budowana **wyłącznie z aktualnie zapisanych rekordów Surowców**
- 🔴 jeśli kartoteka Surowców jest pusta, lista wyboru w Półprodukcie również ma być pusta
- 🔴 usunąć stare/przykładowe/fallbackowe pozycje typu `SUR-001`, `drut f8` itp., jeżeli nie istnieją w aktualnej kartotece Surowców
- 🔴 po usunięciu surowca nie może on pozostawać jako opcja wyboru w Półprodukcie
- 🔴 zachować techniczne ID jako klucz powiązania; użytkownik ma wybierać czytelny opis, a WM zapisuje właściwe ID
- 🔴 usunąć ręczne pole **„Nazwa”** z formularza Surowca
- 🔴 nazwę surowca generować automatycznie z `Rodzaj + Fi/Wymiar`, np. `Profil - 30x30x2`, `Pręt - Fi 20`
- 🔴 nie tworzyć drugiego źródła nazw ani drugiego mechanizmu listy surowców
- 🔴 przy zmianach formularza użyć globalnego systemu pomocy `!` przy istotnych polach i przyciskach; opis maksymalnie dwa krótkie zdania i wspólny mechanizm WM
- 🔴 dodać testy regresyjne: pusta kartoteka → pusta lista; dodany surowiec → pojawia się; usunięty surowiec → znika; nazwa generuje się poprawnie

**DoD:** `Surowce` są jedynym źródłem danych dla wyboru surowca w Półprodukcie, a nazwa jest zawsze deterministycznie tworzona z rodzaju i wymiaru.

---

# 1. Stan projektu na dziś

## Rdzeń aplikacji — ✅ / 🟡

WM posiada już centralny mechanizm konfiguracji (`ConfigManager`), schemat ustawień, centralny ROOT oparty o `core.root_paths`, logowanie oraz rozbudowany panel Ustawień. W kodzie występują również zabezpieczenia związane z Tkinter `.after()` i niszczeniem widgetów.

### Już obecne
- ✅ centralny ROOT / DATA resolver
- ✅ `ConfigManager`
- ✅ `settings_schema.json`
- ✅ logowanie i diagnostyka
- ✅ audyt danych / `data/audyt.json`
- ✅ rozbudowane Ustawienia
- ✅ obsługa ról i ograniczeń modułów
- ✅ część testów GUI i testów regresyjnych
- ✅ ochrona timerów `after()` w wybranych modułach
- ✅ globalny znak wodny „PROGRAM W TRAKCIE ROZWOJU” z opcją w Ustawieniach

### Pozostało
- 🟡 ujednolicić wszystkie moduły pod jeden sposób zapisu/odczytu danych
- 🟡 usunąć pozostałe lokalne / historyczne ścieżki i fallbacki
- 🟡 dopiąć jeden spójny cykl życia modułu: otwarcie → refresh → zamknięcie → anulowanie timerów
- 🟡 rozszerzyć testy regresyjne o scenariusze użytkowe

---

# 2. ETAP I — STABILIZACJA RDZENIA WM 🔴 PRIORYTET

## 2.1 ROOT i dane

**Cel:** żaden moduł nie zapisuje danych „obok programu”. Dane użytkowe mają być przypisane do aktywnego ROOT.

- ✅ centralny ROOT istnieje
- ✅ `WM_ROOT`, `WM_DATA_ROOT`, `WM_CONFIG_FILE` są używane w architekturze
- 🟡 chat — przenieść/zweryfikować wszystkie zapisy do aktywnego ROOT
- 🟡 wydruki/dokumenty Dyspozycji — zapisywać do ROOT
- 🟡 historia maszyn/serwisu — jeden ustalony katalog danych w ROOT
- 🟡 ujednolicić ścieżki modułów: Maszyny / Narzędzia / Dyspozycje / Chat / dokumenty / logi / backup
- 🔴 usunąć pozostałe zapisy zależne od bieżącego katalogu programu

**DoD:** ustawienie ROOT zmienia lokalizację danych całego WM; repo/program pozostaje oddzielone od danych warsztatu.

## 2.2 ConfigManager + Ustawienia

- ✅ centralny `ConfigManager`
- ✅ `settings_schema.json`
- ✅ dynamiczne pola ustawień
- ✅ zakładki systemowe / UI / moduły / backup / diagnostyka
- ✅ pierwszy etap UX: podgląd motywu/czcionki oraz wybór kolorów z próbką i przywracaniem wartości domyślnej bez zmiany logiki zapisu
- 🟡 ograniczyć ręczne wyjątki i równoległe mechanizmy konfiguracji
- 🟡 zastępować ręczne wpisywanie gotowym wyborem: lista / checkbox / Spinbox / kalendarz / wybór pliku / wybór koloru
- 🟡 każdy nowy parametr ma trafiać do schema + ConfigManager
- 🟡 sprawdzić pełny cykl: zmień → zapisz → zamknij → uruchom → odczytaj
- 🔴 pełna walidacja konfiguracji i czytelny komunikat o błędzie zapisu
- 🔴 migracje konfiguracji między wersjami

**DoD:** ustawienia mają jedno źródło prawdy i zachowują się identycznie w całym WM; użytkownik wybiera wartości z gotowych kontrolek wszędzie tam, gdzie ręczne wpisywanie nie jest konieczne.

## 2.3 Refresh / lifecycle GUI

- ✅ część modułów ma zabezpieczenia `.after()` i `Destroy`
- 🟡 ujednolicić `clear_frame()` / odświeżanie / tworzenie widoków
- 🟡 Dyspozycje — pełna stabilizacja odświeżania
- 🟡 Narzędzia — odświeżanie bez skanowania całego katalogu przy każdej operacji
- 🟡 Maszyny — odświeżanie listy i szczegółów bez starych referencji
- 🔴 wspólny mechanizm anulowania timerów i sprzątania widoku
- 🔴 testy przełączania modułów 50–100 razy bez crasha / duplikowania widgetów

**DoD:** przełączanie modułów nie zostawia timerów, starych widgetów ani nieaktualnych danych.

## 2.4 Testy i CI

- ✅ istnieją testy GUI / regresyjne
- ✅ istnieją testy uprawnień i przepływów startowych
- 🟡 testy wymagają rozszerzenia o rzeczywiste scenariusze WM
- 🔴 testy pełnego przepływu: START → LOGIN → MODUŁ → EDYCJA → ZAPIS → POWRÓT → USTAWIENIA → LOGOUT
- 🔴 testy ROOT zmiana + ponowne uruchomienie
- 🔴 testy zapisu danych poza katalogiem programu
- 🔴 stabilny CI dla testów krytycznych

**DoD:** każda większa zmiana przechodzi automatyczne testy regresyjne.

---

# 3. ETAP II — DANE, HISTORIA I AUDYT 🟡

## 3.1 Wspólna historia

- ✅ istnieje audyt techniczny
- ✅ WM zapisuje część zdarzeń do logów / audytu
- 🟡 rozdzielić pojęcia „audyt systemowy” i „historia biznesowa”
- 🔴 wspólny model zdarzenia: `kto / kiedy / moduł / rekord / akcja / stara wartość / nowa wartość`
- 🔴 historia biznesowa dla Maszyn, Narzędzi i Dyspozycji

## 3.2 Migracje i spójność JSON

- ✅ konfiguracja posiada schema i mechanizmy walidacyjne
- 🟡 sprawdzić wersjonowanie struktur danych modułów
- 🔴 migracje JSON `v1 → v2 → ...` bez ręcznej edycji danych użytkownika
- 🔴 testy migracji i backup przed migracją

---

# 4. ETAP III — DYSPozycje 2.0 🔴

## 4.1 Daty i terminy

- 🔴 domyślna data = dziś
- 🔴 szybkie przyciski: `+1 dzień`, `+2 dni`, `+1 tydzień`, `+2 tygodnie`
- 🔴 czytelny sposób zmiany terminu bez ręcznego wpisywania

## 4.2 Zadania

- 🔴 zadania pod opisem Dyspozycji
- 🔴 własne zadania użytkownika z odhaczaniem
- 🔴 zadania typu „Narzędzie” mogą być zapisane bezpośrednio do narzędzia
- 🟡 sprawdzić i domknąć dodawanie zadań do narzędzia z poziomu Dyspozycji

## 4.3 Priorytet automatyczny

- 🔴 priorytet wyliczany automatycznie na podstawie terminu
- 🔴 domyślne progi:
  - ≤ 2 dni — Krytyczny
  - ≤ 5 dni — Wysoki
  - ≤ 14 dni — Normalny
  - ≤ 30 dni — Niski
- 🔴 progi edytowalne w Ustawieniach Dyspozycji
- 🔴 użytkownik widzi wynik priorytetu, a nie musi ustawiać go ręcznie

## 4.4 Automatyczne Dyspozycje

- 🔴 zbliżający się termin przeglądu/serwisu maszyny → automatyczna Dyspozycja
- 🔴 opis ma zawierać maszynę i informację, że Dyspozycja została utworzona automatycznie
- 🔴 zabezpieczenie przed wielokrotnym utworzeniem tego samego zadania

## 4.5 Narzędzie ↔ Dyspozycja

- ✅ otwieranie szczegółów narzędzia bezpośrednio z Dyspozycji jest już obecne
- 🟡 dopiąć zmianę statusu narzędzia z poziomu Dyspozycji
- 🟡 sprawdzić odświeżanie po zmianie numeru / usunięciu powiązanego narzędzia
- 🔴 brak „losowego” narzędzia po odświeżeniu

## 4.6 Wydruk

- 🔴 wybór Dyspozycji do druku
- 🔴 zapis dokumentu do ROOT
- 🔴 spójny format wydruku

## 4.7 Wyszukiwanie i sygnalizacja

- 🔴 **Dyspozycje** → dodać wyszukiwarkę.
- 🔴 **Profil → Dyspozycje** → przywrócić miganie dokładnie według mechanizmu używanego w głównym module Dyspozycje, zamiast samego koloru.

**DoD:** Dyspozycje są szybkie w tworzeniu, stabilne przy edycji i mogą być generowane z terminów serwisowych.

---

# 5. ETAP IV — MASZYNY / SERWIS 2.0 🔴

## 5.1 Dane maszyny

- ✅ edycja techniczna i zdjęcie maszyny są dostępne
- 🟡 jednoznaczne źródło prawdy dla danych maszyn
- 🔴 lokalizacja maszyny — naprawić i ujednolicić
- 🔴 lokalizacja widoczna w głównym widoku przed statusem

### 5.1A Lokalizacje maszyn — docelowy model

**Cel:** usunąć ręczne wpisywanie lokalizacji w każdej maszynie i zastąpić je centralnym, kontrolowanym słownikiem.

- 🔴 dodać `Ustawienia → Moduły → Maszyny → Lokalizacje`
- 🔴 w Ustawieniach umożliwić: **Dodaj / Edytuj / Usuń / Zmień kolejność / Aktywuj-Dezaktywuj** lokalizację
- 🔴 każda lokalizacja ma trwałe `id` niezależne od nazwy wyświetlanej; maszyna przechowuje powiązanie po `id`, nie tylko po tekście
- 🔴 minimalne pola lokalizacji: `id`, `nazwa`, `aktywna`, `kolejność`; opcjonalnie `kod`, `opis/uwagi`
- 🔴 w formularzu Dodaj/Edytuj maszynę zastąpić wolny tekst `Lokalizacja` wyborem z listy zdefiniowanych lokalizacji
- 🔴 umożliwić zmianę przypisania lokalizacji maszyny bez zmiany innych danych maszyny
- 🔴 lokalizacja ma być widoczna na głównej liście Maszyn przed statusem oraz dostępna w wyszukiwaniu/filtrowaniu
- 🔴 usuwanie lokalizacji używanej przez maszyny ma być blokowane albo wymagać przepięcia tych maszyn do innej lokalizacji; nigdy nie usuwać powiązań po cichu
- 🔴 migracja istniejących wartości tekstowych: zebrać unikalne obecne `lokalizacja`, utworzyć z nich słownik i przypisać maszyny bez utraty danych
- 🔴 po zmianie nazwy lokalizacji wszystkie maszyny mają automatycznie pokazywać nową nazwę dzięki powiązaniu po `id`
- 🟡 rozważyć lokalizację nadrzędną / strukturę `hala → strefa → stanowisko`, ale nie komplikować pierwszej wersji, jeśli nie jest potrzebna
- ⚪ później: opcjonalne powiązanie lokalizacji ze strefą na planie hali / współrzędnymi layoutu

**Sugestia implementacyjna:** pierwsza wersja powinna być prosta — centralny plik/słownik lokalizacji w ROOT, stabilne ID, lista w Ustawieniach i readonly Combobox w edycji maszyny. Nie łączyć od razu z mapą hali; mapę dopiąć dopiero po ustabilizowaniu słownika.

### 5.1B Edytor Maszyn — widok uproszczony / zaawansowany per użytkownik

**Cel:** ograniczyć ilość informacji pokazywanych jednocześnie bez usuwania funkcji z edytora Maszyn.

- 🔴 dodać na dole edytora przełącznik **„Widok uproszczony / Widok zaawansowany”**
- 🔴 **Widok uproszczony** pokazuje przede wszystkim najczęściej używane dane i akcje: numer/nazwa maszyny, status, lokalizacja, zdjęcie, najbliższy przegląd/awarię, podstawowe dane oraz główne przyciski zapisu/akcji
- 🔴 **Widok zaawansowany** udostępnia pełny obecny zakres danych: szczegóły techniczne, pełne dane serwisowe, historię, dokumentację i pozostałe pola
- 🔴 oba tryby korzystają z **jednego edytora i jednej logiki zapisu**; nie tworzyć dwóch niezależnych formularzy ani dwóch modeli danych
- 🔴 po zmianie trybu pokazać użytkownikowi potwierdzenie, czy zapisać nowy widok jako jego domyślny
- 🔴 wybór zapisywać **per zalogowany użytkownik**, powiązany z jego profilem/loginem, a nie globalnie dla komputera lub całego WM
- 🔴 po ponownym zalogowaniu/otwarciu edytora automatycznie użyć ostatnio zapisanego trybu danej osoby
- 🔴 brak zapisanej preferencji → bezpieczny domyślny tryb ustalony centralnie; nie nadpisywać profilu bez decyzji użytkownika
- 🔴 w interfejsie stale pokazywać aktualny tryb, np. `Widok: Uproszczony`, aby użytkownik wiedział, dlaczego część pól jest ukryta
- 🔴 preferencję trzymać w istniejącym modelu profilu użytkownika, np. `ui_preferences.machines_editor_view = simple|advanced`, zamiast tworzyć osobny lokalny plik ustawień
- 🔴 dodać testy regresyjne: zapis trybu użytkownika A nie zmienia trybu użytkownika B; ponowne otwarcie przywraca zapisaną preferencję; oba tryby zapisują te same dane maszyny

**DoD:** każdy użytkownik może pracować w wygodnym dla siebie widoku Maszyn, a przełączanie widoku nie zmienia logiki biznesowej ani danych maszyny.

## 5.2 Przeglądy

- ✅ konfiguracja przeglądów została uproszczona w kodzie
- 🔴 możliwość przypisania więcej niż jednego miesiąca przeglądu
- 🔴 pełna historia wykonanych przeglądów
- 🔴 polskie, jednoznaczne statusy i alerty
- 🔴 kreator zaległych przeglądów: lista → wykonano / pomiń → data → następny termin
- ⚪ **Zakres przeglądu okresowego per maszyna** — każda karta maszyny ma własną checklistę punktów do wykonania; cykliczny przegląd/Dyspozycja pobiera tę checklistę i zapisuje wykonane punkty oraz uwagi. Docelowo osobne zakresy np. miesięczny / kwartalny / roczny.

## 5.3 Serwis / naprawy

- 🔴 pełna historia serwisowa maszyny
- 🔴 możliwość dodania archiwalnego przeglądu / serwisu / naprawy
- 🔴 automatyczne zasilanie historii po wykonaniu operacji

## 5.4 Elektroniczna karta maszyny

- 🔴 karta maszyny w Wordzie
- 🔴 automatyczne dopisywanie wykonanych przeglądów i napraw
- 🔴 równoległa historia w JSON w ROOT
- 🔴 spójny identyfikator maszyny między JSON i dokumentem Word

## 5.5 Panel główny — „Maszyny — wymagające uwagi”

**Cel:** sekcja ma pokazywać wszystkie maszyny, które faktycznie wymagają reakcji, a nie tylko wybrane statusy serwisowe.

- 🔴 `Sprawna` → nie pokazywać w tej sekcji
- 🔴 `Awaria` → zawsze pokazywać; najwyższy priorytet i najmocniejsze oznaczenie, np. czerwone
- 🔴 `Serwis / przegląd` → zawsze pokazywać; niższy priorytet niż awaria, np. pomarańczowe/żółte oznaczenie
- 🔴 inne statusy problemowe/ostrzegawcze → pokazywać, jeśli system klasyfikuje je jako wymagające reakcji
- 🔴 logika filtra ma wynikać z zasady **„pokaż każdą maszynę, która nie jest faktycznie sprawna”**, a nie z ręcznego sprawdzania tylko jednego statusu
- 🔴 dodać test regresyjny: `Sprawna` → brak na liście, `Awaria` → jest, `Serwis / przegląd` → jest, inny status problemowy → jest

**DoD:** jedna maszyna ma kompletną kartę: dane → lokalizacja → terminy → przeglądy → naprawy → historia → dokumentacja.

> **Uwaga:** stara roadmapa przewidywała usunięcie modułu „Serwis”. Ten kierunek jest wycofany; aktualny rozwój WM traktuje obsługę serwisową jako część domeny Maszyn.

---

# 6. ETAP V — NARZĘDZIA 2.0 🟠

- ✅ edytor narzędzia oraz otwieranie narzędzia z Dyspozycji są obecne
- ✅ eksport kart narzędzi do PDF z obsługą polskich znaków jest obecny
- 🟡 odświeżanie i wydajność listy narzędzi
- 🟡 walidacja formularzy + czytelne błędy
- 🟡 historia NN ↔ SN i ochrona przed duplikatami
- 🔴 naprawić migrację `NN → SN`, aby nie gubiła zadań
- 🔴 łączenie zadań Dyspozycji z zadaniami narzędzia
- 🔴 możliwość zmiany statusu narzędzia z Dyspozycji
- 🔴 archiwalne etapy: przegląd / serwis / ostrzenie / naprawa itd.
- 🔴 wspólna historia narzędzia

**DoD:** narzędzie posiada stabilny numer, zadania, status, historię i poprawne relacje z Dyspozycjami.

---

# 7. ETAP VI — UPRAWNIENIA 🟠

- ✅ istnieje system ról i ograniczeń modułów
- ✅ dostęp jest sprawdzany w kilku miejscach
- 🟡 scalić mechanizmy dostępu w jeden model
- 🔴 rozdzielić uprawnienia na: `odczyt / dodawanie / edycja / usuwanie / administracja`
- 🔴 testy uprawnień dla ról: administrator / kierownik / brygadzista / operator / gość
- 🔴 jeden punkt prawdy dla widoczności i akcji

**DoD:** użytkownik widzi dokładnie to, do czego ma uprawnienia, a backend/GUI egzekwuje to w każdym module.

---

# 7A. PROFIL / URLOPY / EWIDENCJA 🟠

**Cel:** rozbudować Profil o planowane nieobecności i późniejsze rozliczenie czasu pracy bez tworzenia drugiego, równoległego źródła danych.

- ✅ istnieje minimalna ewidencja obecności `attendance_utils.py` z planem zmiany, logowaniem, potwierdzaniem obecności oraz powodami `L4 / UR / UŻ / ŚW`
- 🟡 wykorzystać istniejącą ewidencję obecności jako fundament i ustalić mapowanie istniejącego `UR` do docelowych typów urlopu; nie zmieniać historycznych danych bez migracji
- 🔴 ujednolicić edycję profilu użytkownika w jednym miejscu
- 🔴 dodać osobną zakładkę `Profil → Urlopy`
- 🔴 na początek obsłużyć **urlopy planowane**: typ, data od, data do, liczba dni/godzin, uwaga i status planu
- 🔴 użytkownik widzi swoje planowane nieobecności i wykorzystanie limitów; Brygadzista ma podgląd planowanych nieobecności pracowników
- 🔴 widok roczny oparty o **rok kalendarzowy** z wyborem roku oraz podsumowaniem wykorzystania
- 🔴 typ `U` — urlop wypoczynkowy: domyślny limit 20 albo 26 dni zależnie od uprawnienia pracownika; limit przechowywany per użytkownik, nie jako jedna sztywna wartość globalna
- 🔴 typ `UŻ` — urlop na żądanie: do 4 dni w roku kalendarzowym, liczony w ramach puli urlopu wypoczynkowego `U`, a nie jako dodatkowe 4 dni
- 🔴 typ `ŚW/SW` — zwolnienie z powodu siły wyższej: ewidencja limitu 2 dni albo 16 godzin w roku kalendarzowym oraz wykorzystania w wybranym sposobie rozliczania
- 🔴 wartości prawne/limity muszą być konfigurowalne i przed wdrożeniem produkcyjnym zweryfikowane z aktualnym stanem polskiego prawa pracy — nie kodować ich bez możliwości zmiany
- 🔴 walidacja nakładania się terminów urlopów oraz czytelny kalendarz/lista planów
- ⚪ później: kalendarz zespołu dla Brygadzisty z jednoczesnymi nieobecnościami
- ⚪ później: liczenie dniówek/czasu pracy na podstawie grafiku zmian, dni roboczych, świąt, obecności i zatwierdzonych nieobecności
- ⚪ później: zestawienia miesięczne i roczne — plan / przepracowane / urlop / L4 / UŻ / ŚW / inne

**DoD:** Profil pokazuje użytkownikowi i Brygadziście jednoznaczny plan nieobecności oraz roczne wykorzystanie limitów, a dane są zgodne z ewidencją obecności i nie są dublowane.

---

# 8. ETAP VII — UI / UX 🟡

- ✅ centralny system motywów istnieje
- ✅ globalny znak wodny jest konfigurowalny
- ✅ Ustawienia — pierwszy etap wyboru kolorów ma próbkę, przycisk wyboru i przywracanie wartości domyślnej; Wygląd ma podgląd motywu/czcionki
- 🟡 ujednolicić wizualnie: Dyspozycje / Narzędzia / Maszyny
- 🟡 ujednolicić czcionki i nagłówki bez zmiany logiki
- 🟡 Ustawienia — kontynuować zasadę „więcej wyboru, mniej wpisywania” dla list, dat, progów, statusów i ścieżek
- 🔴 usunąć/ukryć zbędne skróty klawiszowe z Ustawień
- 🔴 Enter wysyła opinię
- 🔴 spójne komunikaty błędów i walidacji
- 🔴 spójne przyciski „Zapisz / Anuluj / Odśwież / Usuń”

---

# 9. ETAP VIII — WYDAJNOŚĆ 🟡

- 🟡 zmniejszyć liczbę pełnych skanów katalogów JSON
- 🟡 cache indeksów Narzędzi i wybranych danych
- 🟡 odświeżać tylko zmieniony rekord, gdy jest to możliwe
- 🟡 nie blokować GUI podczas większego ładowania
- 🔴 pomiar czasu otwarcia kluczowych modułów
- 🔴 regresja wydajności dla listy narzędzi / Dyspozycji

---

# 10. ETAP IX — DOKUMENTACJA I WYDANIE ⚪

- 🟡 aktualny README opisujący uruchomienie i ROOT
- 🔴 USER GUIDE dla użytkowników warsztatu
- 🔴 opis struktury danych ROOT
- 🔴 procedura backup / restore
- 🔴 instrukcja migracji danych
- 🔴 przygotowanie stabilnego builda EXE
- ⚪ przygotowanie do integracji `Rozwiniecie → main`
- ⚪ wydanie 1.0 dopiero po zamknięciu czerwonych punktów rdzenia

---

# 11. Zgłoszenia użytkowników — źródło wymagań

Roadmapa uwzględnia zgłoszenia zebrane w module opinii, w szczególności:

- ROOT Chatu i danych
- ewidencję obecności
- edycję Profilu i planowane urlopy
- roczne limity/podsumowania `U / UŻ / ŚW` oraz przyszłe liczenie dniówek
- szybkie daty Dyspozycji
- zadania Dyspozycji
- priorytety automatyczne
- automatyczne Dyspozycje z przeglądów
- zadania Narzędzi z Dyspozycji
- stabilność powiązań Narzędzie ↔ Dyspozycja
- lokalizacje Maszyn
- widok uproszczony / zaawansowany edytora Maszyn zapisywany per użytkownik
- przeglądy i historię serwisową
- elektroniczną kartę maszyny
- kreator zaległych przeglądów
- archiwalne etapy Narzędzi
- wydruki Dyspozycji do ROOT
- spójność UI
- Ustawienia: więcej wyboru i podglądów, mniej ręcznego wpisywania
- Planista → Zlecenia: osobne kolumny zlecenia wewnętrznego i warsztatowego, zgodne także z finalnym runtime
- Surowce → Półprodukty: jedno źródło prawdy dla listy surowców i automatyczna nazwa `Rodzaj + Fi/Wymiar`

---

# 12. Zasady pracy na gałęzi `Rozwiniecie`

1. **Najpierw naprawa, potem nowa funkcja.**
2. Zmiana danych musi mieć test regresyjny.
3. Nowy plik danych musi korzystać z centralnego ROOT.
4. Nowe ustawienie musi trafić do `settings_schema.json` i `ConfigManager`.
5. Nie dublujemy mechanizmów, jeśli istnieje już rozwiązanie centralne.
6. Nie zmieniamy logiki biznesowej przy samym ujednolicaniu UI.
7. Każda większa zmiana kończy się wpisem w tej roadmapie.
8. Przy zmianach formularzy i ekranów uwzględniamy globalny system pomocy `!` przy istotnych polach, przyciskach i opcjach; używamy wspólnego mechanizmu WM.

---

# 13. Najbliższa kolejność prac

### 🔴 P0 — najpierw
1. Planista → Zlecenia: rozdzielenie `Zlecenie wew` / `Zlecenie warsztatowe` w finalnym runtime
2. Surowce → Półprodukty: jedno źródło listy + automatyczna nazwa surowca

### 🔴 Faza A — po P0
3. ROOT i wszystkie ścieżki danych
4. ConfigManager / Ustawienia
5. Refresh/lifecycle GUI
6. testy regresyjne rdzenia

### 🔴 Faza B
7. Dyspozycje 2.0
8. Maszyny / Serwis 2.0

### 🟠 Faza C
9. Narzędzia 2.0
10. Historia / Audyt biznesowy
11. Uprawnienia
12. Profil / Urlopy / Ewidencja

### 🟡 Faza D
13. UI / UX
14. Wydajność

### ⚪ Faza E
15. Dokumentacja
16. EXE / release
17. `Rozwiniecie → main`

---

# 14. Historyczna roadmapa

Poprzednia wersja dokumentu zawierała „TRYB NAPRAWCZY Q4-2025”. Została zastąpiona aktualnym planem 2026, ponieważ część założeń z 2025 r. jest już wykonana albo nie odpowiada obecnemu kierunkowi WM.

Nie usuwamy historii zmian z Git — ten dokument opisuje aktualny plan, a historię wcześniejszych roadmap zapewnia Git.