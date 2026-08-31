# version: 1.1
"""Transakcyjne zabezpieczenie korekty terminu cyklicznego serwisu Maszyn.

Jeżeli po zapisie wpisu maszyny nie uda się zsynchronizować istniejącej
automatycznej Dyspozycji, przywracamy poprzedni wpis maszyny i (jeżeli było
to potrzebne) poprzedni termin/meta tej konkretnej Dyspozycji.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import machine_review_correction_runtime as _correction

_INSTALLED = False


def _is_dysp_warning(message: object) -> bool:
    text = str(message or "").casefold()
    return "dyspozycji" in text and (
        "nie uda" in text or "nie został" in text or "nie została" in text
    )


def _find_linked_auto_dysp(
    machine_id: str,
    entry: dict[str, Any] | None,
    original_plan,
) -> dict[str, Any] | None:
    if not isinstance(entry, dict) or _correction._review_source(entry) != "cycle":
        return None
    try:
        from dyspozycje_store import get_dyspozycja, load_dyspozycje
    except Exception:
        return None

    direct_id = str(entry.get("dyspozycja_id") or "").strip()
    if direct_id:
        try:
            item = get_dyspozycja(direct_id)
        except Exception:
            item = None
        meta = (
            item.get("meta")
            if isinstance(item, dict) and isinstance(item.get("meta"), dict)
            else {}
        )
        if str(meta.get("auto_source") or "").strip() == "machine_cycle_review":
            return deepcopy(item)

    identity = _correction._cycle_identity(entry, original_plan)
    if identity is None:
        return None
    year, month = identity
    matches: list[dict[str, Any]] = []
    try:
        rows = load_dyspozycje()
    except Exception:
        return None
    for item in rows:
        if not isinstance(item, dict):
            continue
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        if str(meta.get("auto_source") or "").strip() != "machine_cycle_review":
            continue
        if not _correction._same_machine_id(
            meta.get("machine_id") or item.get("obiekt_id"), machine_id
        ):
            continue
        try:
            same_cycle = (
                int(meta.get("cycle_year") or 0) == int(year)
                and int(meta.get("cycle_month") or 0) == int(month)
            )
        except Exception:
            same_cycle = False
        if same_cycle:
            matches.append(deepcopy(item))
    return matches[0] if len(matches) == 1 else None


def _restore_dysp(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return True
    dysp_id = str(snapshot.get("id") or "").strip()
    if not dysp_id:
        return True
    try:
        from dyspozycje_store import update_dyspozycja

        restored = update_dyspozycja(
            dysp_id,
            {
                "termin": str(snapshot.get("termin") or ""),
                "meta": deepcopy(snapshot.get("meta") or {}),
            },
        )
        return restored is not None
    except Exception:
        return False


def install(gui_module: Any) -> bool:
    """Owiń zapis korekty rollbackiem; instalacja jest idempotentna."""
    global _INSTALLED
    if _INSTALLED:
        return True

    original = getattr(_correction, "_apply_correction", None)
    if not callable(original):
        return False
    if getattr(original, "_wm_tx_guard", False):
        _INSTALLED = True
        return True

    def _guarded_apply(*args, **kwargs):
        machine_id = str(kwargs.get("machine_id") or "").strip()
        context = (
            kwargs.get("context")
            if isinstance(kwargs.get("context"), dict)
            else {}
        )
        expected_id = str(kwargs.get("expected_review_id") or "").strip()

        backup_rows = None
        primary_path = ""
        backup_idx = None
        dysp_snapshot = None
        try:
            rows, primary_path, idx, machine = _correction._load_machine(
                gui_module, machine_id
            )
            if idx is not None and isinstance(machine, dict):
                backup_rows = deepcopy(rows)
                backup_idx = int(idx)
                target = None
                reviews = machine.get("reviews")
                if expected_id and isinstance(reviews, list):
                    for item in reviews:
                        if (
                            isinstance(item, dict)
                            and str(item.get("id") or "").strip() == expected_id
                        ):
                            target = item
                            break
                state = "missing"
                if target is None:
                    target, state = _correction._find_persisted_review(
                        gui_module, machine, context
                    )
                if target is None and state != "ambiguous":
                    target = _correction._default_cycle_entry(
                        gui_module, machine, context
                    )
                if target is not None:
                    before = _correction._safe_snapshot(target)
                    original_plan = _correction._parse_plan(
                        gui_module, before.get("planned_date")
                    )
                    dysp_snapshot = _find_linked_auto_dysp(
                        machine_id, target, original_plan
                    )
        except Exception:
            backup_rows = None
            dysp_snapshot = None

        result = original(*args, **kwargs)
        if not isinstance(result, tuple) or len(result) < 2:
            return result
        ok = bool(result[0])
        message = result[1]
        if not ok or not _is_dysp_warning(message):
            return result

        machine_restored = False
        if (
            isinstance(backup_rows, list)
            and backup_idx is not None
            and 0 <= backup_idx < len(backup_rows)
        ):
            try:
                machine_restored = _correction._save_machine(
                    gui_module,
                    backup_rows,
                    primary_path,
                    backup_idx,
                    backup_rows[backup_idx],
                )
            except Exception:
                machine_restored = False
        dysp_restored = _restore_dysp(dysp_snapshot)

        if machine_restored and dysp_restored:
            return (
                False,
                f"{message} Korekta została automatycznie cofnięta, więc dane pozostały spójne.",
                None,
            )
        return (
            True,
            f"{message} UWAGA: automatyczny rollback nie został potwierdzony w całości.",
            result[2] if len(result) > 2 else None,
        )

    _guarded_apply._wm_tx_guard = True
    _correction._apply_correction = _guarded_apply
    _INSTALLED = True
    return True


__all__ = ["install"]
