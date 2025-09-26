from __future__ import annotations

from pathlib import Path

from backend.audit import wm_audit_runtime
from config import paths as config_paths


def _fake_getter_factory(root: Path):
    mapping = {"paths.data_root": str(root)}

    def _fake_getter(key: str):
        return mapping.get(key)

    return _fake_getter


def test_run_audit_returns_report_text(tmp_path, monkeypatch):
    root = tmp_path / "data"
    getter = _fake_getter_factory(root)
    monkeypatch.setattr(config_paths, "_SETTINGS_STATE", None)
    monkeypatch.setattr(config_paths, "_SETTINGS_GETTER", getter)

    report = wm_audit_runtime.run_audit()

    logs_dir = root / "logs"
    report_files = list(logs_dir.glob("audyt_wm-*.txt"))

    assert report
    assert "Audyt WM" in report
    assert report_files
    assert report == report_files[0].read_text(encoding="utf-8")
