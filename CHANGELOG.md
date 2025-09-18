## 2025-09-18 — Fallback typów ZW/ZN/ZM/ZZ w zleceniach
- Dodano domyślne typy zleceń (ZW/ZN/ZM/ZZ) z prefixami i statusami w `zlecenia_utils.py`.
- `_orders_types()` teraz **scala** wartości z `config.json` z domyślnymi i loguje wynik (`[WM-DBG][ZLECENIA] types=...`).
- Dzięki temu błąd „Nieznany rodzaj: ZW” nie wystąpi nawet przy brakującym/niepełnym configu.

## 2025-09-18 — Stabilizacja kreatora zleceń (ZW/ZN/ZM/ZZ)
- Ujednolicono przekazywanie danych z kreatora: teraz trafiają **proste pola**
  (`produkt`, `narzedzie_id`, `maszyna_id`, `material`, `ilosc`, itp.), bez
  słownika `powiazania`.
- `zlecenia_utils.create_order_skeleton(...)` przyjmuje jawne argumenty i **nie
  wymaga** `powiazania`. Ma bezpieczne fallbacki i walidacje typów.
- Poprawiono gałęzie ZN/ZM/ZZ w kreatorze, by nie przekazywały struktur, które
  potem są traktowane jak słowniki (błąd „string indices must be integers”).
- Dodatkowe osłony na błędne typy w utils (statusy, zapis).

## 2025-09-18 — Poprawka funkcji statuses_for
- Naprawiono błąd w `zlecenia_utils.py`, który powodował wyjątek
  (`'str' object has no attribute 'get'`) przy odczycie statusów z configa.
- Funkcja `statuses_for` teraz sprawdza typ danych i bezpiecznie zwraca listę statusów
  lub pustą listę, gdy struktura jest niepoprawna.

## 2025-09-18 — Cleanup Magazynu
- Usunięto plik `gui_magazyn_order.py` (stary kreator zamówień).
- W `gui_magazyn.py` podłączono wyłącznie nowy kreator zleceń (`open_order_creator`).
- Wszystkie operacje zakupowe teraz realizowane są przez moduł Zleceń (typ ZZ).

## 2025-09-18 — Integracja Magazynu z Kreatorem Zleceń
- Usunięto stary przycisk „Dodaj zamówienie” w module Magazyn.
- Zastąpiono go przyciskiem otwierającym kreator zleceń (`open_order_creator`).
- Dzięki temu wszystkie zamówienia/zakupy przechodzą przez jeden wspólny kreator.

## 2025-09-18 — Zlecenie Zakupu (ZZ)
- Dodano nowy typ zlecenia: ZZ (Zlecenie zakupu).
- Kreator ZZ: wybór materiału z katalogu magazynu albo wpisanie nowego materiału ręcznie.
- Obsługa pól: materiał, ilość, dostawca, termin.
- Przy zapisie ZZ tworzony jest draft w `data/zamowienia_oczekujace.json`.
- Nowe materiały (spoza magazynu) oznaczane są flagą `"nowy": true`.

# Changelog

## 2025-09-18 — Poprawki modułu Zleceń
- Naprawiono obsługę ConfigManager w `zlecenia_utils.py` (użycie instancji zamiast metody klasy).
- Naprawiono błąd w `gui_zlecenia_creator.py` przy wczytywaniu `data/maszyny.json` (obsługa listy i dict).
- Zabezpieczono kreator ZM przed awarią przy nietypowej strukturze pliku maszyn.

## [Unreleased]
- [LOGOWANIE] Dodano przełącznik w ustawieniach systemu umożliwiający włączenie przycisku "Logowanie bez PIN" dla brygadzisty.

## 1.5.1 - 2025-09-09
- [USTAWIENIA] Zapis plików bez znaku BOM.
- [NARZĘDZIA] Limit typów i statusów do 8 × 8.
- [UI] Helper `TopMost` wymusza okno na wierzchu.
- [PATCHER] Obsługa paczek ZIP.

## 1.1.3 - 2025-08-19
- [NOWE] Okno z listą zmian wyświetlane po aktualizacji.
- [NOWE] Obsługa pliku CHANGELOG.md w aplikacji.
- [NOWE] Magazyn i BOM – zakładka, walidacja, rezerwacje, integracja ze Zleceniami (E3).

## 1.1.4 - 2025-08-20
- [NARZĘDZIA] Dodano obsługę obrazów oraz plików DXF z generowaną
  miniaturą i podglądem na liście.

## 1.1.5 - 2025-08-21
- [USER] Możliwość definiowania `disabled_modules` ukrywającego moduły w panelu.

## 1.5.0
- Moduł Ustawień obsługuje 7 zakładek, tooltipy i ostrzega o niezapisanych zmianach.
- Kopie zapasowe pliku `config.json` trafiają do katalogu `backup_wersji/`.
- Ciemny motyw interfejsu.
- Dodane klucze: NN/SN, QR, rezerwacje, BOM, siatka 4 px, punkt startowy, ściany i omijanie.
