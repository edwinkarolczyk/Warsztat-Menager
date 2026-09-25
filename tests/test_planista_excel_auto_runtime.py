# WM-VERSION: 0.1

from pathlib import Path

import planista_excel_auto_runtime as AUTO
import planista_excel_runtime as RUNTIME
import planista_auto_print_runtime as AUTO_PRINT


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

    AUTO.save_auto_state(
        enabled=True,
        source_path=r"C:\Plan\plan.xlsx",
        interval_minutes=5,
        auto_accept=True,
        auto_print=True,
        pending_print_order_ids=["000101"],
    )
    # Częściowy zapis nie może wyzerować pozostałych ustawień automatu.
    AUTO.save_auto_state(enabled=False, source_path=r"C:\Plan\plan.xlsx")
    state = AUTO.load_auto_state()

    assert state == {
        "enabled": False,
        "source_path": r"C:\Plan\plan.xlsx",
        "interval_minutes": 5,
        "auto_accept": True,
        "auto_print": True,
        "pending_print_order_ids": ["000101"],
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
    assert "Sprawdzaj co:" in source
    assert "Automatycznie akceptuj bezpieczne pozycje" in source
    assert "Drukuj nowe zlecenia" in source


def test_manual_and_auto_analysis_use_same_detached_copy_path():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")

    assert "parse_from_detached_copy(original, _parse)" in source
    assert 'payload["source_path"] = str(original)' in source



def test_auto_interval_is_clamped_to_one_through_sixty_minutes():
    assert AUTO.normalize_interval_minutes(0) == 1
    assert AUTO.normalize_interval_minutes(1) == 1
    assert AUTO.normalize_interval_minutes(15) == 15
    assert AUTO.normalize_interval_minutes(999) == 60
    assert AUTO.interval_ms(2) == 120_000


def test_auto_accept_runs_only_create_and_update(monkeypatch):
    monkeypatch.setattr(
        RUNTIME,
        "build_order_sync_plan",
        lambda _payload: {
            "items": [
                {"identity": "1|P1", "action": "Utwórz"},
                {"identity": "2|P2", "action": "Aktualizuj"},
                {"identity": "3|P3", "action": "Chronione"},
                {"identity": "4|P4", "action": "Wymaga decyzji"},
            ]
        },
    )
    calls = []

    def apply(_payload, plan, *, approved_identities, autor):
        item = plan["items"][0]
        calls.append((item["identity"], item["action"], set(approved_identities), autor))
        return {
            "written": 1,
            "results": [{
                "identity": item["identity"],
                "action": item["action"],
                "status": "ok",
                "order_id": "000001",
            }],
        }

    monkeypatch.setattr(RUNTIME, "apply_order_sync", apply)

    class Owner:
        login = "Edwin"

    result = RUNTIME._auto_apply_safe(Owner(), {"rows": [{}]})

    assert [call[1] for call in calls] == ["Utwórz", "Aktualizuj"]
    assert all(call[3] == "Edwin" for call in calls)
    assert len(result["results"]) == 2
    assert result["errors"] == []


def test_auto_print_prepares_same_work_order_without_browser_print_script(monkeypatch, tmp_path):
    target = tmp_path / "zlecenie_000101.html"
    monkeypatch.setattr(AUTO_PRINT, "_work_order_output_path", lambda _order: target)
    monkeypatch.setattr(
        AUTO_PRINT,
        "_work_order_html",
        lambda _order: (
            "<html><body>KARTA"
            "<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),250));</script>"
            "</body></html>"
        ),
    )

    path = AUTO_PRINT.prepare_work_order_card({"id": "000101"})

    assert path == target
    content = target.read_text(encoding="utf-8")
    assert "KARTA" in content
    assert "window.print()" not in content


def test_auto_print_dispatches_to_windows_print_verb(monkeypatch, tmp_path):
    target = tmp_path / "zlecenie_000101.html"
    monkeypatch.setattr(AUTO_PRINT, "_work_order_output_path", lambda _order: target)
    monkeypatch.setattr(AUTO_PRINT, "_work_order_html", lambda _order: "<html>KARTA</html>")
    monkeypatch.setattr(AUTO_PRINT.os, "name", "nt")
    calls = []
    monkeypatch.setattr(
        AUTO_PRINT.os,
        "startfile",
        lambda path, verb=None: calls.append((path, verb)),
        raising=False,
    )

    AUTO_PRINT.dispatch_work_order_print({"id": "000101"})

    assert calls == [(str(target), "print")]
