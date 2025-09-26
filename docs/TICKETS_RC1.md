# WM – RC1 Ticket Checklist

## Szablon zgłoszenia
**Priorytet:** KRYTYCZNY / ŚREDNI / NISKI

**Checklista:**
- [ ] Reprodukcja naprawiona
- [ ] Smoke test OK
- [ ] Brak nowych wyjątków w logach

## Rejestr zgłoszeń
| ID | Priorytet | Moduł | Opis | Status | Właściciel | Uwagi |
|----|-----------|-------|------|--------|------------|-------|
|    |           |       |      |        |            |       |

### Audyt 2025-09-26 — zgłoszenia FAIL
- [MAGAZYN] Brak pliku magazynu w ścieżce konfiguracyjnej | Uruchom audyt z Ustawień → Testy/Audyt | Audyt potwierdza istnienie `warehouse.stock_source` | Raport wskazuje `[FAIL] warehouse.stock_source` | `C:\\wm\\data/logs/audyt_wm-20250926-155310.txt` | KRYTYCZNY
- [BOM] Nie znaleziono źródła BOM | Uruchom audyt systemowy | Plik `bom.file` istnieje w katalogu danych | Audyt zgłasza brak `bom.file` | `C:\\wm\\data/logs/audyt_wm-20250926-155310.txt` | KRYTYCZNY
- [NARZĘDZIA] Brak słownika typów narzędzi | Uruchom audyt | Odczyt `tools.types_file` kończy się sukcesem | Audyt zgłasza `[FAIL] tools.types_file` | `C:\\wm\\data/logs/audyt_wm-20250926-155310.txt` | KRYTYCZNY
- [NARZĘDZIA] Brak słownika statusów | Uruchom audyt | Audyt potwierdza `tools.statuses_file` | Raport zawiera `[FAIL] tools.statuses_file` | `C:\\wm\\data/logs/audyt_wm-20250926-155310.txt` | ŚREDNI
- [NARZĘDZIA] Brak szablonów zadań | Uruchom audyt | Plik `tools.task_templates_file` dostępny | Audyt zgłasza `[FAIL] tools.task_templates_file` | `C:\\wm\\data/logs/audyt_wm-20250926-155310.txt` | ŚREDNI

## Notatki
- Dokumentuj decyzje architektoniczne dotyczące RC1.
- Aktualizuj status po każdym teście regresyjnym.
