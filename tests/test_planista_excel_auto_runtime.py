# WM-VERSION: 0.1

from pathlib import Path

import planista_excel_auto_runtime as AUTO
import planista_excel_runtime as RUNTIME


def test_excel_is_parsed_from_detached_copy(tmp_path):
    source = tmp_path / "plan.xlsx"
    source.write_bytes(b"excel-test-bytes")
    seen = {}

    def parser(copy_path):
        copy_path = Path(copy_path)
        seen["copy"] = copy_path
        assert copy_path != source
        assert copy_path.is_file()
        assert copy_path.read_bytes() == source.read_bytes()
        return {"ok": True}

    result = AUTO.parse_from_detached_copy(source, parser)

    assert result == {"ok": True}
    assert source.is_file()
    assert source.read_bytes() == b"excel-test-bytes"
    assert not seen["copy"].exists()


def test_auto_state_is_persisted_under_planista_dir(monkeypatch, tmp_path):
    planista_dir = tmp_path / "data" / "planista"
    monkeypatch.setattr(AUTO, "_planista_dir", lambda: planista_dir)

    AUTO.save_auto_state(enabled=True, source_path=r"C:\Plan\plan.xlsx")
    state = AUTO.load_auto_state()

    assert state == {
        "enabled": True,
        "source_path": r"C:\Plan\plan.xlsx",
    }
    assert (planista_dir / "excel_auto_state.json").is_file()


def test_pending_count_counts_only_create_and_update(monkeypatch):
    monkeypatch.setattr(
        RUNTIME,
        "build_order_sync_plan",
        lambda _payload: {
            "items": [
                {"action": "Utwórz"},
                {"action": "Aktualizuj"},
                {"action": "Bez zmian"},
                {"action": "Chronione"},
            ]
        },
    )

    assert RUNTIME._pending_sync_count({"rows": [{}]}) == 2


def test_planista_auto_ui_disables_manual_controls_and_has_acceptance_button():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")

    assert "Niech WM pracuje automatycznie na pliku:" in source
    assert "Do akceptacji (" in source
    assert "_set_manual_excel_controls(self, enabled=not bool(self._excel_auto_var.get()))" in source
    assert "preselect_safe=True" in source
    assert "DEFAULT_INTERVAL_MS" in source


def test_manual_and_auto_analysis_use_same_detached_copy_path():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")

    assert "parse_from_detached_copy(original, _parse)" in source
    assert 'payload["source_path"] = str(original)' in source
