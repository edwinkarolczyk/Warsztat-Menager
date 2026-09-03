# WM-VERSION: 0.1
# Plik: planista_excel_changes.py
# version: 1.0
"""Snapshot i wykrywanie zmian zewnętrznego planu produkcji Excel.

Moduł nie zapisuje zleceń WM i nie modyfikuje pliku XLSX. Jedynym zapisem
jest techniczny snapshot ostatniej analizy pod aktywnym WM_ROOT.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

from planista_excel_match import STATUS_CHANGED, extract_product_designation, normalize_designation


SNAPSHOT_RELATIVE = ("data", "planista", "excel_plan_snapshot.json")
SNAPSHOT_SCHEMA = 1

CHANGE_BASELINE = "Punkt odniesienia"
CHANGE_NONE = "Bez zmian"
CHANGE_NEW_ORDER = "Nowe zlecenie"
CHANGE_NEW_ROW = "Nowa pozycja"
CHANGE_CHANGED = STATUS_CHANGED
CHANGE_REMOVED = "Usunięta pozycja"


class PlanChangeError(ValueError):
    """Czytelny dla użytkownika błąd snapshotu/analizy zmian."""


def _text(value) -> str:
    return str(value or "").strip()


def _normalized_text(value) -> str:
    text = unicodedata.normalize("NFKD", _text(value).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    return " ".join(re.sub(r"\s+", " ", text).split())


def _quantity(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(_text(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _designation(row: dict) -> str:
    return _text(row.get("excel_oznaczenie") or extract_product_designation(row.get("produkt")))


def _snapshot_row(row: dict) -> dict:
    """Zachowaj dane potrzebne do kolejnej analizy; numer wiersza jest tylko diagnostyczny."""
    return {
        "source_row": row.get("source_row", ""),
        "nr_zlec": _text(row.get("nr_zlec")),
        "excel_oznaczenie": _designation(row),
        "produkt": _text(row.get("produkt")),
        "ilosc": _quantity(row.get("ilosc")),
        "data_wysylki": _text(row.get("data_wysylki")),
        "proces": _text(row.get("proces")),
        "wm_symbol": _text(row.get("wm_symbol")),
        "wm_nazwa": _text(row.get("wm_nazwa")),
        "match_status": _text(row.get("match_status")),
    }


def _identity_key(row: dict) -> tuple[str, str]:
    return (
        _text(row.get("nr_zlec")).casefold(),
        normalize_designation(_designation(row)),
    )


def _exact_signature(row: dict) -> tuple:
    return (
        _normalized_text(row.get("produkt")),
        _quantity(row.get("ilosc")),
        _text(row.get("data_wysylki")),
    )


def _row_sort_key(row: dict) -> tuple:
    try:
        source_row = int(row.get("source_row") or 0)
    except (TypeError, ValueError):
        source_row = 0
    return (source_row, _normalized_text(row.get("produkt")), _quantity(row.get("ilosc")) or 0.0)


def _format_value(value) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _changed_fields(previous: dict, current: dict, *, force_product: bool = False) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    details: list[str] = []

    prev_product = _normalized_text(previous.get("produkt"))
    curr_product = _normalized_text(current.get("produkt"))
    if force_product or prev_product != curr_product:
        fields.append("Produkt")
        details.append(
            f"Produkt: {_format_value(previous.get('produkt'))} → {_format_value(current.get('produkt'))}"
        )

    prev_qty = _quantity(previous.get("ilosc"))
    curr_qty = _quantity(current.get("ilosc"))
    if prev_qty != curr_qty:
        fields.append("Ilość")
        details.append(f"Ilość: {_format_value(prev_qty)} → {_format_value(curr_qty)}")

    prev_date = _text(previous.get("data_wysylki"))
    curr_date = _text(current.get("data_wysylki"))
    if prev_date != curr_date:
        fields.append("Data wysyłki")
        details.append(f"Data wysyłki: {_format_value(prev_date)} → {_format_value(curr_date)}")

    return fields, details


def _mark_current(row: dict, status: str, fields: list[str] | None = None, details: list[str] | None = None) -> None:
    row["excel_change_status"] = status
    row["excel_change_fields"] = list(fields or [])
    row["excel_change_note"] = "; ".join(details or [])


def compare_plan_rows(previous_rows: list[dict] | None, current_rows: list[dict]) -> dict:
    """Porównaj dwa plany bez używania numeru wiersza Excel jako klucza biznesowego."""
    current = [dict(row) for row in current_rows if isinstance(row, dict)]
    previous = [dict(row) for row in (previous_rows or []) if isinstance(row, dict)]

    if previous_rows is None:
        for row in current:
            _mark_current(row, CHANGE_BASELINE)
        return {
            "rows": current,
            "removed_rows": [],
            "change_summary": {CHANGE_BASELINE: len(current)},
            "has_changes": False,
            "baseline_created": True,
        }

    prev_unused = set(range(len(previous)))
    curr_unused = set(range(len(current)))

    prev_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    curr_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, row in enumerate(previous):
        prev_groups[_identity_key(row)].append(idx)
    for idx, row in enumerate(current):
        curr_groups[_identity_key(row)].append(idx)

    # 1) Najpierw łączymy po Nr zlec. + oznaczenie produktu. W obrębie grupy
    # szukamy dokładnie niezmienionych pozycji, potem parujemy pozostałe.
    for key in sorted(set(prev_groups) & set(curr_groups)):
        p_ids = sorted(prev_groups[key], key=lambda i: _row_sort_key(previous[i]))
        c_ids = sorted(curr_groups[key], key=lambda i: _row_sort_key(current[i]))

        remaining_p = list(p_ids)
        remaining_c = list(c_ids)
        for p_idx in list(remaining_p):
            signature = _exact_signature(previous[p_idx])
            match_idx = next(
                (c_idx for c_idx in remaining_c if _exact_signature(current[c_idx]) == signature),
                None,
            )
            if match_idx is None:
                continue
            _mark_current(current[match_idx], CHANGE_NONE)
            prev_unused.discard(p_idx)
            curr_unused.discard(match_idx)
            remaining_p.remove(p_idx)
            remaining_c.remove(match_idx)

        for p_idx, c_idx in zip(remaining_p, remaining_c):
            fields, details = _changed_fields(previous[p_idx], current[c_idx])
            if fields:
                _mark_current(current[c_idx], CHANGE_CHANGED, fields, details)
            else:
                _mark_current(current[c_idx], CHANGE_NONE)
            prev_unused.discard(p_idx)
            curr_unused.discard(c_idx)

    # 2) Jeśli w tym samym Nr zlec. został dokładnie jeden stary i jeden nowy
    # nierozstrzygnięty rekord, traktujemy to jako zmianę produktu, a nie
    # przypadkowe "usuń + dodaj".
    prev_by_order: dict[str, list[int]] = defaultdict(list)
    curr_by_order: dict[str, list[int]] = defaultdict(list)
    for idx in sorted(prev_unused):
        prev_by_order[_text(previous[idx].get("nr_zlec")).casefold()].append(idx)
    for idx in sorted(curr_unused):
        curr_by_order[_text(current[idx].get("nr_zlec")).casefold()].append(idx)

    for order in sorted(set(prev_by_order) & set(curr_by_order)):
        p_ids = prev_by_order[order]
        c_ids = curr_by_order[order]
        if len(p_ids) != 1 or len(c_ids) != 1:
            continue
        p_idx, c_idx = p_ids[0], c_ids[0]
        fields, details = _changed_fields(previous[p_idx], current[c_idx], force_product=True)
        _mark_current(current[c_idx], CHANGE_CHANGED, fields, details)
        prev_unused.discard(p_idx)
        curr_unused.discard(c_idx)

    previous_orders = {_text(row.get("nr_zlec")).casefold() for row in previous}
    current_orders = {_text(row.get("nr_zlec")).casefold() for row in current}

    # 3) Pozostałe bieżące rekordy są nowymi pozycjami albo całymi zleceniami.
    for c_idx in sorted(curr_unused):
        order = _text(current[c_idx].get("nr_zlec")).casefold()
        if order and order not in previous_orders:
            _mark_current(
                current[c_idx],
                CHANGE_NEW_ORDER,
                ["Nowe zlecenie"],
                [f"Nr zlec. {_text(current[c_idx].get('nr_zlec'))} nie występował w poprzedniej analizie."],
            )
        else:
            _mark_current(
                current[c_idx],
                CHANGE_NEW_ROW,
                ["Nowa pozycja"],
                ["Pozycja nie występowała w poprzedniej analizie tego planu."],
            )

    # 4) Usunięte wiersze zachowujemy osobno, żeby były widoczne w podglądzie.
    removed_rows = []
    for p_idx in sorted(prev_unused):
        row = dict(previous[p_idx])
        order = _text(row.get("nr_zlec")).casefold()
        note = "Pozycja z poprzedniej analizy nie występuje już w bieżącym planie."
        if order and order not in current_orders:
            note = f"Nr zlec. {_text(row.get('nr_zlec'))} nie występuje już w bieżącym planie."
        _mark_current(row, CHANGE_REMOVED, ["Usunięta pozycja"], [note])
        removed_rows.append(row)

    summary: dict[str, int] = defaultdict(int)
    for row in current:
        summary[_text(row.get("excel_change_status")) or CHANGE_NONE] += 1
    for row in removed_rows:
        summary[_text(row.get("excel_change_status")) or CHANGE_REMOVED] += 1

    changed_statuses = {CHANGE_NEW_ORDER, CHANGE_NEW_ROW, CHANGE_CHANGED, CHANGE_REMOVED}
    return {
        "rows": current,
        "removed_rows": removed_rows,
        "change_summary": dict(summary),
        "has_changes": any(summary.get(status, 0) for status in changed_statuses),
        "baseline_created": False,
    }


def _snapshot_path(root=None) -> Path:
    if root is not None:
        return Path(root).joinpath(*SNAPSHOT_RELATIVE)
    from config_manager import ConfigManager

    return Path(ConfigManager().path_anchor(*SNAPSHOT_RELATIVE))


def source_sha256(path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PlanChangeError(f"Nie można policzyć sumy kontrolnej planu Excel: {exc}") from exc
    return digest.hexdigest()


def load_plan_snapshot(*, root=None) -> dict | None:
    path = _snapshot_path(root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanChangeError(f"Nie można odczytać snapshotu planu: {path} ({exc})") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SNAPSHOT_SCHEMA or not isinstance(payload.get("rows"), list):
        raise PlanChangeError(f"Snapshot planu ma nieprawidłowy format: {path}")
    return payload


def _build_snapshot(payload: dict) -> dict:
    source_path = _text(payload.get("source_path"))
    if not source_path:
        raise PlanChangeError("Brak ścieżki źródłowego planu Excel w wyniku importu.")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_path": source_path,
        "source_name": _text(payload.get("source_name")),
        "sheet": _text(payload.get("sheet")),
        "source_sha256": source_sha256(source_path),
        "rows": [_snapshot_row(row) for row in list(payload.get("rows") or []) if isinstance(row, dict)],
    }


def save_plan_snapshot(snapshot: dict, *, root=None) -> Path:
    path = _snapshot_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        raise PlanChangeError(f"Nie można zapisać snapshotu planu pod WM_ROOT: {path} ({exc})") from exc
    return path


def analyze_and_store_plan_changes(payload: dict, *, root=None) -> dict:
    """Porównaj z ostatnim snapshotem, a potem zapisz bieżącą analizę jako nowy punkt odniesienia."""
    previous = load_plan_snapshot(root=root)
    previous_rows = None if previous is None else previous.get("rows", [])
    comparison = compare_plan_rows(previous_rows, list(payload.get("rows") or []))

    result = dict(payload)
    result.update(comparison)
    current_snapshot = _build_snapshot(result)
    path = save_plan_snapshot(current_snapshot, root=root)
    result["snapshot_path"] = str(path)
    result["source_sha256"] = current_snapshot["source_sha256"]
    result["previous_source_sha256"] = _text((previous or {}).get("source_sha256"))
    result["previous_analyzed_at"] = _text((previous or {}).get("analyzed_at"))
    return result


def last_plan_source_path(*, root=None) -> str:
    snapshot = load_plan_snapshot(root=root)
    return _text((snapshot or {}).get("source_path"))
