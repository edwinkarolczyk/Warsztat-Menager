"""Tests for the independent Plan Monitor engine."""

import json
from pathlib import Path

import pandas as pd

from PlanMonitor.main import (PlanMonitor, append_dispositions, compare_plans,
                              export_changes, load_config, read_plan,
                              save_config)


def row(order="306", symbol="1.670.93 REMS", quantity=336,
        deadline="2026-06-11"):
    return {"order": order, "symbol": symbol, "quantity": quantity,
            "deadline": deadline}


def test_compare_detects_all_requested_change_types():
    previous = [row(), row("501", "02.090 FAM", 200, "2026-06-12"),
                row("700", "OLD NT", 2, "2026-06-10")]
    current = [row(quantity=450, deadline="2026-06-13"),
               row("501", "02.091 FAM", 200, "2026-06-12"),
               row("800", "NEW MARPOL", 3, "2026-06-14")]

    changes = compare_plans(previous, current, ["REMS", "NT", "FAM"])

    assert {change["type"] for change in changes} == {
        "new", "removed", "quantity_changed", "deadline_changed",
        "description_changed",
    }
    assert next(change for change in changes
                if change["type"] == "quantity_changed")["new"] == 450
    assert next(change for change in changes
                if change["type"] == "description_changed")["old"] == (
                    "02.090 FAM"
                )


def test_read_plan_normalizes_excel_and_infers_columns(tmp_path):
    plan = tmp_path / "plan.xlsx"
    pd.DataFrame({
        "Nr zlecenia": [306.0],
        "Symbol": [" 1.670.93 REMS "],
        "Ilość": ["450,5"],
        "Termin": [pd.Timestamp("2026-06-13")],
    }).to_excel(plan, index=False)

    assert read_plan(plan) == [row(quantity=450.5, deadline="2026-06-13")]


def test_check_saves_snapshot_history_and_disposition(tmp_path):
    config_path = tmp_path / "config.json"
    snapshot_path = tmp_path / "snapshots" / "current_snapshot.json"
    history_path = tmp_path / "reports" / "history.jsonl"
    disposition_path = tmp_path / "data" / "pending_dispositions.json"
    plan_file = tmp_path / "plan.xlsx"
    plan_file.write_text("placeholder", encoding="utf-8")
    config = load_config(tmp_path / "missing.json")
    config["plan_file"] = str(plan_file)
    save_config(config, config_path)
    monitor = PlanMonitor(config_path, snapshot_path, history_path,
                          disposition_path, reader=lambda *_: [row()])

    result = monitor.check(force=True)

    assert result.status == "changed"
    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["rows"] == [
        row()
    ]
    assert json.loads(history_path.read_text(encoding="utf-8"))["type"] == "new"
    assert json.loads(disposition_path.read_text(encoding="utf-8")) == [{
        "typ": "zlecenie_wykonania",
        "nr_zlecenia": "306",
        "symbol": "1.670.93 REMS",
        "ilosc": 336,
        "termin": "2026-06-11",
    }]


def test_export_csv_and_txt(tmp_path):
    changes = compare_plans([], [row()], ["REMS"], "2026-06-01T07:30:00")

    export_changes(changes, tmp_path / "report.csv")
    export_changes(changes, tmp_path / "report.txt")

    assert "DOTYCZY DZIAŁU" in (tmp_path / "report.csv").read_text(
        encoding="utf-8-sig"
    )
    assert "NOWE" in (tmp_path / "report.txt").read_text(encoding="utf-8")
