# Plan Monitor

Samodzielna aplikacja testowa do monitorowania jednego sieciowego pliku planu
produkcji. Nie importuje ani nie wykorzystuje kodu Warsztat Menager.

## Uruchomienie

```bash
python -m PlanMonitor.main
```

Przy pierwszym uruchomieniu aplikacja poprosi o wskazanie pliku `xls`, `xlsx`
lub `xlsm`. Ustawienia, ręczne mapowanie kolumn oraz słowa kluczowe działu można
później zmienić przyciskiem **Ustawienia**.

Dla starych plików `.xls` biblioteka pandas wymaga opcjonalnego silnika `xlrd`.

## Dane aplikacji

- `config.json` — lokalna konfiguracja użytkownika,
- `snapshots/current_snapshot.json` — ostatni pełny stan planu,
- `reports/history.jsonl` — historia zmian, jeden obiekt JSON na linię,
- `data/pending_dispositions.json` — przygotowane przyszłe dyspozycje WM,
- `logs/plan_monitor.log` — log działania aplikacji.

## Budowanie EXE

Po instalacji zależności i PyInstaller uruchom w katalogu repozytorium:

```bash
pyinstaller --noconfirm --onefile --windowed --name PlanMonitor PlanMonitor/main.py
```
