# -*- coding: utf-8 -*-
"""WM RC1 PACK – helper for documentation housekeeping and diagnostics."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = ROOT / "reports"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


FILES_UNUSED_MD = """# WM – Pliki nieużywane / archiwalne

Ten plik dokumentuje zasoby obecne w repozytorium, które **nie są wykorzystywane przez kod aplikacji WM**.
Pozostają w repozytorium wyłącznie jako archiwum/testy i nie powinny być brane pod uwagę przy rozwoju.

---

## Dane (JSON)
- `data/maszyny.json` – **legacy** (obecnie używamy `data/maszyny/maszyny.json`)
- `data/profile.json` – **legacy** (obecnie używamy `data/profiles.json`)

## Archiwa / pliki pomocnicze
- `Karty przeglądów i napraw.zip` – archiwum testowe
- `wm_json_demo_20.zip` – dane demonstracyjne
- `drive-download-2025*.zip` – paczki pobrane zewnętrznie
- `Harmonogram przeglądów i napraw na 2025.xlsm` – arkusz dokumentacyjny, nie część programu

## Grafiki / ikony testowe
- `11.ico` – ikona testowa
- `logo.png` – stare logo testowe
- `ChatGPT Image *.png` – testowe grafiki podglądowe

---

## Uwagi
- **Nie usuwać** tych plików automatycznie – mogą być potrzebne jako dokumentacja lub do porównań.
- W kodzie WM korzystamy wyłącznie z nowych ścieżek (`data/maszyny/maszyny.json`, `data/profiles.json`, itp.).
- Każdy nowy plik uznany za archiwalny należy dopisać do tej listy.
"""


TICKETS_MD = """# WM – Stabilizacja RC1 (tickets)

Tutaj zapisujemy zgłoszenia błędów oraz zadań do wykonania w ramach wersji RC1.
Każdy błąd = osobna sekcja.

---

## Szablon wpisu

### [MODUŁ] Krótki opis
**Kroki do odtworzenia:**
1. …
2. …
3. …

**Oczekiwane:**
- …

**Rzeczywiste:**
- …

**Log (max 3 linie):**
```
...
```

**Status / właściciel:** …
**Notatki dodatkowe:** …

---

## Lista zgłoszeń RC1

| ID | Priorytet | Moduł | Skrót opisu | Status | Owner | Link do logów |
|----|-----------|-------|-------------|--------|-------|----------------|
|    |           |       |             |        |       |                |

---

## Checklist przed zamknięciem RC1
- [ ] Brak zgłoszeń P0/P1 w statusie innym niż "Gotowe".
- [ ] Wykonane testy regresyjne dla krytycznych ścieżek.
- [ ] Zweryfikowane plany wdrożenia i rollbacku.
- [ ] Aktualne logi i notatki w repozytorium.

## Notatki po stabilizacji
- Co zadziałało dobrze?
- Co należy poprawić w kolejnym cyklu?
- Lista usprawnień dla narzędzi / procesów.
"""


ROADMAP_MD = """# WM – Roadmapa stabilizacji RC1

Dokument śledzący etapy stabilizacji RC1 wraz z kluczowymi kamieniami milowymi.

## Założenia
- RC1 to wydanie kandydujące do publikacji produkcyjnej.
- Każda faza musi mieć przypisaną osobę odpowiedzialną.
- Raportujemy status raz w tygodniu podczas spotkania stabilizacyjnego.

## Fazy
1. **Analiza zgłoszeń** – przegląd rejestru błędów, priorytetyzacja i plan działania.
2. **Implementacja poprawek** – development, code review, smoke testy modułowe.
3. **Regresja** – testy automatyczne/manualne, sanity check środowisk.
4. **Przygotowanie releasu** – komplet dokumentacji, komunikacja z interesariuszami.
5. **Go/No-Go** – decyzja o publikacji lub kolejnym cyklu poprawek.

## Harmonogram przykładowy
| Tydzień | Zadania | Odpowiedzialny |
|---------|---------|----------------|
| T1 | Analiza backlogu, aktualizacja TICKETS_RC1 | ... |
| T2 | Poprawki krytyczne, review planu testów | ... |
| T3 | Pełna regresja, walidacja kryteriów wyjścia | ... |
| T4 | Przygotowanie releasu, komunikacja | ... |

## Ryzyka i mitigacje
- **Brak zasobów QA** – rotacja testerów, priorytetyzacja smoke testów.
- **Niestabilne środowisko testowe** – automatyczne healthchecki, monitoring.
- **Nowe zgłoszenia P0** – szybka triage, dedykowany kanał incident-response.

