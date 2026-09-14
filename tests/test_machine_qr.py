import json

from machine_qr_runtime import (
    _pip_qrcode_command,
    build_machine_qr_image,
    build_machine_qr_print_page,
    create_machine_qr_pdf,
    machine_qr_payload,
    machine_qr_print_size,
)
from services import wmm_api


def test_machine_qr_payload_uses_existing_machine_id():
    assert machine_qr_payload("42") == "WMM:MACHINE:42"
    assert machine_qr_payload("  M-071  ") == "WMM:MACHINE:M-071"


def test_machine_qr_image_can_be_generated():
    image = build_machine_qr_image("WMM:MACHINE:66")
    assert image.width > 0
    assert image.height > 0


def test_machine_qr_installer_uses_current_python():
    assert _pip_qrcode_command("C:/Python/python.exe") == [
        "C:/Python/python.exe",
        "-m",
        "pip",
        "install",
        "qrcode",
    ]


def test_machine_qr_print_page_sizes_are_real_a5_and_a6():
    assert machine_qr_print_size("A5") == (1748, 2480)
    assert machine_qr_print_size("a6") == (1240, 1748)

    a5 = build_machine_qr_print_page(
        "WMM:MACHINE:66",
        "66",
        label="Wiertarka stolowa",
        page_format="A5",
    )
    a6 = build_machine_qr_print_page(
        "WMM:MACHINE:66",
        "66",
        label="Wiertarka stolowa",
        page_format="A6",
    )
    assert a5.size == (1748, 2480)
    assert a6.size == (1240, 1748)


def test_machine_qr_pdf_can_be_created_for_print(tmp_path):
    target = tmp_path / "qr_a6.pdf"
    result = create_machine_qr_pdf(
        target,
        "WMM:MACHINE:66",
        "66",
        label="Wiertarka stolowa",
        page_format="A6",
    )

    payload = result.read_bytes()
    assert result == target
    assert payload.startswith(b"%PDF")
    assert len(payload) > 5000


def test_wmm_resolves_prefixed_and_legacy_machine_codes(tmp_path, monkeypatch):
    machines_dir = tmp_path / "data" / "maszyny"
    machines_dir.mkdir(parents=True)
    (machines_dir / "maszyny.json").write_text(
        json.dumps(
            [{"id": "42", "nr_ewid": "42", "nazwa": "Prasa"}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("WM_ROOT", str(tmp_path))
    monkeypatch.delenv("WM_DATA_ROOT", raising=False)

    prefixed = wmm_api._find_machine("WMM:MACHINE:42")
    legacy = wmm_api._find_machine("42")

    assert prefixed is not None
    assert prefixed["id"] == "42"
    assert legacy is not None
    assert legacy["id"] == "42"
