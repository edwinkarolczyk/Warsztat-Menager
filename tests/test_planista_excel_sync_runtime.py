# WM-VERSION: 0.1
# Plik: tests/test_planista_excel_sync_runtime.py
# version: 1.0

from __future__ import annotations

from pathlib import Path

import planista_excel_sync_runtime as runtime
from planista_excel_orders import (
    ACTION_CONFLICT,
    ACTION_CREATE,
    ACTION_NONE,
    ACTION_PROTECTED,
    ACTION_REMOVED,
    ACTION_SKIP,
    ACTION_UPDATE,
)


def _item(identity, action, source_row=1):
    return {
        "identity": identity,
        "action": action,
        "source_row": source_row,
        "row": {},
    }


def test_only_create_and_update_are_user_selectable():
    plan = {
        "items": [
            _item("create", ACTION_CREATE),
            _item("update", ACTION_UPDATE),
            _item("same", ACTION_NONE),
            _item("protected", ACTION_PROTECTED),
            _item("conflict", ACTION_CONFLICT),
            _item("skip", ACTION_SKIP),
            _item("removed", ACTION_REMOVED),
        ]
    }

    assert runtime._writable_identities(plan) == {"create", "update"}


def test_confirmation_counts_only_safe_selected_actions():
    plan = {
        "items": [
            _item("create", ACTION_CREATE),
            _item("update", ACTION_UPDATE),
            _item("conflict", ACTION_CONFLICT),
        ]
    }

    counts = runtime._selected_action_counts(plan, {"create", "update", "conflict"})

    assert counts[ACTION_CREATE] == 1
    assert counts[ACTION_UPDATE] == 1
    assert counts.get(ACTION_CONFLICT, 0) == 0


def test_sync_preview_promotes_writable_rows_and_puts_removed_last():
    items = [
        _item("removed", ACTION_REMOVED, 2),
        _item("conflict", ACTION_CONFLICT, 3),
        _item("same", ACTION_NONE, 4),
        _item("update", ACTION_UPDATE, 5),
        _item("create", ACTION_CREATE, 6),
        _item("skip", ACTION_SKIP, 7),
    ]

    ordered = sorted(items, key=runtime._sync_item_sort_key)

    assert [item["identity"] for item in ordered] == [
        "update",
        "create",
        "same",
        "conflict",
        "skip",
        "removed",
    ]


def test_runtime_requires_explicit_selection_and_second_confirmation():
    root_runtime = Path("planista_excel_runtime.py").read_text(encoding="utf-8")
    sync_runtime = Path("planista_excel_sync_runtime.py").read_text(encoding="utf-8")

    assert 'text="Synchronizuj z WM…"' in root_runtime
    assert "show_excel_sync_preview(owner, payload)" in root_runtime
    assert 'text="Wykonaj zaznaczone"' in sync_runtime
    assert "messagebox.askyesno" in sync_runtime
    assert "fresh_plan = build_order_sync_plan(payload)" in sync_runtime
    assert "stale = selected - fresh_writable" in sync_runtime
    assert "apply_order_sync(" in sync_runtime
    assert "owner.refresh()" in sync_runtime


def test_context_help_for_sync_controls_stays_short():
    assert runtime._SELECT_HELP.count(".") <= 2
    assert runtime._APPLY_HELP.count(".") <= 2