## Materiały powiązane
- `docs/TICKETS_RC1.md`
- Plan testów QA
- Lista właścicieli modułów oraz kontaktów awaryjnych
"""


@dataclass
class HealthCheckItem:
    """Represents a single file or directory healthcheck entry."""

    label: str
    path: Path
    must_exist: bool = True
    expect_file: bool | None = None  # None = either

    def run(self) -> str:
        if not self.path.exists():
            return f"[MISSING] {self.label} -> {self.path}"
        if self.expect_file is True and not self.path.is_file():
            return f"[WARN] {self.label}: oczekiwano pliku, znaleziono inny typ ({self.path})"
        if self.expect_file is False and not self.path.is_dir():
            return f"[WARN] {self.label}: oczekiwano katalogu, znaleziono plik ({self.path})"
        if self.path.is_file():
            size = self.path.stat().st_size
            if size == 0:
                return f"[WARN] {self.label}: plik pusty ({self.path})"
            return f"[OK] {self.label}: plik istnieje ({self.path}, {size} B)"
        return f"[OK] {self.label}: katalog istnieje ({self.path})"


def ensure_file(path: Path, content: str) -> bool:
    """Create file with content if it does not exist. Returns True if created."""

    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def create_docs() -> List[Path]:
    created: List[Path] = []
    if ensure_file(DOCS_DIR / "FILES_UNUSED.md", FILES_UNUSED_MD):
        created.append(DOCS_DIR / "FILES_UNUSED.md")
    if ensure_file(DOCS_DIR / "TICKETS_RC1.md", TICKETS_MD):
        created.append(DOCS_DIR / "TICKETS_RC1.md")
    if ensure_file(DOCS_DIR / "ROADMAP_RC1.md", ROADMAP_MD):
        created.append(DOCS_DIR / "ROADMAP_RC1.md")
    return created


def run_healthcheck(checks: Iterable[HealthCheckItem]) -> Path:
    now = _dt.datetime.now()
    report_path = REPORTS_DIR / f"wm_healthcheck_{now:%Y%m%d_%H%M}.txt"

    lines = [
        "WM RC1 PACK – Healthcheck raport",
        f"Data: {now:%Y-%m-%d %H:%M}",
        "",
        "Kontrole:",
    ]
    for item in checks:
        lines.append(f"- {item.run()}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def print_git_hints(report_path: Path, created_docs: List[Path]) -> None:
    """Print helper git commands for preparing a PR."""

    print("\nGotowe komendy git do utworzenia PR z dokumentacją:")
    doc_paths = " ".join(str(p.relative_to(ROOT)) for p in created_docs)
    tracked_items = f"{doc_paths} {report_path.relative_to(ROOT)}".strip()
    branch_name = f"docs/rc1-pack-{_dt.datetime.now():%Y%m%d}".lower()
    print(f"git checkout -b {branch_name}")
    if tracked_items:
        print(f"git add {tracked_items}")
    else:
        print("git add docs reports")
    print('git commit -m "Add WM RC1 documentation pack"')
    print(f"git push origin {branch_name}")
    print("gh pr create --title 'Add WM RC1 documentation pack' --body 'Dodaje pakiet dokumentacji RC1.'")


def main() -> None:
    created_docs = create_docs()
    if created_docs:
        print("Utworzono pliki dokumentacji:")
        for doc in created_docs:
            print(f"- {doc.relative_to(ROOT)}")
    else:
        print("Pliki dokumentacji już istniały – nic nie tworzono.")

    checks = [
        HealthCheckItem("Repozytorium – README", ROOT / "README.md", expect_file=True),
        HealthCheckItem("Konfiguracja domyślna", ROOT / "config.defaults.json", expect_file=True),
        HealthCheckItem("Konfiguracja aktywna", ROOT / "config.json", expect_file=True),
        HealthCheckItem("Katalog danych", ROOT / "data", expect_file=False),
        HealthCheckItem("Główny skrypt aplikacji", ROOT / "start.py", expect_file=True),
        HealthCheckItem("Moduł logiki zleceń", ROOT / "zlecenia_logika.py", expect_file=True),
        HealthCheckItem("Logi aplikacji", ROOT / "logi", expect_file=False),
        HealthCheckItem("Dokumentacja RC1 – tickets", DOCS_DIR / "TICKETS_RC1.md", expect_file=True),
    ]

    report_path = run_healthcheck(checks)
    print(f"Zapisano raport healthcheck: {report_path.relative_to(ROOT)}")

    print_git_hints(report_path, created_docs)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - diagnostyka ręczna
        print("Błąd podczas wykonywania WM RC1 PACK")
        print(str(exc))
        raise
