from __future__ import annotations

import machine_ui_repair_runtime as repair


def test_collect_machine_qr_rows_uses_existing_ids_and_deduplicates():
    rows = [
        {"id": "42", "nazwa": "BLELL"},
        {"nr_ewid": "27", "name": "CJ6250YC"},
        {"numer": "71", "nazwa": "TOP-115"},
        {"id": "42", "nazwa": "Duplikat"},
        {"nazwa": "Bez numeru"},
    ]

    assert repair.collect_machine_qr_rows(rows) == [
        {"id": "42", "name": "BLELL"},
        {"id": "27", "name": "CJ6250YC"},
        {"id": "71", "name": "TOP-115"},
    ]


def test_create_all_machine_qr_pdf_saves_one_multipage_pdf(monkeypatch, tmp_path):
    saved = {}
    pages = []

    class FakePage:
        def __init__(self, machine_id):
            self.machine_id = machine_id

        def save(self, path, format_name, **kwargs):
            saved["path"] = path
            saved["format"] = format_name
            saved["kwargs"] = kwargs

    def fake_page(payload, machine_id, *, label="", page_format="A6"):
        assert payload == f"WMM:MACHINE:{machine_id}"
        assert page_format == "A6"
        page = FakePage(machine_id)
        pages.append(page)
        return page

    monkeypatch.setattr(repair, "build_machine_qr_print_page", fake_page)

    target = tmp_path / "QR_wszystkie_maszyny_A6.pdf"
    path, count = repair.create_all_machine_qr_pdf(
        target,
        [
            {"id": "42", "nazwa": "BLELL"},
            {"id": "27", "nazwa": "CJ6250YC"},
        ],
    )

    assert path == target
    assert count == 2
    assert saved["path"] == target
    assert saved["format"] == "PDF"
    assert saved["kwargs"]["save_all"] is True
    assert saved["kwargs"]["append_images"] == [pages[1]]
