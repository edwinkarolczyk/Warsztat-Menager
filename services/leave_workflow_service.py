# version: 1.0
"""Workflow urlopów i L4 dla Profilu WM.

Urlopy pracowników są najpierw zapisywane jako wnioski w ``leave_requests.json``.
Dopiero akceptacja brygadzisty tworzy właściwe wpisy w istniejącym ``leaves.json``.
L4 brygadzista dodaje bezpośrednio do ``leaves.json``.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from core import root_paths
from services.profile_service import get_user

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


def _leave_candidates() -> list[Path]:
    candidates = [
        root_paths.get_root_anchor() / "leaves.json",
        root_paths.get_data_root() / "leaves.json",
        root_paths.get_data_root() / "profile" / "leaves.json",
        Path.cwd() / "leaves.json",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def leaves_path() -> Path:
    """Zwróć aktywny leaves.json zgodny z panelem brygadzisty."""
    existing: list[tuple[float, Path]] = []
    for path in _leave_candidates():
        try:
            if path.is_file():
                existing.append((path.stat().st_mtime, path))
        except Exception:
            continue
    if existing:
        existing.sort(key=lambda item: item[0], reverse=True)
        return existing[0][1]
    return root_paths.get_root_anchor() / "leaves.json"


def requests_path() -> Path:
    """Wnioski mają jedno stałe miejsce niezależne od legacy leaves.json."""
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
    out.sort(
        key=lambda row: (
            str(row.get("created_at") or ""),
            str(row.get("date_start") or ""),
        ),
        reverse=True,
    )
    return out


def _parse_day(value: str | date) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError("Brak daty.")
    return date.fromisoformat(text)


def dates_from_range(
    start: str | date,
    end: str | date,
    *,
    include_sundays: bool = False,
) -> list[str]:
    """Zwróć daty z zakresu; urlop pomija niedziele, L4 może je obejmować."""
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


def _same_day(row: dict, login: str, day: str, type_: str | None = None) -> bool:
    if str(row.get("login") or "").strip().casefold() != login.casefold():
        return False
    if str(row.get("date") or "")[:10] != day:
        return False
    if type_ is None:
        return True
    return str(row.get("type") or "").strip().casefold() == type_.casefold()


def request_vacation(login: str, dates: Iterable[str | date], note: str = "") -> str:
    """Utwórz wniosek urlopowy oczekujący na decyzję brygadzisty."""
    login = str(login or "").strip()
    if not login:
        raise ValueError("Brak loginu pracownika.")
    selected = _normalize_dates(dates)

    leaves = read_leaves()
    for day in selected:
        if any(_same_day(row, login, day) for row in leaves):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")

    pending = read_requests(login=login, status=_PENDING)
    pending_days = {
        str(day)
        for request in pending
        for day in (request.get("dates") or [])
    }
    overlap = [day for day in selected if day in pending_days]
    if overlap:
        raise ValueError(f"Wniosek na {overlap[0]} już oczekuje na decyzję.")

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
    }
    rows = _as_list(_read_json(requests_path(), []))
    rows.append(row)
    _write_json(requests_path(), rows)
    return request_id


def _require_foreman(actor_login: str) -> str:
    actor = str(actor_login or "").strip()
    if not actor:
        raise PermissionError("Brak zalogowanego brygadzisty.")
    try:
        user = get_user(actor) or {}
    except Exception:
        user = {}
    role = str(user.get("rola") or user.get("role") or "").strip().casefold()
    if role != "brygadzista":
        raise PermissionError("Tę operację może wykonać tylko brygadzista.")
    return actor


def _find_request(rows: list[dict], request_id: str) -> tuple[int, dict]:
    wanted = str(request_id or "").strip()
    for idx, row in enumerate(rows):
        if str(row.get("id") or "").strip() == wanted:
            return idx, row
    raise KeyError("Nie znaleziono wniosku.")


def approve_request(request_id: str, actor_login: str) -> dict:
    actor = _require_foreman(actor_login)
    request_rows = _as_list(_read_json(requests_path(), []))
    idx, request = _find_request(request_rows, request_id)
    if str(request.get("status") or "").casefold() != _PENDING:
        raise ValueError("Ten wniosek został już rozpatrzony.")

    login = str(request.get("login") or "").strip()
    dates = _normalize_dates(request.get("dates") or [])
    leave_rows = read_leaves()
    for day in dates:
        if any(_same_day(row, login, day) for row in leave_rows):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")

    short_id = str(request.get("id") or uuid.uuid4().hex)[-10:]
    created = _utc_now()
    for day in dates:
        leave_rows.append(
            {
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
            }
        )
    _write_json(leaves_path(), leave_rows)

    updated = dict(request)
    updated["status"] = _APPROVED
    updated["approved_by"] = actor
    updated["decision_at"] = created
    request_rows[idx] = updated
    _write_json(requests_path(), request_rows)
    return updated


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


def add_l4(
    login: str,
    dates: Iterable[str | date],
    actor_login: str,
    note: str = "",
) -> int:
    """Brygadzista dodaje L4 bez etapu akceptacji."""
    actor = _require_foreman(actor_login)
    login = str(login or "").strip()
    if not login:
        raise ValueError("Wybierz pracownika.")
    selected = _normalize_dates(dates)
    rows = read_leaves()
    added = 0
    created = _utc_now()
    token = uuid.uuid4().hex[-10:]
    for day in selected:
        if any(_same_day(row, login, day) for row in rows):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")
        rows.append(
            {
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
            }
        )
        added += 1
    _write_json(leaves_path(), rows)
    return added


def calendar_snapshot(login: str, year: int, month: int) -> dict[str, Any]:
    """Dane kalendarza jednego pracownika."""
    prefix = f"{int(year):04d}-{int(month):02d}-"
    login_key = str(login or "").strip().casefold()
    leaves = [
        row
        for row in read_leaves()
        if str(row.get("login") or "").strip().casefold() == login_key
        and str(row.get("date") or "").startswith(prefix)
    ]
    requests = []
    for row in read_requests(login=login):
        dates = [str(day) for day in (row.get("dates") or [])]
        if any(day.startswith(prefix) for day in dates):
            requests.append(row)
    return {"leaves": leaves, "requests": requests}


__all__ = [
    "add_l4",
    "approve_request",
    "calendar_snapshot",
    "dates_from_range",
    "leaves_path",
    "read_leaves",
    "read_requests",
    "reject_request",
    "request_vacation",
    "requests_path",
]
