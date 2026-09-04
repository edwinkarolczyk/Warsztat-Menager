# version: 1.1
"""Workflow urlopów i L4 dla Profilu WM.

Jedno kanoniczne źródło ``<ROOT>/leaves.json`` oraz ``<ROOT>/leave_requests.json``.
Urlop jest rozliczany rocznie przez leave_balance_service; przy wykorzystaniu
najpierw schodzi najstarszy dostępny urlop zaległy. Akceptacja zapisuje dwa
pliki transakcyjnie z rollbackiem.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from core import root_paths
from services.workforce_profile_service import get_user, is_foreman

_PENDING = "pending"
_APPROVED = "approved"
_REJECTED = "rejected"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _canonical_leaves_path() -> Path:
    return root_paths.get_root_anchor() / "leaves.json"


def _legacy_leave_candidates() -> list[Path]:
    canonical = _canonical_leaves_path()
    candidates = [
        root_paths.get_data_root() / "leaves.json",
        root_paths.get_data_root() / "profile" / "leaves.json",
    ]
    out: list[Path] = []
    for path in candidates:
        try:
            if path.resolve() != canonical.resolve():
                out.append(path)
        except Exception:
            out.append(path)
    return out


def _ensure_canonical_leaves() -> Path:
    """Jednorazowo skopiuj legacy, ale nigdy nie wybieraj źródła po mtime."""
    canonical = _canonical_leaves_path()
    if canonical.exists():
        return canonical
    for legacy in _legacy_leave_candidates():
        try:
            if legacy.is_file():
                canonical.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, canonical)
                return canonical
        except Exception:
            continue
    return canonical


def leaves_path() -> Path:
    return _ensure_canonical_leaves()


def requests_path() -> Path:
    return root_paths.get_root_anchor() / "leave_requests.json"


def _as_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "requests", "leaves"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [dict(item) for item in rows if isinstance(item, dict)]
    return []


def read_leaves() -> list[dict]:
    return _as_list(_read_json(leaves_path(), []))


def read_requests(login: str | None = None, status: str | None = None) -> list[dict]:
    rows = _as_list(_read_json(requests_path(), []))
    login_key = str(login or "").strip().casefold()
    status_key = str(status or "").strip().casefold()
    out: list[dict] = []
    for row in rows:
        if login_key and str(row.get("login") or "").strip().casefold() != login_key:
            continue
        if status_key and str(row.get("status") or "").strip().casefold() != status_key:
            continue
        out.append(row)
    out.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("date_start") or "")), reverse=True)
    return out


def _parse_day(value: str | date) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError("Brak daty.")
    return date.fromisoformat(text)


def dates_from_range(start: str | date, end: str | date, *, include_sundays: bool = False) -> list[str]:
    first = _parse_day(start)
    last = _parse_day(end)
    if last < first:
        first, last = last, first
    if (last - first).days > 62:
        raise ValueError("Jednorazowo można zaznaczyć maksymalnie 63 dni.")
    rows: list[str] = []
    current = first
    while current <= last:
        if include_sundays or current.weekday() != 6:
            rows.append(current.isoformat())
        current += timedelta(days=1)
    return rows


def _normalize_dates(values: Iterable[str | date]) -> list[str]:
    unique = sorted({_parse_day(value).isoformat() for value in values})
    if not unique:
        raise ValueError("Nie wybrano żadnego dnia.")
    return unique


def _user_workdays(login: str) -> set[int]:
    user = get_user(login) or {}
    raw = user.get("workdays") or user.get("dni_pracy")
    if not isinstance(raw, list) or not raw:
        return {0, 1, 2, 3, 4}
    out: set[int] = set()
    for item in raw:
        try:
            value = int(item)
        except Exception:
            continue
        if 0 <= value <= 6:
            out.add(value)
    return out or {0, 1, 2, 3, 4}


def _vacation_workdays(login: str, values: list[str]) -> list[str]:
    workdays = _user_workdays(login)
    return [day for day in values if _parse_day(day).weekday() in workdays]


def _same_day(row: dict, login: str, day: str, type_: str | None = None) -> bool:
    if str(row.get("login") or "").strip().casefold() != login.casefold():
        return False
    if str(row.get("date") or "")[:10] != day:
        return False
    if type_ is None:
        return True
    return str(row.get("type") or "").strip().casefold() == type_.casefold()


def request_vacation(login: str, dates: Iterable[str | date], note: str = "") -> str:
    login = str(login or "").strip()
    if not login:
        raise ValueError("Brak loginu pracownika.")
    selected = _vacation_workdays(login, _normalize_dates(dates))
    if not selected:
        raise ValueError("Wybrane dni nie są dniami pracy tego pracownika.")

    leaves = read_leaves()
    for day in selected:
        if any(_same_day(row, login, day) for row in leaves):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")

    pending = read_requests(login=login, status=_PENDING)
    pending_days = {str(day) for request in pending for day in (request.get("dates") or [])}
    overlap = [day for day in selected if day in pending_days]
    if overlap:
        raise ValueError(f"Wniosek na {overlap[0]} już oczekuje na decyzję.")

    # Nie blokujemy samego zgłoszenia ponad saldo; oznaczamy je dla brygadzisty.
    balance_warning = False
    over_by = 0.0
    try:
        from services.leave_balance_service import get_balance
        by_year: dict[int, int] = {}
        for day in selected:
            by_year[int(day[:4])] = by_year.get(int(day[:4]), 0) + 1
        for year, count in by_year.items():
            bal = get_balance(login, year)
            after_pending = float(bal.get("remaining") or 0.0) - float(bal.get("pending") or 0.0)
            if float(count) > after_pending:
                balance_warning = True
                over_by += float(count) - max(0.0, after_pending)
    except Exception:
        pass

    request_id = f"req_{uuid.uuid4().hex}"
    row = {
        "id": request_id,
        "login": login,
        "type": "urlop",
        "dates": selected,
        "date_start": selected[0],
        "date_end": selected[-1],
        "quantity_days": float(len(selected)),
        "status": _PENDING,
        "requested_by": login,
        "created_at": _utc_now(),
        "note": str(note or "").strip(),
        "approved_by": None,
        "decision_at": None,
        "over_balance": bool(balance_warning),
        "over_by_days": float(over_by),
    }
    rows = _as_list(_read_json(requests_path(), []))
    rows.append(row)
    _write_json(requests_path(), rows)
    return request_id


def _require_foreman(actor_login: str) -> str:
    actor = str(actor_login or "").strip()
    if not actor:
        raise PermissionError("Brak zalogowanego brygadzisty.")
    if not is_foreman(actor):
        raise PermissionError("Tę operację może wykonać tylko brygadzista.")
    return actor


def _find_request(rows: list[dict], request_id: str) -> tuple[int, dict]:
    wanted = str(request_id or "").strip()
    for idx, row in enumerate(rows):
        if str(row.get("id") or "").strip() == wanted:
            return idx, row
    raise KeyError("Nie znaleziono wniosku.")


def _source_years_for_dates(login: str, dates: list[str]) -> dict[str, int]:
    """Przydziel każdy dzień do najstarszego dostępnego koszyka urlopu."""
    result: dict[str, int] = {}
    balances: dict[int, dict[int, float]] = {}
    for day in dates:
        target_year = int(day[:4])
        if target_year not in balances:
            try:
                from services.leave_balance_service import get_balance
                bal = get_balance(login, target_year)
                balances[target_year] = {
                    int(source): float(value)
                    for source, value in (bal.get("remaining_by_source") or {}).items()
                }
            except Exception:
                balances[target_year] = {target_year: 999999.0}
        buckets = balances[target_year]
        source = target_year
        for candidate in sorted(buckets):
            if buckets[candidate] > 0:
                source = candidate
                buckets[candidate] -= 1.0
                break
        result[day] = source
    return result


def _slot_for_attendance(login: str, day: str) -> str:
    try:
        profile = get_user(login) or {}
        import gui_logowanie
        resolver = getattr(gui_logowanie, "_slot_for_user", None)
        if callable(resolver):
            moment = datetime.combine(_parse_day(day), datetime.strptime("12:00", "%H:%M").time())
            slot = resolver(profile, moment)
            if slot in {"RANO", "POPO"}:
                return slot
    except Exception:
        pass
    return "RANO"


def _sync_attendance_reason(login: str, dates: Iterable[str], actor: str, reason: str) -> None:
    try:
        from services import attendance_service
    except Exception:
        return
    for day in dates:
        try:
            attendance_service.set_reason(
                day,
                _slot_for_attendance(login, day),
                login,
                actor,
                reason,
                _utc_now(),
            )
        except Exception:
            continue


def approve_request(request_id: str, actor_login: str, *, allow_over_balance: bool = False) -> dict:
    actor = _require_foreman(actor_login)
    request_rows = _as_list(_read_json(requests_path(), []))
    idx, request = _find_request(request_rows, request_id)
    if str(request.get("status") or "").casefold() != _PENDING:
        raise ValueError("Ten wniosek został już rozpatrzony.")
    if request.get("over_balance") and not allow_over_balance:
        over = float(request.get("over_by_days") or 0.0)
        raise ValueError(
            f"Wniosek przekracza dostępny urlop o {_fmt_days(over)} dni. "
            "Brygadzista musi jawnie potwierdzić przekroczenie."
        )

    login = str(request.get("login") or "").strip()
    dates = _normalize_dates(request.get("dates") or [])
    leave_rows_before = read_leaves()
    for day in dates:
        if any(_same_day(row, login, day) for row in leave_rows_before):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")

    source_year = _source_years_for_dates(login, dates)
    leave_rows = [dict(row) for row in leave_rows_before]
    short_id = str(request.get("id") or uuid.uuid4().hex)[-10:]
    created = _utc_now()
    for day in dates:
        leave_rows.append({
            "id": f"leave_{day}_{login}_urlop_{short_id}",
            "login": login,
            "type": "urlop",
            "date": day,
            "shift": None,
            "quantity_days": 1.0,
            "minutes": 0,
            "approved_by": actor,
            "created_at": created,
            "note": str(request.get("note") or ""),
            "request_id": request.get("id"),
            "leave_source_year": int(source_year.get(day, int(day[:4]))),
        })

    updated = dict(request)
    updated["status"] = _APPROVED
    updated["approved_by"] = actor
    updated["decision_at"] = created
    updated["over_balance_override"] = bool(request.get("over_balance") and allow_over_balance)
    request_rows[idx] = updated

    # Dwa dokumenty: jeśli drugi zapis nie wyjdzie, przywracamy pierwszy.
    _write_json(leaves_path(), leave_rows)
    try:
        _write_json(requests_path(), request_rows)
    except Exception:
        try:
            _write_json(leaves_path(), leave_rows_before)
        except Exception as rollback_exc:
            raise RuntimeError(
                "Nie udało się zapisać decyzji ani przywrócić ewidencji urlopu. "
                f"Rollback: {rollback_exc}"
            )
        raise

    _sync_attendance_reason(login, dates, actor, "UR")
    return updated


def _fmt_days(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{float(value):.1f}"


def reject_request(request_id: str, actor_login: str, reason: str = "") -> dict:
    actor = _require_foreman(actor_login)
    rows = _as_list(_read_json(requests_path(), []))
    idx, request = _find_request(rows, request_id)
    if str(request.get("status") or "").casefold() != _PENDING:
        raise ValueError("Ten wniosek został już rozpatrzony.")
    updated = dict(request)
    updated["status"] = _REJECTED
    updated["approved_by"] = actor
    updated["decision_at"] = _utc_now()
    updated["decision_note"] = str(reason or "").strip()
    rows[idx] = updated
    _write_json(requests_path(), rows)
    return updated


def add_l4(login: str, dates: Iterable[str | date], actor_login: str, note: str = "") -> int:
    actor = _require_foreman(actor_login)
    login = str(login or "").strip()
    if not login:
        raise ValueError("Wybierz pracownika.")
    selected = _normalize_dates(dates)
    rows_before = read_leaves()
    rows = [dict(row) for row in rows_before]
    added = 0
    created = _utc_now()
    token = uuid.uuid4().hex[-10:]
    for day in selected:
        if any(_same_day(row, login, day) for row in rows):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")
        rows.append({
            "id": f"leave_{day}_{login}_l4_{token}",
            "login": login,
            "type": "l4",
            "date": day,
            "shift": None,
            "quantity_days": 1.0,
            "minutes": 0,
            "approved_by": actor,
            "created_at": created,
            "note": str(note or "").strip(),
            "entered_by": actor,
        })
        added += 1
    _write_json(leaves_path(), rows)
    _sync_attendance_reason(login, selected, actor, "L4")
    return added


def add_nn(login: str, dates: Iterable[str | date], actor_login: str, note: str = "") -> int:
    actor = _require_foreman(actor_login)
    login = str(login or "").strip()
    selected = _normalize_dates(dates)
    rows = read_leaves()
    created = _utc_now()
    token = uuid.uuid4().hex[-10:]
    for day in selected:
        if any(_same_day(row, login, day) for row in rows):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")
        rows.append({
            "id": f"leave_{day}_{login}_nn_{token}", "login": login, "type": "nn",
            "date": day, "shift": None, "quantity_days": 1.0, "minutes": 0,
            "approved_by": actor, "created_at": created, "note": str(note or ""),
            "entered_by": actor,
        })
    _write_json(leaves_path(), rows)
    _sync_attendance_reason(login, selected, actor, "NN")
    return len(selected)


def calendar_snapshot(login: str, year: int, month: int) -> dict[str, Any]:
    prefix = f"{int(year):04d}-{int(month):02d}-"
    login_key = str(login or "").strip().casefold()
    leaves = [
        row for row in read_leaves()
        if str(row.get("login") or "").strip().casefold() == login_key
        and str(row.get("date") or "").startswith(prefix)
    ]
    requests = []
    for row in read_requests(login=login):
        dates = [str(day) for day in (row.get("dates") or [])]
        if any(day.startswith(prefix) for day in dates):
            requests.append(row)
    try:
        from services.leave_balance_service import get_balance
        balance = get_balance(login, year)
    except Exception:
        balance = {}
    return {"leaves": leaves, "requests": requests, "balance": balance}


__all__ = [
    "add_l4", "add_nn", "approve_request", "calendar_snapshot", "dates_from_range",
    "leaves_path", "read_leaves", "read_requests", "reject_request",
    "request_vacation", "requests_path",
]
