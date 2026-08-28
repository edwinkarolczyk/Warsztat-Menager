# ROADMAP — Warsztat Menager

> **Aktualizacja:** 2026-08-28  
> **Gałąź robocza:** `Rozwiniecie`  
> **Cel bieżący:** stabilizacja WM + dopięcie rzeczy wynikających z codziennego użycia programu.  
> **Zasada:** najpierw rdzeń, spójność danych i niezawodność; dopiero potem nowe duże funkcje.

## Status oznaczeń

- ✅ **Gotowe / działa w kodzie**
- 🟡 **Częściowo gotowe / wymaga dopięcia**
- 🔴 **Do wykonania**
- ⚪ **Później / po stabilizacji**

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
- 🟡 ograniczyć ręczne wyjątki i równoległe mechanizmy konfiguracji
- 🟡 każdy nowy parametr ma trafiać do schema + ConfigManager
- 🟡 sprawdzić pełny cykl: zmień → zapisz → zamknij → uruchom → odczytaj
- 🔴 pełna walidacja konfiguracji i czytelny komunikat o błędzie zapisu
- 🔴 migracje konfiguracji między wersjami

**DoD:** ustawienia mają jedno źródło prawdy i zachowują się identycznie w całym WM.

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

**DoD:** Dyspozycje są szybkie w tworzeniu, stabilne przy edycji i mogą być generowane z terminów serwisowych.

---

# 5. ETAP IV — MASZYNY / SERWIS 2.0 🔴

## 5.1 Dane maszyny

- ✅ edycja techniczna i zdjęcie maszyny są dostępne
- 🟡 jednoznaczne źródło prawdy dla danych maszyn
- 🔴 lokalizacja maszyny — naprawić i ujednolicić
- 🔴 lokalizacja widoczna w głównym widoku przed statusem

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

# 8. ETAP VII — UI / UX 🟡

- ✅ centralny system motywów istnieje
- ✅ globalny znak wodny jest konfigurowalny
- 🟡 ujednolicić wizualnie: Dyspozycje / Narzędzia / Maszyny
- 🟡 ujednolicić czcionki i nagłówki bez zmiany logiki
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
- szybkie daty Dyspozycji
- zadania Dyspozycji
- priorytety automatyczne
- automatyczne Dyspozycje z przeglądów
- zadania Narzędzi z Dyspozycji
- stabilność powiązań Narzędzie ↔ Dyspozycja
- lokalizacje Maszyn
- przeglądy i historię serwisową
- elektroniczną kartę maszyny
- kreator zaległych przeglądów
- archiwalne etapy Narzędzi
- wydruki Dyspozycji do ROOT
- spójność UI

---

# 12. Zasady pracy na gałęzi `Rozwiniecie`

1. **Najpierw naprawa, potem nowa funkcja.**
2. Zmiana danych musi mieć test regresyjny.
3. Nowy plik danych musi korzystać z centralnego ROOT.
4. Nowe ustawienie musi trafić do `settings_schema.json` i `ConfigManager`.
5. Nie dublujemy mechanizmów, jeśli istnieje już rozwiązanie centralne.
6. Nie zmieniamy logiki biznesowej przy samym ujednolicaniu UI.
7. Każda większa zmiana kończy się wpisem w tej roadmapie.

---

# 13. Najbliższa kolejność prac

### 🔴 Faza A — teraz
1. ROOT i wszystkie ścieżki danych
2. ConfigManager / Ustawienia
3. Refresh/lifecycle GUI
4. testy regresyjne rdzenia

### 🔴 Faza B
5. Dyspozycje 2.0
6. Maszyny / Serwis 2.0

### 🟠 Faza C
7. Narzędzia 2.0
8. Historia / Audyt biznesowy
9. Uprawnienia

### 🟡 Faza D
10. UI / UX
11. Wydajność

### ⚪ Faza E
12. Dokumentacja
13. EXE / release
14. `Rozwiniecie → main`

---

# 14. Historyczna roadmapa

Poprzednia wersja dokumentu zawierała „TRYB NAPRAWCZY Q4-2025”. Została zastąpiona aktualnym planem 2026, ponieważ część założeń z 2025 r. jest już wykonana albo nie odpowiada obecnemu kierunkowi WM.

Nie usuwamy historii zmian z Git — ten dokument opisuje aktualny plan, a historię wcześniejszych roadmap zapewnia Git.
