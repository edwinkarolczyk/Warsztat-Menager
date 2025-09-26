#!/usr/bin/env python3
"""Narzędzie do przygotowania paczki dokumentów RC1 oraz raportu healthcheck."""

from __future__ import annotations

import datetime
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent.parent


def p(*parts: str) -> str:
    """Zwraca ścieżkę w repozytorium względem katalogu głównego."""

    return str(ROOT.joinpath(*parts))


FILES_UNUSED_MD = """# WM – Pliki archiwalne i nieużywane

Ten dokument zbiera zasoby, które pozostają w repozytorium wyłącznie ze względów
archiwalnych lub pomocniczych. Nie powinny wpływać na bieżący rozwój aplikacji.

---

## Dane historyczne (JSON)
- `data/maszyny.json` – **legacy** (obowiązuje `data/maszyny/maszyny.json`).
- `data/profile.json` – **legacy** (obowiązuje `data/profiles.json`).

## Archiwa i zrzuty
- `Karty przeglądów i napraw.zip` – archiwum testowe.
- `wm_json_demo_20.zip` – paczka demonstracyjna.
- `drive-download-2025*.zip` – paczki pobrane zewnętrznie.
- `Harmonogram przeglądów i napraw na 2025.xlsm` – materiał referencyjny.

## Grafiki i ikony testowe
- `11.ico` – ikona testowa.
- `logo.png` – stare logo testowe.
- `ChatGPT Image *.png` – podglądy generowane podczas testów.

---

## Wskazówki utrzymaniowe
- Pliki z tej listy nie powinny być ładowane w kodzie aplikacji.
- W przypadku dodania nowych artefaktów archiwalnych dopisz je do dokumentu.
- Przed usunięciem upewnij się, że nie są referencjonowane w dokumentacji zewnętrznej.
"""


TICKETS_MD = """# WM – RC1 Ticket Checklist

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

## Notatki
- Dokumentuj decyzje architektoniczne dotyczące RC1.
- Aktualizuj status po każdym teście regresyjnym.
"""


ROADMAP_MD = """# WM – Roadmapa RC1

Celem jest stworzenie stabilnej wersji **Release Candidate 1**, która "po prostu działa".
Brak nowych ficzerów – tylko naprawy i stabilizacja.

---

## Kryteria „działa”
- Start programu bez wyjątków.
- Zamknięcie programu bez wyjątków.
- Moduły: Ustawienia, Profile, Narzędzia, Zlecenia, Maszyny → działają poprawnie w podstawowym zakresie.

---

## Priorytety napraw
1. **ScrollableFrame / TclError** – Ustawienia (KRYTYCZNY)
2. **Niewidoczne napisy na przyciskach** – Theme/UI (KRYTYCZNY)
3. **Maszyny – jedno źródło danych** (KRYTYCZNY)
4. **Widoczność przycisku „Profil”** – Profile (ŚREDNI)
5. **Zlecenia – niespójne typy/statusy** (ŚREDNI)
6. **Narzędzia – usunięcie możliwości dodawania typu w edycji** (ŚREDNI)
7. **Motywy dodatkowe (Warm, Holiday)** – stabilizacja stylów (NISKI)
8. **Magazyn – niejasne etykiety (tooltipy)** (NISKI)
9. **Hala – renderer opcjonalny** (NISKI)
10. **Git/Auto-update – czytelne komunikaty przy dirty** (NISKI)

---

## Harmonogram (7 dni sprint)
- **Dzień 1–2:** Naprawa krytycznych (1–3).
- **Dzień 3–4:** Naprawa średnich (4–6).
- **Dzień 5–6:** Naprawa niskich (7–10).
- **Dzień 7:** Testy smoke, raport RC1, ewentualne poprawki.

---

## Definicja ukończenia (DoD)
- Brak błędów krytycznych w logach.
- Moduły działają w podstawowym zakresie.
- Dokumentacja uzupełniona (`FILES_UNUSED.md`, `TICKETS_RC1.md`, `ROADMAP_RC1.md`).
"""


def write_if_absent(path: str, content: str) -> bool:
    """Zapisuje plik tylko jeśli nie istnieje. Zwraca True gdy utworzono."""

    file_path = Path(path)
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content.strip() + "\n", encoding="utf-8")
        return True
    return False


def quick_json_try(path: str) -> Tuple[bool, str]:
    if not Path(path).exists():
        return (False, "brak pliku")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            json.load(handle)
        return (True, "OK")
    except Exception as exc:
        return (False, f"JSON błąd: {exc.__class__.__name__}: {exc}")


