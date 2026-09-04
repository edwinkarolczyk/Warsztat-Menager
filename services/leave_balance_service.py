# version: 1.0
"""Roczny bilans urlopu WM z przenoszeniem najstarszych dni w pierwszej kolejności."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None

from services.workforce_profile_service import get_user


def ledger_path() -> Path:
    if root_paths is not None:
        try:
            return root_paths.get_data_root() / "leave_balances.json"
        except Exception:
            pass
    return Path("data") / "leave_balances.json"


def _read(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _user_key(login: str) -> str:
    user = get_user(login) or {}
    return str(user.get("user_id") or user.get("id") or login or "").strip()


def _annual_entitlement(login: str) -> float:
    user = get_user(login) or {}
    ent = user.get("entitlements")
    if isinstance(ent, dict) and ent.get("urlop_rocznie") is not None:
        try:
            return float(ent.get("urlop_rocznie"))
        except Exception:
            pass
    old = user.get("urlop")
    if isinstance(old, dict):
        try:
            return float(old.get("nalezne", 26))
        except Exception:
            pass
    return 26.0


def _approved_used(login: str, year: int) -> float:
    try:
        from services.leave_workflow_service import read_leaves
        rows = read_leaves()
    except Exception:
        rows = []
    key = str(login or "").strip().casefold()
    total = 0.0
    prefix = f"{int(year):04d}-"
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("login") or "").strip().casefold() != key:
            continue
        if str(row.get("type") or "").strip().casefold() != "urlop":
            continue
        if not str(row.get("date") or "").startswith(prefix):
            continue
        try:
            total += float(row.get("quantity_days") or 1.0)
        except Exception:
            total += 1.0
    return total


def _pending(login: str, year: int) -> float:
    try:
        from services.leave_workflow_service import read_requests
        rows = read_requests(login=login, status="pending")
    except Exception:
        rows = []
    prefix = f"{int(year):04d}-"
    days: set[str] = set()
    for row in rows:
        for raw in row.get("dates") or []:
            text = str(raw)
            if text.startswith(prefix):
                days.add(text[:10])
    return float(len(days))


def _load_ledger() -> dict:
    doc = _read(ledger_path(), {})
    return doc if isinstance(doc, dict) else {}


def _save_ledger(doc: dict) -> None:
    _write(ledger_path(), doc)


def _year_row(login: str, year: int, *, create: bool = True) -> tuple[dict, dict, str]:
    doc = _load_ledger()
    users = doc.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        doc["users"] = users
    uid = _user_key(login)
    person = users.setdefault(uid, {"login_snapshot": login, "years": {}})
    if not isinstance(person, dict):
        person = {"login_snapshot": login, "years": {}}
        users[uid] = person
    person["login_snapshot"] = login
    years = person.setdefault("years", {})
    if not isinstance(years, dict):
        years = {}
        person["years"] = years
    key = str(int(year))
    row = years.get(key)
    if not isinstance(row, dict) and create:
        row = {
            "entitlement": _annual_entitlement(login),
            "adjustment": 0.0,
            "manual_carryover": {},
        }
        years[key] = row
        _save_ledger(doc)
    return doc, row if isinstance(row, dict) else {}, uid


def set_year_values(login: str, year: int, *, entitlement: float | None = None,
                    adjustment: float | None = None,
                    carryover: dict[int | str, float] | None = None) -> None:
    """Korekta brygadzisty; carryover zachowuje rok pochodzenia dni."""
    doc, row, _uid = _year_row(login, year, create=True)
    if entitlement is not None:
        row["entitlement"] = float(entitlement)
    if adjustment is not None:
        row["adjustment"] = float(adjustment)
    if carryover is not None:
        row["manual_carryover"] = {
            str(int(source_year)): max(0.0, float(value))
            for source_year, value in carryover.items()
            if float(value) > 0
        }
    _save_ledger(doc)


def _explicit_carryover(login: str, year: int) -> dict[int, float]:
    _doc, row, _uid = _year_row(login, year, create=True)
    raw = row.get("manual_carryover")
    out: dict[int, float] = {}
    if isinstance(raw, dict):
        for source, value in raw.items():
            try:
                amount = float(value)
                source_year = int(source)
            except Exception:
                continue
            if amount > 0 and source_year < int(year):
                out[source_year] = amount
    return out


def _computed_carryover(login: str, year: int, _seen: set[int] | None = None) -> dict[int, float]:
    """Przenieś niewykorzystane saldo z poprzedniego roku z zachowaniem pochodzenia."""
    if int(year) <= 2000:
        return {}
    seen = set(_seen or set())
    if year in seen:
        return {}
    seen.add(year)

    explicit = _explicit_carryover(login, year)
    if explicit:
        return explicit

    # Pierwszy rok, o którym nic nie wiemy, nie wymyśla zaległego urlopu.
    _doc, prev_row, _uid = _year_row(login, year - 1, create=False)
    if not prev_row:
        user = get_user(login) or {}
        old = user.get("urlop") if isinstance(user, dict) else None
        legacy_carry = None
        if isinstance(old, dict):
            legacy_carry = old.get("zalegly", old.get("przeniesione"))
        try:
            value = float(legacy_carry or 0.0)
        except Exception:
            value = 0.0
        return {year - 1: value} if value > 0 else {}

    prev = get_balance(login, year - 1, _seen=seen)
    out: dict[int, float] = {}
    for source, value in (prev.get("remaining_by_source") or {}).items():
        try:
            amount = float(value)
            source_year = int(source)
        except Exception:
            continue
        if amount > 0:
            out[source_year] = amount
    return out


def _consume_oldest(buckets: dict[int, float], used: float) -> dict[int, float]:
    remaining = {int(year): max(0.0, float(value)) for year, value in buckets.items()}
    left = max(0.0, float(used))
    for source_year in sorted(remaining):
        if left <= 0:
            break
        available = remaining[source_year]
        take = min(available, left)
        remaining[source_year] = available - take
        left -= take
    return remaining


def get_balance(login: str, year: int | None = None, *, _seen: set[int] | None = None) -> dict[str, Any]:
    year = int(year or date.today().year)
    _doc, row, uid = _year_row(login, year, create=True)
    try:
        entitlement = float(row.get("entitlement", _annual_entitlement(login)))
    except Exception:
        entitlement = _annual_entitlement(login)
    try:
        adjustment = float(row.get("adjustment", 0.0))
    except Exception:
        adjustment = 0.0

    carry = _computed_carryover(login, year, _seen=_seen)
    buckets: dict[int, float] = dict(carry)
    buckets[year] = max(0.0, entitlement + adjustment)
    used = _approved_used(login, year)
    remaining_by_source = _consume_oldest(buckets, used)
    carried_total = sum(value for source, value in buckets.items() if source < year)
    remaining = sum(remaining_by_source.values())
    pending = _pending(login, year)

    consumed_by_source = {
        source: max(0.0, buckets.get(source, 0.0) - remaining_by_source.get(source, 0.0))
        for source in buckets
    }
    return {
        "user_id": uid,
        "login": login,
        "year": year,
        "entitlement": entitlement,
        "adjustment": adjustment,
        "carryover": carried_total,
        "available": sum(buckets.values()),
        "used": used,
        "pending": pending,
        "remaining": remaining,
        "projected_remaining": remaining - pending,
        "buckets": {str(k): v for k, v in sorted(buckets.items())},
        "remaining_by_source": {str(k): v for k, v in sorted(remaining_by_source.items())},
        "consumed_by_source": {str(k): v for k, v in sorted(consumed_by_source.items())},
    }


def can_request(login: str, dates: list[str], year: int | None = None) -> tuple[bool, float]:
    if not dates:
        return False, 0.0
    target_year = int(year or str(dates[0])[:4])
    count = float(sum(1 for day in dates if str(day).startswith(f"{target_year:04d}-")))
    bal = get_balance(login, target_year)
    available_after_pending = float(bal.get("remaining") or 0.0) - float(bal.get("pending") or 0.0)
    return count <= available_after_pending, available_after_pending - count


__all__ = ["ledger_path", "get_balance", "set_year_values", "can_request"]
