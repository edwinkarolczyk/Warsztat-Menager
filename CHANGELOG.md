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
