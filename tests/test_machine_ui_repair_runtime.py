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
    saved = []
    active_pages = {"count": 0, "maximum": 0}

    class FakePage:
        def __init__(self, machine_id):
            self.machine_id = machine_id
            active_pages["count"] += 1
            active_pages["maximum"] = max(
                active_pages["maximum"], active_pages["count"]
            )

        def save(self, path, format_name, **kwargs):
            saved.append((self.machine_id, path, format_name, kwargs))
            mode = "ab" if kwargs.get("append") else "wb"
            with open(path, mode) as handle:
                handle.write(self.machine_id.encode("utf-8"))

        def close(self):
            active_pages["count"] -= 1

    def fake_page(payload, machine_id, *, label="", page_format="A6"):
        assert payload == f"WMM:MACHINE:{machine_id}"
        assert page_format == "A6"
        return FakePage(machine_id)

    monkeypatch.setattr(repair, "build_machine_qr_print_page", fake_page)

    target = tmp_path / "QR_wszystkie_maszyny_A6.pdf"
    machines = [
        {"id": str(machine_id), "nazwa": f"Maszyna {machine_id}"}
        for machine_id in range(1, 101)
    ]
    path, count = repair.create_all_machine_qr_pdf(
        target,
        machines,
    )

    assert path == target
    assert count == 100
    assert [row[0] for row in saved] == [str(value) for value in range(1, 101)]
    assert all(row[1] == target.with_name(target.name + ".tmp") for row in saved)
    assert all(row[2] == "PDF" for row in saved)
    assert saved[0][3]["append"] is False
    assert all(row[3]["append"] is True for row in saved[1:])
    assert active_pages == {"count": 0, "maximum": 1}
    assert target.read_text(encoding="utf-8") == "".join(
        str(value) for value in range(1, 101)
    )
    assert not target.with_name(target.name + ".tmp").exists()


def test_create_all_machine_qr_pdf_keeps_old_file_after_error(monkeypatch, tmp_path):
    target = tmp_path / "QR_wszystkie_maszyny_A6.pdf"
    target.write_bytes(b"old-pdf")

    class FailingPage:
        def __init__(self, machine_id):
            self.machine_id = machine_id

        def save(self, path, _format_name, **kwargs):
            if kwargs.get("append"):
                raise OSError("brak miejsca")
            with open(path, "wb") as handle:
                handle.write(b"partial-pdf")

        def close(self):
            pass

    monkeypatch.setattr(
        repair,
        "build_machine_qr_print_page",
        lambda _payload, machine_id, **_kwargs: FailingPage(machine_id),
    )

    try:
        repair.create_all_machine_qr_pdf(
            target,
            [{"id": "42"}, {"id": "27"}],
        )
    except OSError as exc:
        assert str(exc) == "brak miejsca"
    else:
        raise AssertionError("Oczekiwano błędu zapisu drugiej strony")

    assert target.read_bytes() == b"old-pdf"
    assert not target.with_name(target.name + ".tmp").exists()
