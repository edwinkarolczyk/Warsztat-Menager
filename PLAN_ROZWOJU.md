# WM — Plan rozwoju (źródło prawdy)
> Zasada: zmieniamy tylko to, co potrzebne; wszystko po polsku w UI/logach.

## Moduły i zależności
- Ustawienia, Narzędzia, Magazyn, Zlecenia, Maszyny, Hala/Serwis, Profile, Dashboard, Aktualizacje/Git, Mobile (Kivy).
- Główne zależności: Zlecenia→Magazyn; Hala→Maszyny; wszystko→Ustawienia.

## Stan % i RAG (15.09.2025)
- Ustawienia 70% 🟡
- Narzędzia 80% 🟡
- Magazyn 60% 🟡
- Zlecenia 55% 🟡
- Maszyny 55% 🟡
- Hala/Serwis 45% 🔴
- Profile 50% 🟡
- Dashboard 60% 🟡
- Aktualizacje/Git 70% 🟡
- Mobile (Kivy) 20% 🔴

## Definition of Done (DoD)
**Ustawienia**
- Comboboxy i opisy z `help` (`settings_schema.json`).
- Zakładka „Profile użytkowników” + nazwa przy „Wyloguj”.
- Naprawione okna nad głównym programem (focus/parent).
- Teksty i logi po polsku.

**Narzędzia — twarda reguła Typ→Status→Zadania**
- Model: Typ (≤8) → Statusy (≤8/typ) → Zadania (checklista).
- Edycja: dwuklik, dark, bez tooltipów, wyszukiwarka u góry.
- Limity: twarde 8/8 z komunikatem PL.
- Auto-domknięcie: przy wejściu w **ostatni status** zadania odhaczają się.
- Historia zmian: `narzedzia/NNN.json` z datą, loginem i komentarzem.

**Magazyn**
- Jeden przycisk „➕ Dodaj materiał” (po autoryzacji).
- Nazwy zakładek czytelne.
- Alert progowy z konfiguracji.

**Zlecenia**
- Kreator (Toplevel, dark) + comboboxy.
- Walidacja BOM; brak → pytanie „Zamówić brak?” i draft zamówienia.
- Edycja statusu zlecenia przez combobox.

**Maszyny**
- Kolumna „Awaria [h]”.
- Kropki statusu (zielona stała / czerwona migająca).
- Po usunięciu — znika z widoku hali.
- Na kaflach numer hali zamiast współrzędnych.

**Hala/Serwis**
- Jedna hala: tło JPEG, siatka 20cm (4px), drag&drop zapis do `maszyny/maszyny.json`.
- Serwisanci (Edwin, Dawid, Marek, Sebastian) jako placeholdery.

**Profile**
- Zakładka w Ustawieniach.
- Nazwa użytkownika przy „Wyloguj”.
- Wyłączanie modułów odzwierciedlone w Panelu.

**Dashboard**
- Kafel „Awarie” (licznik aktywnych).
- Opcjonalny start na dashboard.
- Mini-widok hali tylko do odczytu.

**Aktualizacje/Git**
- Ekran „Zmiany lokalne vs zdalne — co robimy?” (3 przyciski).
- Logi PL z tagami [WM-DBG]/[INFO]/[ERROR].

**Mobile (Kivy)**
- APK offline: logowanie, lista maszyn, zgłaszanie awarii.
- Docelowo synchronizacja FTP (bez trybu demo).

---

### 3.1 Sugestie zmian
1. `modules_registry.py` – rejestr modułów i zależności (nowy plik).
2. Start: dialog 3 opcji przy dirty git.
3. Ustawienia: poprawne bindy aktywności (`<Key>`, `<Button>`, `<Motion>`).
4. Magazyn: kanon danych = `data/magazyn/magazyn.json`.
5. Hala: respektować `hall.triple_confirm_delete`.
6. Smoke-testy DoD (1 test na punkt).

---

## Backlog Iteracja A
1. Ustawienia: combobox + opisy (`help`).
2. Narzędzia: edycja Typ→Status→Zadania (8/8, dwuklik, dark, wyszukiwarka) + auto-domknięcie.
3. Magazyn: „➕ Dodaj materiał”.
4. Zlecenia: kreator + combobox + walidacja BOM.
5. Maszyny: kolumna „Awaria [h]” + kropki.
6. Hala: tło+siatka+drag&drop.
7. Profile: zakładka + logout name.
8. Dashboard: kafel „Awarie”.
9. Aktualizacje: ekran porównań.
10. Mobile: szkic APK offline.

---
