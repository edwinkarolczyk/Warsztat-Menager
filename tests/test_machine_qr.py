import json

from machine_qr_runtime import (
    _pip_qrcode_command,
    build_machine_qr_image,
    machine_qr_payload,
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
