# WM-VERSION: 0.1
# Plik: planista_labels_a5_runtime.py
# version: 1.0
"""Etykiety A5 poziomo: duży numer wewnętrzny, QR konkretnej pozycji WM.

Jedno wybrane zlecenie WM = jedna strona A5. Wiele pozycji = jeden PDF.
Wydruk etykiety nie oznacza wydrukowania karty produkcyjnej A4.
"""

from __future__ import annotations

from datetime import date, datetime
import html
from pathlib import Path
import re
import subprocess
import tempfile

import zlecenia_logika as ZL
from gui_planista import (
    _work_order_output_path, _work_order_qr_data_uri,
    _work_order_qr_payload,
)
from planista_auto_print_runtime import _find_browser
from planista_batch_print_runtime import (
    BatchPrintError, _print_one_pdf, _validated_orders,
)


class LabelPrintError(BatchPrintError):
    """Nie udało się przygotować lub wydrukować etykiet A5."""


def _shipping_date(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        return date.fromisoformat(raw[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return raw


def _number_font_size(number: str) -> int:
    """Numer ma być jak największy, bez ucięcia długich oznaczeń."""
    length = max(1, len(number))
    return max(37, min(185, int(560 / max(3, length))))


def build_labels_a5_html(
    orders: list[dict], *, catalog_names: dict[str, str] | None = None,
) -> str:
    """Stwórz jeden dokument: odrębny QR i pełną stronę A5 dla każdej pozycji."""
    rows = _validated_orders(orders)
    catalog = catalog_names or {}
    pages: list[str] = []
    for order in rows:
        oid = str(order["id"]).strip()
        internal = str(order.get("zlec_wew") or "").strip()
        main_number = internal or oid
        heading = "ZLECENIE WEWNĘTRZNE" if internal else "ZLECENIE WARSZTATOWE"
        symbol = str(order.get("produkt") or "").strip()
        display_name = str(catalog.get(symbol) or symbol or "—").strip()
        product = (
            f"{display_name} [{symbol}]"
            if symbol and display_name.casefold() != symbol.casefold()
            else display_name
        )
        raw_qty = order.get("ilosc", 0)
        try:
            qty = float(raw_qty or 0)
            qty_text = str(int(qty)) if qty.is_integer() else f"{qty:g}"
        except (TypeError, ValueError):
            qty_text = str(raw_qty)
        qr = _work_order_qr_data_uri(order)
        qr_content = _work_order_qr_payload(order)
        if not qr or not qr_content:
            raise LabelPrintError(f"Brak kodu QR dla zlecenia {oid}.")
        qr_img = (
            f'<img src="{html.escape(qr, quote=True)}"'
            f' alt="QR pozycji WM {html.escape(oid, quote=True)}">'
        )
        pages.append(
            '<section class="wm-label">'
            '  <div class="label-top">'
            '    <div class="label-number-area">'
            f'      <div class="title">{html.escape(heading)}</div>'
            f'      <div class="main-number" style="font-size:{_number_font_size(main_number)}pt">'
            f'        {html.escape(main_number)}</div>'
            '    </div>'
            '    <div class="label-qr">'
            f'      {qr_img}'
            f'      <div class="wm-id">WM {html.escape(oid)}</div>'
            '    </div>'
            '  </div>'
            '  <div class="label-bottom">'
            '    <div class="ship">'
            '      <div class="small-title">DATA WYSYŁKI</div>'
            f'      <div class="ship-value">{html.escape(_shipping_date(order.get("termin")))}</div>'
            '    </div>'
            '    <div class="product">'
            '      <div class="small-title">PRODUKT</div>'
            f'      <div class="product-value">{html.escape(product)}</div>'
            '    </div>'
            '    <div class="quantity">'
            '      <div class="small-title">ILOŚĆ</div>'
            f'      <div class="qty-value">{html.escape(qty_text)} szt.</div>'
            '    </div>'
            '  </div>'
            '</section>'
        )

    style = """
@page { size: A5 landscape; margin: 5mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; color: #111; font-family: Arial, Helvetica, sans-serif; }
.wm-label {
  width: 198mm; height: 136mm; margin: 0;
  display: flex; flex-direction: column; overflow: hidden;
}
.wm-label:not(:last-child) { break-after: page; page-break-after: always; }
.label-top { display: flex; flex: 1; min-height: 0; gap: 4mm; align-items: stretch; }
.label-number-area {
  flex: 1; min-width: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; overflow: hidden;
}
.title { font-size: 10.5pt; font-weight: bold; letter-spacing: 1.2pt; }
.main-number {
  font-family: Arial, Helvetica, sans-serif;
  font-weight: 900; letter-spacing: -0.045em;
  line-height: 1; white-space: nowrap; text-align: center;
  max-width: 100%;
}
.label-qr {
  width: 55mm; flex: 0 0 55mm; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.label-qr img { display: block; width: 51mm; height: 51mm; image-rendering: pixelated; }
.wm-id { font-size: 11pt; font-weight: bold; margin-top: 1.5mm; }
.label-bottom {
  flex: 0 0 35mm; border-top: 1.5pt solid #111; padding-top: 3mm;
  display: grid; grid-template-columns: 50mm 1fr 28mm; gap: 3mm;
}
.small-title { font-size: 8pt; letter-spacing: .6pt; font-weight: bold; color: #444; }
.ship-value { font-size: 17pt; font-weight: 800; margin-top: 2mm; white-space: nowrap; }
.product-value {
  font-size: 12pt; font-weight: bold; margin-top: 2mm;
  overflow-wrap: anywhere; line-height: 1.2;
}
.qty-value { font-size: 14pt; font-weight: 800; margin-top: 2mm; white-space: nowrap; }
"""
    return (
        "<!doctype html><html lang='pl'><head>"
        "<meta charset='utf-8'><title>Etykiety produkcyjne A5</title>"
        f"<style>{style}</style></head><body>"
        + "".join(pages) + "</body></html>"
    )


def _labels_output_path(orders: list[dict]) -> Path:
    folder = _work_order_output_path(orders[0]).parent / "etykiety"
    folder.mkdir(parents=True, exist_ok=True)
    first = re.sub(r"[^A-Za-z0-9_-]", "_", str(orders[0]["id"]))[:24]
    last = re.sub(r"[^A-Za-z0-9_-]", "_", str(orders[-1]["id"]))[:24]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return folder / f"etykiety_{first}-{last}_{stamp}_A5.pdf"


def prepare_labels_a5_pdf(orders: list[dict]) -> Path:
    """Jeden PDF A5; samo przygotowanie nie zmienia żadnych statusów wydruku."""
    rows = _validated_orders(orders)
    try:
        names = {
            str(rec.get("kod") or "").strip(): str(rec.get("nazwa") or "").strip()
            for rec in ZL.list_produkty()
            if isinstance(rec, dict)
        }
        html_document = build_labels_a5_html(rows, catalog_names=names)
    except Exception as exc:
        if isinstance(exc, LabelPrintError):
            raise
        raise LabelPrintError(f"Nie można przygotować etykiet A5: {exc}") from exc

    browser = _find_browser()
    if browser is None:
        raise LabelPrintError("Nie znaleziono Edge ani Chrome do wygenerowania PDF A5.")
    target = _labels_output_path(rows)
    try:
        with tempfile.TemporaryDirectory(prefix="WM_etykiety_A5_") as folder:
            tmp = Path(folder)
            source = tmp / "etykiety.html"
            source.write_text(html_document, encoding="utf-8")
            command = [
                str(browser), "--headless=new", "--disable-gpu",
                "--no-first-run", "--no-default-browser-check",
                "--no-pdf-header-footer", "--disable-extensions",
                f"--user-data-dir={tmp / 'profil'}",
                f"--print-to-pdf={target}",
                source.resolve().as_uri(),
            ]
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=max(90, min(300, len(rows) * 10)),
                check=False,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", errors="replace")[-600:]
                raise LabelPrintError(
                    f"Przeglądarka nie wygenerowała PDF A5: {detail}"
                )
        if not target.is_file() or target.stat().st_size < 100:
            raise LabelPrintError("Nie powstał poprawny plik PDF A5.")
        with target.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise LabelPrintError("Wygenerowany plik nie jest w formacie PDF.")
        return target
    except Exception as exc:
        target.unlink(missing_ok=True)
        if isinstance(exc, LabelPrintError):
            raise
        raise LabelPrintError(f"Nie udało się przygotować etykiet A5: {exc}") from exc


def dispatch_labels_a5_print(orders: list[dict]) -> Path:
    """Wyślij jeden PDF A5 do drukarki; nie oznaczaj kart A4 jako wydrukowanych."""
    path = prepare_labels_a5_pdf(orders)
    try:
        _print_one_pdf(path)
    except Exception as exc:
        raise LabelPrintError(
            f"Etykiety A5 zostały zapisane w {path}, ale nie udało się wysłać "
            f"ich do drukarki: {exc}"
        ) from exc
    return path
