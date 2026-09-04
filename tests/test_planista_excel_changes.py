# WM-VERSION: 0.1
# Plik: tests/test_planista_excel_changes.py
# version: 1.1

from __future__ import annotations

from pathlib import Path

from planista_excel_changes import (
    CHANGE_BASELINE,
    CHANGE_CHANGED,
    CHANGE_NEW_ORDER,
    CHANGE_NEW_ROW,
    CHANGE_NONE,
    CHANGE_REMOVED,
    analyze_and_store_plan_changes,
    compare_plan_rows,
    last_plan_source_path,
)


def _row(order, code, qty, date="2026-09-14", *, source_row=4, name="NW"):
    return {
        "source_row": source_row,
        "nr_zlec": str(order),
        "excel_oznaczenie": code,
        "produkt": f"{code} {name} - RAL 5003",
        "ilosc": float(qty),
        "data_wysylki": date,
        "proces": "zgrzane",
        "match_status": "Znaleziony w WM",
        "wm_symbol": code,
        "wm_nazwa": name,
    }


def _payload(source: Path, rows):
    return {
        "source_path": str(source.resolve()),
        "source_name": source.name,
        "sheet": "PLAN 2026",
        "rows": [dict(row) for row in rows],
        "match_summary": {"Znaleziony w WM": len(rows)},
        "product_catalog_size": len(rows),
    }


def test_first_analysis_creates_snapshot_under_active_root_and_second_is_unchanged(tmp_path):
    root = tmp_path / "wm-root"
    source = tmp_path / "Plan.xlsx"
    source.write_bytes(b"plan-v1")
    rows = [_row(659, "1.327.50", 640)]

    first = analyze_and_store_plan_changes(_payload(source, rows), root=root)

    snapshot = root / "data" / "planista" / "excel_plan_snapshot.json"
    assert snapshot.is_file()
    assert first["baseline_created"] is True
    assert first["rows"][0]["excel_change_status"] == CHANGE_BASELINE
    assert first["has_changes"] is False
    assert last_plan_source_path(root=root) == str(source.resolve())

    second = analyze_and_store_plan_changes(_payload(source, rows), root=root)
    assert second["baseline_created"] is False
    assert second["rows"][0]["excel_change_status"] == CHANGE_NONE
    assert second["removed_rows"] == []
    assert second["has_changes"] is False
    assert second["previous_source_sha256"] == first["source_sha256"]


def test_quantity_and_shipping_date_changes_are_reported_without_changing_identity(tmp_path):
    root = tmp_path / "wm-root"
    source = tmp_path / "Plan.xlsx"
    source.write_bytes(b"plan-v1")
    analyze_and_store_plan_changes(
        _payload(source, [_row(659, "1.327.50", 640, "2026-09-14")]),
        root=root,
    )

    source.write_bytes(b"plan-v2")
    changed = analyze_and_store_plan_changes(
        _payload(source, [_row(659, "1.327.50", 700, "2026-09-18")]),
        root=root,
    )

    row = changed["rows"][0]
    assert row["excel_change_status"] == CHANGE_CHANGED
    assert row["excel_change_fields"] == ["Ilość", "Data wysyłki"]
    assert "640" in row["excel_change_note"]
    assert "700" in row["excel_change_note"]
    assert changed["source_sha256"] != changed["previous_source_sha256"]
    assert changed["has_changes"] is True


def test_process_change_is_reported_as_excel_change():
    previous = [_row(659, "1.327.50", 640)]
    current = [_row(659, "1.327.50", 640)]
    current[0]["proces"] = "malowane"

    result = compare_plan_rows(previous, current)

    row = result["rows"][0]
    assert row["excel_change_status"] == CHANGE_CHANGED
    assert row["excel_change_fields"] == ["Proces"]
    assert row["excel_change_note"] == "Proces: zgrzane → malowane"
    assert result["has_changes"] is True


def test_single_product_replacement_in_same_external_order_is_product_change():
    previous = [_row(659, "1.327.50", 640)]
    current = [_row(659, "1.620.165", 640)]

    result = compare_plan_rows(previous, current)

    assert result["removed_rows"] == []
    assert result["rows"][0]["excel_change_status"] == CHANGE_CHANGED
    assert "Produkt" in result["rows"][0]["excel_change_fields"]


def test_new_row_new_order_and_removed_row_are_separate_changes():
    previous = [
        _row(659, "1.327.50", 640, source_row=4),
        _row(659, "1.620.165", 84, source_row=5),
        _row(593, "1.435.135", 420, source_row=6),
    ]
    current = [
        _row(659, "1.327.50", 640, source_row=40),
        _row(659, "1.620.165", 84, source_row=41),
        _row(659, "5.300.600", 10, source_row=42),
        _row(700, "HP14", 25, source_row=43),
    ]

    result = compare_plan_rows(previous, current)
    statuses = {row["excel_oznaczenie"]: row["excel_change_status"] for row in result["rows"]}

    assert statuses["1.327.50"] == CHANGE_NONE
    assert statuses["1.620.165"] == CHANGE_NONE
    assert statuses["5.300.600"] == CHANGE_NEW_ROW
    assert statuses["HP14"] == CHANGE_NEW_ORDER
    assert len(result["removed_rows"]) == 1
    assert result["removed_rows"][0]["excel_oznaczenie"] == "1.435.135"
    assert result["removed_rows"][0]["excel_change_status"] == CHANGE_REMOVED
    assert result["has_changes"] is True


def test_row_reordering_alone_does_not_create_false_changes():
    previous = [
        _row(659, "1.327.50", 640, source_row=4),
        _row(659, "1.620.165", 84, source_row=5),
    ]
    current = [
        _row(659, "1.620.165", 84, source_row=40),
        _row(659, "1.327.50", 640, source_row=41),
    ]

    result = compare_plan_rows(previous, current)

    assert all(row["excel_change_status"] == CHANGE_NONE for row in result["rows"])
    assert result["removed_rows"] == []
    assert result["has_changes"] is False


def test_runtime_exposes_manual_check_button_and_keeps_analysis_read_only():
    source = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    assert 'text="Sprawdź zmiany"' in source
    assert "analyze_and_store_plan_changes" in source
    assert "bez tworzenia zleceń" in source
