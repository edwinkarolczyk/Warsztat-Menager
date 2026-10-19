# WM-VERSION: 0.1
"""A5 poziomo: duży numer, osobny QR pozycji i jeden PDF na wiele etykiet."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import planista_labels_a5_runtime as LABELS
import planista_print_history as HISTORY


def _order(oid, *, internal="747", product="270x100x170", qty=10):
    return {
        "id": oid,
        "zlec_wew": internal,
        "produkt": product,
        "ilosc": qty,
        "termin": "2026-10-09",
    }


def test_three_positions_share_large_internal_number_but_have_separate_qrs(monkeypatch):
    qr_orders = []
    monkeypatch.setattr(
        LABELS, "_work_order_qr_data_uri",
        lambda order: qr_orders.append(order["id"]) or
        f"data:image/png;base64,QR{order['id']}",
    )
    monkeypatch.setattr(
        LABELS, "_work_order_qr_payload",
        lambda order: f"WM:PLANISTA:ORDER:{order['id']}",
    )
    doc = LABELS.build_labels_a5_html(
        [_order("0026"), _order("0027"), _order("0028")],
        catalog_names={"270x100x170": "Szafka loto"},
    )
    assert qr_orders == ["0026", "0027", "0028"]
    assert "@page { size: A5 landscape; margin: 5mm; }" in doc
    assert doc.count('class="wm-label"') == 3
    assert doc.count("ZLECENIE WEWNĘTRZNE") == 3
    assert doc.count("        747</div>") == 3
    assert "QR0026" in doc and "QR0027" in doc and "QR0028" in doc
    assert "WM 0026" in doc and "WM 0027" in doc and "WM 0028" in doc
    assert "Szafka loto [270x100x170]" in doc
    assert "09.10.2026" in doc
    assert "10 szt." in doc
    assert "window.print()" not in doc
    assert "wm-label:not(:last-child)" in doc


def test_label_with_missing_internal_number_identifies_workshop_order(monkeypatch):
    monkeypatch.setattr(
        LABELS, "_work_order_qr_data_uri",
        lambda order: "data:image/png;base64,AAA",
    )
    monkeypatch.setattr(
        LABELS, "_work_order_qr_payload",
        lambda order: f"WM:PLANISTA:ORDER:{order['id']}",
    )
    doc = LABELS.build_labels_a5_html([_order("0026", internal="")])
    assert "ZLECENIE WARSZTATOWE" in doc
    assert "ZLECENIE WEWNĘTRZNE" not in doc
    assert "        0026</div>" in doc


def test_long_internal_number_uses_smaller_font_without_truncation(monkeypatch):
    monkeypatch.setattr(LABELS, "_work_order_qr_data_uri", lambda order: "data:image/png;base64,AAA")
    monkeypatch.setattr(LABELS, "_work_order_qr_payload", lambda order: f"WM:PLANISTA:ORDER:{order['id']}")
    short = LABELS.build_labels_a5_html([_order("1", internal="747")])
    long = LABELS.build_labels_a5_html([_order("2", internal="747012345678")])
    assert 'font-size:185pt' in short
    assert 'font-size:46pt' in long
    assert "747012345678" in long


def test_prepare_pdf_renders_once_and_keeps_a5_in_filename(monkeypatch, tmp_path):
    target = tmp_path / "etykiety_A5.pdf"
    command_calls = []
    monkeypatch.setattr(LABELS.ZL, "list_produkty", lambda: [
        {"kod": "270x100x170", "nazwa": "Szafka loto"},
    ])
    monkeypatch.setattr(LABELS, "_find_browser", lambda: tmp_path / "chrome.exe")
    monkeypatch.setattr(LABELS, "_labels_output_path", lambda _rows: target)
    monkeypatch.setattr(
        LABELS, "_work_order_qr_data_uri",
        lambda order: f"data:image/png;base64,QR{order['id']}",
    )
    monkeypatch.setattr(
        LABELS, "_work_order_qr_payload",
        lambda order: f"WM:PLANISTA:ORDER:{order['id']}",
    )

    def fake_chromium(command, **_kwargs):
        command_calls.append(command)
        assert "--headless=new" in command
        assert "--no-pdf-header-footer" in command
        assert any(str(part).startswith("--print-to-pdf=") for part in command)
        target.write_bytes(b"%PDF-1.7\n" + b"x" * 200)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(LABELS.subprocess, "run", fake_chromium)
    assert LABELS.prepare_labels_a5_pdf([_order("0026"), _order("0027")]) == target
    assert len(command_calls) == 1
    assert target.read_bytes().startswith(b"%PDF-")


def test_one_print_command_for_multiple_labels_without_marking_a4_as_printed(
    monkeypatch, tmp_path,
):
    registry = tmp_path / "historia.json"
    monkeypatch.setattr(HISTORY, "print_history_path", lambda: registry)
    orders = [_order("0026"), _order("0027"), _order("0028")]
    HISTORY.ensure_print_registry(orders)
    pdf = tmp_path / "zlecenia_A5.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"x" * 200)
    built = []
    printed = []
    monkeypatch.setattr(
        LABELS, "prepare_labels_a5_pdf",
        lambda rows: built.append([r["id"] for r in rows]) or pdf,
    )
    monkeypatch.setattr(
        LABELS, "_print_one_pdf", lambda path: printed.append(path) or "drukarka",
    )

    assert LABELS.dispatch_labels_a5_print(orders) == pdf
    assert built == [["0026", "0027", "0028"]]
    assert printed == [pdf]
    for order in orders:
        assert HISTORY.print_events(order["id"]) == []
        assert HISTORY.print_status(order) == HISTORY.PRINT_UNKNOWN


def test_label_pdf_failure_does_not_send_a_print_command(monkeypatch):
    attempts = []
    def fail(_rows):
        raise LABELS.LabelPrintError("Nie udało się utworzyć PDF")

    monkeypatch.setattr(LABELS, "prepare_labels_a5_pdf", fail)
    monkeypatch.setattr(LABELS, "_print_one_pdf", lambda path: attempts.append(path))
    with pytest.raises(LABELS.LabelPrintError, match="PDF"):
        LABELS.dispatch_labels_a5_print([_order("0026")])
    assert not attempts


def test_planista_has_separate_a5_actions_and_preserves_a4_pdf_controls():
    content = (Path(__file__).resolve().parents[1] / "gui_planista_panel.py").read_text(
        encoding="utf-8"
    )
    assert "Podgląd etykiet A5" in content
    assert "Drukuj etykiety A5" in content
    assert "Drukuj zaznaczone" in content
    assert "Drukuj niewydrukowane" in content
    assert "preview=True, labels=True" in content
    assert "dispatch_labels_a5_print(" in content
    assert "prepare_labels_a5_pdf(" in content