def detect_tk_version() -> Tuple[str, str]:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        version = root.tk.call("info", "patchlevel")
        root.destroy()
        return ("OK", version)
    except Exception as exc:  # pragma: no cover - zależne od środowiska
        return ("ERR", f"{exc.__class__.__name__}: {exc}")


def run_healthcheck() -> tuple[str, bool]:
    lines = []
    add = lines.append
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add(f"[WM][Healthcheck] start {timestamp}")
    ok_all = True

    checks = [
        ("Config", Path(p("config.json")).exists()),
        (
            "Maszyny PRIMARY (data/maszyny/maszyny.json)",
            Path(p("data", "maszyny", "maszyny.json")).exists(),
        ),
        (
            "Maszyny LEGACY (data/maszyny.json)",
            Path(p("data", "maszyny.json")).exists(),
        ),
        (
            "Profiles (data/profiles.json or data/profile.json)",
            Path(p("data", "profiles.json")).exists()
            or Path(p("data", "profile.json")).exists(),
        ),
        (
            "Narzędzia (katalog data/narzedzia|narzędzia)",
            Path(p("data", "narzedzia")).exists()
            or Path(p("data", "narzędzia")).exists(),
        ),
        ("Zlecenia (katalog data/zlecenia)", Path(p("data", "zlecenia")).exists()),
        ("Magazyn (data/magazyn.json)", Path(p("data", "magazyn.json")).exists()),
    ]

    for name, result in checks:
        add(f"- {name}: {'OK' if result else 'BRAK'}")
        ok_all &= bool(result)

    for label, abs_path in [
        ("data/maszyny/maszyny.json", p("data", "maszyny", "maszyny.json")),
        ("data/maszyny.json (LEGACY)", p("data", "maszyny.json")),
        ("data/magazyn.json", p("data", "magazyn.json")),
        ("data/profiles.json", p("data", "profiles.json")),
        ("data/profile.json (LEGACY)", p("data", "profile.json")),
    ]:
        exists = Path(abs_path).exists()
        valid, message = quick_json_try(abs_path) if exists else (False, "brak pliku")
        add(f"- Walidacja {label}: {'OK' if valid else message}")
        ok_all &= (not exists) or valid

    tk_status, tk_info = detect_tk_version()
    if tk_status == "OK":
        add(f"- Tk version: {tk_info}")
    else:
        add("- Tk version: nieustalona")
        add(f"  (Uwaga: {tk_info})")

    add(f"[WM][Healthcheck] wynik: {'OK' if ok_all else 'PROBLEMY WYKRYTE'}")
    return "\n".join(lines), ok_all


def main() -> int:
    created = []
    if write_if_absent(p("docs", "FILES_UNUSED.md"), FILES_UNUSED_MD):
        created.append("docs/FILES_UNUSED.md")
    if write_if_absent(p("docs", "TICKETS_RC1.md"), TICKETS_MD):
        created.append("docs/TICKETS_RC1.md")
    if write_if_absent(p("docs", "ROADMAP_RC1.md"), ROADMAP_MD):
        created.append("docs/ROADMAP_RC1.md")

    print("[WM][RC1] Dokumentacja:")
    if created:
        for path in created:
            print("  + utworzono:", path)
    else:
        print("  (nic do utworzenia — wszystkie pliki już istnieją)")

    report_text, ok_all = run_healthcheck()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    report_path = Path(p("reports", f"wm_healthcheck_{stamp}.txt"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text + "\n", encoding="utf-8")

    print("\n[WM][RC1] Raport zapisano:", report_path.relative_to(ROOT))
    print(report_text)

    print("\n[WM][RC1] Proponowane komendy Git:")
    print("  git checkout Rozwiniecie")
    print("  git pull")
    print("  git checkout -b docs/rc1-pack")
    if created:
        for path in created:
            print(f"  git add {path}")
    print(f"  git add {report_path.relative_to(ROOT)}")
    print('  git commit -m "docs: RC1 pack (docs + healthcheck raport)"')
    print("  git push -u origin docs/rc1-pack")

    print("\n[WM][RC1] Kolejne kroki:")
    print("  1) Wpisz w docs/TICKETS_RC1.md konkretne błędy (po jednym wpisie).")
    print("  2) Każdy błąd naprawiaj w osobnej gałęzi (fix/...).")
    print("  3) Po naprawie odpal ponownie ten skrypt i sprawdź raport w reports/.")

    return 0 if ok_all else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("[WM][RC1] Nieoczekiwany błąd w skrypcie:", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
