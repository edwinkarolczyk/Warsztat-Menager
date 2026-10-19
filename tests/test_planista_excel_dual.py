# WM-VERSION: 0.1
# Plik: tests/test_planista_excel_dual.py
"""Regresje A–E dla dwóch niezależnych źródeł Planisty."""
from __future__ import annotations

from pathlib import Path

from planista_excel_match import STATUS_AMBIGUOUS, STATUS_FOUND
import planista_excel_dual_runtime as dual


def _row(qty=100, *, order="740", code="1.327.50", date="2026-10-22",
         source_row=4, process="zgrzane"):
    return {
        "nr_zlec": order,
        "wm_symbol": code,
        "wm_nazwa": "NW",
        "produkt": code + " NW - RAL 5003",
        "match_status": STATUS_FOUND,
        "ilosc": float(qty),
        "data_wysylki": date,
        "source_row": source_row,
        "proces": process,
    }


def _state(rows_a, rows_b, resolutions=None):
    return {
        "sources": {
            "A": {"rows": rows_a, "status": "OK"},
            "B": {"rows": rows_b, "status": "OK"},
        },
        "resolutions": resolutions or {},
    }


def test_same_order_in_two_sources_does_not_double_quantity():
    merged = dual._merge(_state([_row(100)], [_row(100)]), fully_available=True)
    assert len(merged["rows"]) == 1
    assert merged["rows"][0]["ilosc"] == 100
    assert merged["rows"][0]["source_tag"] == "A+B"
    assert merged["conflicts"] == []


def test_two_sources_can_add_different_orders_independently():
    merged = dual._merge(
        _state([_row(100, order="740")], [_row(50, order="741")]),
        fully_available=True,
    )
    assert len(merged["rows"]) == 2
    assert {r["nr_zlec"] for r in merged["rows"]} == {"740", "741"}
    assert all(r["match_status"] == STATUS_FOUND for r in merged["rows"])


def test_different_quantities_are_conflict_not_automatic_choice():
    merged = dual._merge(_state([_row(100)], [_row(200)]), fully_available=True)
    assert len(merged["rows"]) == 1
    assert merged["rows"][0]["match_status"] == STATUS_AMBIGUOUS
    assert merged["rows"][0]["wm_symbol"] == ""
    assert len(merged["conflicts"]) == 1


def test_decision_b_is_persistent_for_same_pair_of_values():
    state = _state([_row(100)], [_row(200)])
    first = dual._merge(state, fully_available=True)
    problem = first["conflicts"][0]
    state["resolutions"] = {
        problem["key"]: {"signature": problem["signature"], "decision": "B"}
    }
    merged = dual._merge(state, fully_available=True)
    assert merged["conflicts"] == []
    assert merged["rows"][0]["ilosc"] == 200
    assert merged["rows"][0]["match_status"] == STATUS_FOUND

    state["sources"]["A"]["rows"][0]["ilosc"] = 300
    changed = dual._merge(state, fully_available=True)
    assert len(changed["conflicts"]) == 1


def test_missing_source_blocks_automatic_sync_without_losing_rows():
    merged = dual._merge(_state([_row(100)], [_row(100)]), fully_available=False)
    assert len(merged["rows"]) == 1
    assert merged["rows"][0]["match_status"] == STATUS_AMBIGUOUS
    assert merged["rows"][0]["wm_symbol"] == ""


def test_duplicate_batches_with_same_code_require_decision():
    state = _state([_row(100, source_row=4), _row(50, source_row=5)], [])
    merged = dual._merge(state, fully_available=True)
    assert len(merged["rows"]) == 2
    assert all(item["match_status"] == STATUS_FOUND for item in merged["rows"])
    assert all(item["dual_conflict_type"] == "duplicate" for item in merged["rows"])
    assert {item["ilosc"] for item in merged["rows"]} == {50, 100}
    assert len(merged["conflicts"]) == 1


