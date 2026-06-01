# Plan Monitor

Samodzielna aplikacja do monitorowania jednego sieciowego pliku planu
produkcji. Nie importuje ani nie wykorzystuje kodu Warsztat Menager i nie
generuje dyspozycji WM.

## Uruchomienie

```bash
python -m PlanMonitor.main
```

Przy pierwszym uruchomieniu aplikacja poprosi o wskazanie pliku `xls`, `xlsx`
lub `xlsm`. Ustawienia, ręczne mapowanie liter kolumn, arkusz, zakres danych
oraz słowa kluczowe działu można później zmienić przyciskiem **Ustawienia**.

Pliki `xlsx` i `xlsm` są analizowane bezpośrednio przez `openpyxl`: parser
skanuje wielowierszowe nagłówki, czyta cały używany zakres arkusza, dziedziczy
numer zlecenia oraz termin w grupie i nie zatrzymuje się na pustym wierszu.
Dla starych plików `.xls` pozostaje fallback przez pandas, który wymaga
opcjonalnego silnika `xlrd`.

Po każdym odczycie ekran główny pokazuje liczbę przeskanowanych wierszy, liczbę
pozycji i użyte kolumny. Przycisk **Podgląd odczytanych pozycji** wyświetla do
100 pierwszych rekordów parsera. Szczegółowa diagnostyka trafia również do
logu.

## Dane aplikacji

- `config.json` — lokalna konfiguracja użytkownika,
- `snapshots/current_snapshot.json` — ostatni pełny stan planu i metadane parsera,
- `reports/history.jsonl` — historia zmian, jeden obiekt JSON na linię,
- `logs/plan_monitor.log` — log działania aplikacji.

## Budowanie EXE

Po instalacji zależności i PyInstaller uruchom w katalogu repozytorium:

```bash
pyinstaller --noconfirm --onefile --windowed --name PlanMonitor PlanMonitor/main.py
```
