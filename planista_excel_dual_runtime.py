# WM-VERSION: 0.1
# Plik: planista_excel_dual_runtime.py
"""Dwa równorzędne plany Excel; warstwa źródeł, nie zastępuje silnika zleceń."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading

from config_manager import ConfigManager
from planista_excel_auto_runtime import parse_from_detached_copy
from planista_excel_import import load_production_plan
from planista_excel_match import (
    STATUS_AMBIGUOUS, STATUS_FOUND, STATUS_MISSING, match_production_plan,
    normalize_designation, excel_mapping_key,
)
from planista_excel_changes import compare_plan_rows
from planista_excel_mappings import load_manual_mappings

_LOCK = threading.RLock()
_FILENAME = "excel_dual_state.json"


def _path() -> Path:
    return Path(ConfigManager().path_data()) / "planista" / _FILENAME


def _empty() -> dict:
    return {"schema": 1, "sources": {}, "merged_rows": [], "resolutions": {}, "history": []}


def load_dual_state() -> dict:
    with _LOCK:
        try:
            data = json.loads(_path().read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and data.get("schema") == 1 else _empty()
        except (OSError, ValueError):
            return _empty()


def _save(state: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _identity(row: dict) -> str:
    order = str(row.get("nr_zlec") or "").strip().casefold()
    code = str(row.get("wm_symbol") or "").strip()
    if row.get("match_status") == STATUS_FOUND and code:
        product = "WM:" + normalize_designation(code)
    else:
        product = "EXCEL:" + excel_mapping_key(row.get("produkt"))
    return order + "|" + product


def _facts(row: dict) -> tuple:
    return (
        str(row.get("produkt") or "").strip().casefold(),
        row.get("ilosc"),
        str(row.get("data_wysylki") or "").strip(),
        str(row.get("proces") or "").strip().casefold(),
    )


def _signature(rows: dict[str, dict]) -> str:
    payload = [
        (key, _facts(row)) for key, row in sorted(rows.items())
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _read_one(path: str, products: dict, mappings: dict) -> dict:
    def parse(temp: Path) -> dict:
        payload = load_production_plan(temp, sheet_name="PLAN 2026")
        return match_production_plan(payload, products, manual_mappings=mappings)
    payload = parse_from_detached_copy(path, parse)
    payload["source_path"] = str(Path(path).expanduser().resolve())
    payload["source_name"] = Path(path).name
    return payload


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if isinstance(row, dict):
            result[_identity(row)].append(row)
    return result


def _merge(state: dict, *, fully_available: bool) -> dict:
    sources = state["sources"]
    a = _group(sources.get("A", {}).get("rows") or [])
    b = _group(sources.get("B", {}).get("rows") or [])
    rows = []
    conflicts = []
    resolutions = state.get("resolutions") or {}
    for key in sorted(set(a) | set(b)):
        aa, bb = a.get(key, []), b.get(key, [])
        if len(aa) > 1 or len(bb) > 1:
            # Każda partia pozostaje widoczna. Dopasuj identyczne partie z A/B
            # tylko 1:1, nie wolno zgubić powtarzającego się wiersza.
            reason = "Powtarzający się produkt w jednym zleceniu — rozróżnij partie przed synchronizacją."
            used_b: set[int] = set()
            batch_rows: list[tuple[dict, str]] = []
            for item_a in aa:
                matched = next(
                    (idx for idx, item_b in enumerate(bb)
                     if idx not in used_b and _facts(item_a) == _facts(item_b)),
                    None,
                )
                if matched is not None:
                    used_b.add(matched)
                batch_rows.append((item_a, "A+B" if matched is not None else "A"))
            for idx, item_b in enumerate(bb):
                if idx not in used_b:
                    batch_rows.append((item_b, "B"))
            for raw, source_tag in batch_rows:
                selected_batch = dict(raw)
                selected_batch.update({
                    "match_status": STATUS_AMBIGUOUS,
                    "match_category": "Możliwy produkt — potwierdź",
                    "match_note": reason,
                    "wm_symbol": "",
                    "source_tag": source_tag,
                    "source_row_original": raw.get("source_row"),
                    "source_row": len(rows) + 1,
                })
                rows.append(selected_batch)
            conflicts.append({
                "key": key, "reason": reason, "A": aa, "B": bb,
                "signature": "", "status": "Do rozróżnienia partii",
            })
            continue
        elif aa and bb and _facts(aa[0]) != _facts(bb[0]):
            options = {"A": aa[0], "B": bb[0]}
            reason = "Excel A i B zawierają różne ilości, terminy, proces lub wariant."
            signature = _signature(options)
            previous = resolutions.get(key) or {}
            decision = previous.get("decision") if previous.get("signature") == signature else ""
            selected = dict(options.get(decision) or options["A"])
            if decision == "Własne":
                selected.update(previous.get("values") or {})
            if decision:
                reason = ""
        else:
            options = {}
            reason = ""
            signature = ""
            selected = dict((aa or bb)[0])
        if reason:
            selected["match_status"] = STATUS_AMBIGUOUS
            selected["match_category"] = "Możliwy produkt — potwierdź"
            selected["match_note"] = reason
            selected["wm_symbol"] = ""
            conflicts.append({"key": key, "reason": reason, "A": aa, "B": bb,
                              "signature": signature, "status": "Do decyzji"})
        selected["source_tag"] = "A+B" if aa and bb else ("A" if aa else "B")
        selected["source_row_original"] = selected.get("source_row")
        selected["source_row"] = len(rows) + 1
        if not fully_available:
            selected["match_status"] = STATUS_AMBIGUOUS
            selected["wm_symbol"] = ""
            selected["match_note"] = "Niepełny odczyt źródeł — automatyczny zapis zablokowany."
        rows.append(selected)
    return {"rows": rows, "conflicts": conflicts}


def inspect_dual_plans(source_a: str, source_b: str) -> dict:
    """Odczytaj obie odłączone kopie i przekaż scalony wynik staremu silnikowi."""
    from gui_magazyn_bom import WarehouseModel
    products = WarehouseModel().produkty
    mappings = load_manual_mappings()
    with _LOCK:
        state = load_dual_state()
        source_errors = []
        diagnostics = {"source_rows": 0, "imported_rows": 0,
                       "skipped_rows": [], "row_warnings": []}
        for label, path in (("A", source_a), ("B", source_b)):
            target = str(Path(path).expanduser().resolve()) if path else ""
            previous = state["sources"].get(label) or {}
            if previous.get("path") != target:
                previous = {}
            if not target:
                state["sources"][label] = {"path": "", "rows": [], "status": "Nie wskazano"}
                source_errors.append(f"{label}: nie wskazano pliku")
                continue
            try:
                payload = _read_one(target, products, mappings)
                current = dict(previous)
                current.update({"path": target, "rows": payload["rows"],
                                "status": "OK", "checked_at": _now(),
                                "source_name": Path(target).name})
                current["diff"] = compare_plan_rows(
                    previous.get("rows") if previous else None, payload["rows"]
                ).get("change_summary", {})
                current["diagnostics"] = payload.get("import_diagnostics") or {}
                state["sources"][label] = current
            except Exception as exc:
                previous["path"] = target
                previous["status"] = f"Błąd: {exc}"
                state["sources"][label] = previous
                source_errors.append(f"{label}: {exc}")
            diag = state["sources"][label].get("diagnostics") or {}
            diagnostics["source_rows"] += int(diag.get("source_rows") or 0)
            diagnostics["imported_rows"] += int(diag.get("imported_rows") or 0)
            diagnostics["skipped_rows"].extend(
                {"source": label, **entry} for entry in diag.get("skipped_rows") or []
            )
            diagnostics["row_warnings"].extend(
                {"source": label, **entry} for entry in diag.get("row_warnings") or []
            )
        merged = _merge(state, fully_available=not source_errors)
        comparison = compare_plan_rows(state.get("merged_rows"), merged["rows"])
        # Przypisz globalne numery wierszy raportu, aby walidacja synchronizacji
        # odróżniała identyczne numery wierszy pochodzące z różnych plików.
        warnings = []
        for row in merged["rows"]:
            original = row.get("source_row_original")
            for label in row["source_tag"].split("+"):
                for issue in (state["sources"].get(label, {}).get("diagnostics") or {}).get("row_warnings") or []:
                    if issue.get("source_row") == original:
                        warnings.append({"source_row": row["source_row"],
                                         "reasons": issue.get("reasons") or []})
        diagnostics["row_warnings"] = warnings
        state["merged_rows"] = merged["rows"]
        state["history"] = (state.get("history") or [])[-199:] + [{
            "at": _now(), "event": "Kontrola źródeł",
            "changes": comparison.get("change_summary") or {},
            "conflicts": len(merged["conflicts"]),
            "errors": source_errors,
        }]
        _save(state)
    counted = {STATUS_FOUND: 0, STATUS_MISSING: 0, STATUS_AMBIGUOUS: 0}
    for row in comparison["rows"]:
        status = row.get("match_status")
        if status in counted:
            counted[status] += 1
    return {
        **comparison, "source_name": "Excel A + Excel B",
        "source_path": source_a, "sheet": "PLAN 2026",
        "match_summary": counted, "product_catalog_size": len(products),
        "import_diagnostics": diagnostics, "dual_source_errors": source_errors,
        "dual_conflicts": merged["conflicts"], "dual_sources": state["sources"],
        "dual_mode": True,
    }


def resolve_dual_conflict(key: str, signature: str, decision: str,
                          values: dict | None = None, user: str = "") -> None:
    if decision not in {"A", "B", "Własne"}:
        raise ValueError("Wybierz Excel A, Excel B lub własne wartości.")
    with _LOCK:
        state = load_dual_state()
        state["resolutions"][key] = {
            "signature": signature, "decision": decision,
            "values": dict(values or {}), "user": user, "at": _now(),
        }
        state["history"] = (state.get("history") or [])[-199:] + [{
            "at": _now(), "event": "Konflikt rozstrzygnięty", "key": key,
            "decision": decision, "user": user,
        }]
        _save(state)
