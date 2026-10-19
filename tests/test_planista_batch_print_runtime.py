# WM-VERSION: 0.1
"""Regresje: jeden PDF A4 dla wielu zleceń, QR, historia i brak dubli."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import planista_batch_print_runtime as BATCH
import planista_print_history as HISTORY


def _order(oid):
    return {
        "id": oid, "zlec_wew": "747", "produkt": "Szafka loto",
        "ilosc": 5, "wykonano": 0, "termin": "2026-10-09",
        "rzaz_mm": 2, "plan_polprodukty": {},
        "zapotrzebowanie_surowce": {},
    }


def test_combined_html_has_qr_and_one_new_page_per_order():
    merged = BATCH.combined_work_orders_html([_order("0026"), _order("0027")])

    assert merged.count("ZLECENIE DO WYKONANIA") == 2
    assert "WM:PLANISTA:ORDER:0026" in merged
    assert "WM:PLANISTA:ORDER:0027" in merged
    assert merged.count("class='qr-block'") == 2
    assert "break-before: page" in merged
    assert merged.count('class="wm-batch-next"') == 1
    assert merged.count('class="wm-batch-first"') == 1
    assert merged.count("@page { size: A4 portrait;") == 1
    assert "window.print()" not in merged
    assert merged.count("<style>") == 1


def test_batch_deduplicates_order_ids_and_keeps_their_input_order():
    a, b = _order("0026"), _order("0027")
    merged = BATCH.combined_work_orders_html([b, a, b])
    assert merged.count("ZLECENIE DO WYKONANIA") == 2
    assert merged.index("WM:PLANISTA:ORDER:0027") < merged.index("WM:PLANISTA:ORDER:0026")


def test_batch_pdf_uses_one_chromium_render_and_creates_real_pdf_marker(monkeypatch, tmp_path):
    output = tmp_path / "zbiorcze" / "zlecenia_A4.pdf"
    browser = tmp_path / "chrome.exe"
    seen = []
    monkeypatch.setattr(BATCH, "_find_browser", lambda: browser)
    monkeypatch.setattr(BATCH, "_output_path", lambda _orders: output)

    def pretend_chrome(command, **kwargs):
        seen.append(command)
        assert command[-1].startswith("file:")
        assert "--headless=new" in command
        assert "--no-pdf-header-footer" in command
        assert any(str(part).startswith("--print-to-pdf=") for part in command)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF-1.4\n" + b"1" * 200)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(BATCH.subprocess, "run", pretend_chrome)
    target = BATCH.prepare_batch_pdf([_order("0026"), _order("0027")])
    assert target == output
    assert target.read_bytes().startswith(b"%PDF-")
    assert len(seen) == 1


def test_print_dispatch_sends_single_pdf_and_records_each_order(monkeypatch, tmp_path):
    monkeypatch.setattr(HISTORY, "print_history_path", lambda: tmp_path / "historia.json")
    HISTORY.ensure_print_registry([])
    pdf = tmp_path / "jedna_paczka_A4.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"1" * 200)
    render = []
    sends = []

    def build(orders):
        render.append([row["id"] for row in orders])
        return pdf

    monkeypatch.setattr(BATCH, "prepare_batch_pdf", build)
    monkeypatch.setattr(BATCH, "_print_one_pdf", lambda path: sends.append(path) or "Windows PDF")
    orders = [_order("0026"), _order("0027"), _order("0028")]
    result = BATCH.dispatch_batch_print(orders, user="brygadzista")

    assert result == pdf
    assert render == [["0026", "0027", "0028"]]
    assert sends == [pdf]  # Nie trzy osobne polecenia wydruku!
    for order in orders:
        events = HISTORY.print_events(order["id"])
        assert [event["stan"] for event in events] == [
            HISTORY.PRINT_PENDING, HISTORY.PRINT_SENT
        ]
        assert "jedna_paczka_A4.pdf" in events[-1]["szczegoly"]
        assert events[-1]["uzytkownik"] == "brygadzista"


def test_failed_pdf_print_marks_each_card_failed_without_false_sent(monkeypatch, tmp_path):
    monkeypatch.setattr(HISTORY, "print_history_path", lambda: tmp_path / "historia.json")
    HISTORY.ensure_print_registry([])
    path = tmp_path / "zbiorczy_A4.pdf"
    monkeypatch.setattr(BATCH, "prepare_batch_pdf", lambda _orders: path)

    def fail(_path):
        raise BATCH.BatchPrintError("Drukarka wyłączona")

    monkeypatch.setattr(BATCH, "_print_one_pdf", fail)
    with pytest.raises(BATCH.BatchPrintError, match="Drukarka wyłączona"):
        BATCH.dispatch_batch_print([_order("0026"), _order("0027")])
    for oid in ("0026", "0027"):
        events = HISTORY.print_events(oid)
        assert [event["stan"] for event in events] == [
            HISTORY.PRINT_PENDING, HISTORY.PRINT_ERROR,
        ]
        assert HISTORY.print_status(_order(oid)) == HISTORY.PRINT_ERROR


def test_pdf_preview_does_not_mark_orders_as_sent(monkeypatch, tmp_path):
    monkeypatch.setattr(HISTORY, "print_history_path", lambda: tmp_path / "historia.json")
    HISTORY.ensure_print_registry([])
    pdf = tmp_path / "podglad_A4.pdf"
    monkeypatch.setattr(BATCH, "_find_browser", lambda: tmp_path / "chrome.exe")
    monkeypatch.setattr(BATCH, "_output_path", lambda _orders: pdf)

    def render(_command, **_kwargs):
        pdf.write_bytes(b"%PDF-1.4\n" + b"1" * 150)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(BATCH.subprocess, "run", render)
    BATCH.prepare_batch_pdf([_order("0026"), _order("0027")])

    assert HISTORY.print_events("0026") == []
    assert HISTORY.print_events("0027") == []


def test_gui_has_combined_pdf_preview_and_preserves_single_order_print():
    source = (Path(__file__).resolve().parents[1] / "gui_planista_panel.py").read_text(
        encoding="utf-8"
    )
    assert "Podgląd PDF" in source
    assert "dispatch_batch_print(" in source
    assert "prepare_batch_pdf(" in source
    assert "single=True" in source
    assert "dispatch_work_order_print(" in source
    assert "self._print_orders(order_ids, only_unprinted=True)" in source
