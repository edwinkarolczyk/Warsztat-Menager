# WM-VERSION: 0.1
# Plik: planista_batch_print_runtime.py
# version: 1.0
"""Jeden PDF A4 i jedno polecenie drukowania dla wielu zleceń Planisty.

Wariant zbiorczy nie zmienia kart pojedynczych ani danych zleceń.
Podgląd PDF nie zapisuje zdarzenia "Wysłano".
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from gui_planista import _work_order_html, _work_order_output_path
from planista_auto_print_runtime import _find_browser
from planista_print_history import (
    PRINT_ERROR, PRINT_PENDING, PRINT_SENT, record_print_event,
)


class BatchPrintError(RuntimeError):
    """Błąd tworzenia lub wysłania jednego zbiorczego PDF."""


def _validated_orders(orders: list[dict]) -> list[dict]:
    if not orders:
        raise BatchPrintError("Nie wybrano żadnego zlecenia do wydruku.")
    result = []
    seen = set()
    for row in orders:
        if not isinstance(row, dict):
            raise BatchPrintError("Nieprawidłowe dane zlecenia do wydruku.")
        oid = str(row.get("id") or "").strip()
        if not oid:
            raise BatchPrintError("Zlecenie do wydruku nie ma numeru.")
        if oid in seen:
            continue
        seen.add(oid)
        result.append(dict(row))
    return result


def combined_work_orders_html(orders: list[dict]) -> str:
    """Łączy istniejące karty bez usuwania QR, rozkroju i operacji.

    Każda karta rozpoczyna nową stronę A4, ale długa karta może zajmować
    kolejne strony. Skrypt automatycznego drukowania każdej karty usuwamy.
    """
    rows = _validated_orders(orders)
    sections = []
    css = None
    for index, order in enumerate(rows):
        document = _work_order_html(order)
        style = re.search(r"<style\b[^>]*>(.*?)</style>", document, re.I | re.S)
        body = re.search(r"<body\b[^>]*>(.*?)</body>", document, re.I | re.S)
        if not style or not body:
            raise BatchPrintError(
                f"Nie można przygotować treści karty {order['id']}."
            )
        if css is None:
            css = style.group(1)
        card = re.sub(
            r"<script\b[^>]*>.*?</script>", "", body.group(1),
            flags=re.I | re.S,
        )
        page_class = "wm-batch-first" if index == 0 else "wm-batch-next"
        sections.append(f'<section class="{page_class}">{card}</section>')

    if not css or "A4 portrait" not in css:
        raise BatchPrintError("Karty muszą mieć format A4.")
    css += (
        "\n.wm-batch-next { break-before: page; page-break-before: always; }\n"
        ".wm-batch-first { break-before: auto; page-break-before: auto; }\n"
    )
    return (
        "<!doctype html><html lang='pl'><head>"
        "<meta charset='utf-8'><title>Zlecenia zbiorcze A4</title>"
        f"<style>{css}</style></head><body>"
        + "".join(sections)
        + "</body></html>"
    )


def _output_path(orders: list[dict]) -> Path:
    root = _work_order_output_path(orders[0]).parent / "zbiorcze"
    root.mkdir(parents=True, exist_ok=True)
    date_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    identifiers = [
        re.sub(r"[^A-Za-z0-9_-]", "_", str(order["id"]))
        for order in orders
    ]
    first = identifiers[0][:24]
    last = identifiers[-1][:24]
    return root / f"zlecenia_{first}-{last}_{date_id}_A4.pdf"


def prepare_batch_pdf(orders: list[dict]) -> Path:
    """Wyrenderuj jeden PDF w Edge/Chrome bez otwierania osobnych kart."""
    rows = _validated_orders(orders)
    html = combined_work_orders_html(rows)
    browser = _find_browser()
    if browser is None:
        raise BatchPrintError(
            "Nie znaleziono Microsoft Edge ani Google Chrome do utworzenia PDF."
        )
    target = _output_path(rows)
    try:
        with tempfile.TemporaryDirectory(prefix="WM_planista_pdf_") as tmp:
            directory = Path(tmp)
            source = directory / "zbiorcze.html"
            source.write_text(html, encoding="utf-8")
            flags = [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pdf-header-footer",
                "--disable-extensions",
                f"--user-data-dir={directory / 'profil'}",
                f"--print-to-pdf={target}",
                source.resolve().as_uri(),
            ]
            timeout = max(90, min(300, len(rows) * 10))
            run = subprocess.run(
                flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=timeout,
                check=False,
            )
            if run.returncode:
                message = run.stderr.decode("utf-8", errors="replace")[-600:]
                raise BatchPrintError(
                    f"Przeglądarka nie utworzyła PDF (kod {run.returncode}). {message}"
                )
        if not target.is_file() or target.stat().st_size < 100:
            raise BatchPrintError("Nie znaleziono wygenerowanego PDF lub plik jest pusty.")
        with target.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise BatchPrintError("Wygenerowany plik nie jest poprawnym PDF.")
        return target
    except Exception as exc:
        target.unlink(missing_ok=True)
        if isinstance(exc, BatchPrintError):
            raise
        raise BatchPrintError(f"Nie udało się przygotować zbiorczego PDF: {exc}") from exc


def _find_sumatra() -> Path | None:
    names = [
        Path(os.environ.get("ProgramFiles", "")) / "SumatraPDF" / "SumatraPDF.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "SumatraPDF" / "SumatraPDF.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "SumatraPDF" / "SumatraPDF.exe",
    ]
    found = shutil.which("SumatraPDF.exe")
    if found:
        names.insert(0, Path(found))
    return next((p for p in names if p.is_file()), None)


def _print_one_pdf(path: Path) -> str:
    """Zleć wydruk jednego pliku PDF, nigdy osobnych HTML."""
    if os.name != "nt":
        raise BatchPrintError(
            "Automatyczny wydruk PDF wymaga Windows. "
            "Plik PDF jest gotowy do ręcznego otwarcia i wydrukowania."
        )
    sumatra = _find_sumatra()
    if sumatra is not None:
        try:
            subprocess.run(
                [str(sumatra), "-print-to-default", "-silent", str(path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise BatchPrintError(f"Nie udało się wysłać PDF przez SumatraPDF: {exc}") from exc
        return "SumatraPDF: jeden zbiorczy PDF"
    try:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
    except Exception as exc:
        raise BatchPrintError(
            "Windows nie obsługuje polecenia »Drukuj« dla plików PDF. "
            "Otwórz przygotowany PDF i wydrukuj go z przeglądarki PDF. "
            f"Szczegóły: {exc}"
        ) from exc
    return "Windows: jedno polecenie drukowania zbiorczego PDF"


def dispatch_batch_print(
    orders: list[dict], *, user: str = "system",
    source: str = "Planista – wydruk zbiorczy",
) -> Path:
    """Wspólne zadanie PDF, lecz odrębna historia dla każdego zlecenia."""
    rows = _validated_orders(orders)
    try:
        path = prepare_batch_pdf(rows)
    except Exception as exc:
        for order in rows:
            record_print_event(
                order, PRINT_ERROR, user=user, source=source,
                details=f"PDF zbiorczy: {exc}",
            )
        raise

    for order in rows:
        record_print_event(
            order, PRINT_PENDING, user=user, source=source,
            details=f"PDF zbiorczy: {path.name}",
        )
    try:
        method = _print_one_pdf(path)
    except Exception as exc:
        for order in rows:
            record_print_event(
                order, PRINT_ERROR, user=user, source=source,
                details=f"PDF: {path.name} — {exc}",
            )
        raise

    for order in rows:
        record_print_event(
            order, PRINT_SENT, user=user, source=source,
            details=f"{method}; plik: {path.name}",
        )
    return path