def test_source_state_and_resolution_survive_restart(tmp_path, monkeypatch):
    storage = tmp_path / "planista" / "excel_dual_state.json"
    monkeypatch.setattr(dual, "_path", lambda: storage)
    state = dual._empty()
    state["sources"]["A"] = {"path": str(tmp_path / "A.xlsx"), "rows": [_row()]}
    state["resolutions"]["740|wm:1.327.50"] = {
        "signature": "abc", "decision": "B", "user": "brygadzista"
    }
    dual._save(state)
    restored = dual.load_dual_state()
    assert restored["sources"]["A"]["rows"][0]["ilosc"] == 100
    assert restored["resolutions"]["740|wm:1.327.50"]["decision"] == "B"


def test_legacy_automatic_workflow_is_still_present():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    assert "_auto_apply_safe(owner, payload)" in source
    assert "_queue_created_prints(owner, results)" in source
    assert "inspect_dual_plans(source, second)" in source
    assert "def start_global_excel_watcher(root)" in source
    assert 'text="Plan Excel — źródła i zmiany…"' in source
    assert "_open_excel_control(self)" in source


def test_global_watcher_starts_from_main_panel():
    source = Path("gui_panel.py").read_text(encoding="utf-8")
    assert "start_global_excel_watcher(root)" in source
    assert "start_global_excel_watcher(root)" in source.split("_build_sidebar(initial=True)", 1)[1]


def test_two_source_printing_uses_existing_registry_after_order_creation():
    source = Path("planista_excel_sync_runtime.py").read_text(encoding="utf-8")
    assert 'if payload.get("dual_mode") and created and print_enabled:' in source
    assert "_queue_created_prints(owner, succeeded)" in source
    auto = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    assert 'elif payload.get("dual_mode"):' in auto


def test_two_independent_snapshots_and_unavailable_copy(monkeypatch, tmp_path):
    import sys
    import types

    monkeypatch.setattr(dual, "_path", lambda: tmp_path / "planista" / "excel_dual_state.json")
    fake_module = types.ModuleType("gui_magazyn_bom")
    class FakeWarehouse:
        def __init__(self):
            self.produkty = {"1.327.50": _row()}
    fake_module.WarehouseModel = FakeWarehouse
    monkeypatch.setitem(sys.modules, "gui_magazyn_bom", fake_module)
    monkeypatch.setattr(dual, "load_manual_mappings", lambda: {})
    rows_by_file = {
        "A.xlsx": [_row(100)],
        "B.xlsx": [_row(100)],
    }
    def fake_reader(source, products, mappings):
        filename = Path(source).name
        if filename not in rows_by_file:
            raise FileNotFoundError(filename)
        return {
            "rows": [dict(item) for item in rows_by_file[filename]],
            "import_diagnostics": {
                "source_rows": len(rows_by_file[filename]),
                "imported_rows": len(rows_by_file[filename]),
                "skipped_rows": [], "row_warnings": [],
            },
        }
    monkeypatch.setattr(dual, "_read_one", fake_reader)
    a, b = str(tmp_path / "A.xlsx"), str(tmp_path / "B.xlsx")
    first = dual.inspect_dual_plans(a, b)
    assert first["dual_source_errors"] == []
    assert len(first["rows"]) == 1
    assert first["match_summary"][STATUS_FOUND] == 1
    assert dual.load_dual_state()["sources"]["A"]["path"] == a
    assert dual.load_dual_state()["sources"]["B"]["path"] == b

    rows_by_file["A.xlsx"] = [_row(150)]
    second = dual.inspect_dual_plans(a, b)
    assert len(second["dual_conflicts"]) == 1
    assert second["match_summary"][STATUS_FOUND] == 0

    del rows_by_file["B.xlsx"]
    third = dual.inspect_dual_plans(a, b)
    assert third["dual_source_errors"]
    assert len(third["rows"]) == 1
    assert all(row["match_status"] == STATUS_AMBIGUOUS for row in third["rows"])
    assert dual.load_dual_state()["sources"]["B"]["rows"][0]["ilosc"] == 100
