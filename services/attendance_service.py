# version: 1.0
"""Jedno źródło prawdy dla dniówek i nadgodzin WM.

Warstwa jest zgodna z istniejącym ``attendance_utils`` i rozszerza jego
``ewidencja_obecnosci.json`` bez zmiany starej struktury dzień/zmiana/login.
Nie liczymy spóźnień. Pierwsze logowanie jest zachowywane, kolejne tylko
aktualizują historię. Sobota jest ewidencjonowana oddzielnie jako kandydat
nadgodzin sobotnich.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None

try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore

RANO = "RANO"
POPO = "POPO"
VALID_SLOTS = {RANO, POPO}

STATUS_PRESENT = "PRESENT"
STATUS_PENDING_LATE = "PENDING_LATE"
STATUS_MISSING = "MISSING"
STATUS_EXCUSED = "EXCUSED"
STATUS_SATURDAY = "OVERTIME_SATURDAY"

SHIFT_RULES = {
    RANO: {
        "shift_start": time(6, 0),
        "shift_end": time(14, 0),
        "early_from": time(5, 0),
        "auto_until": time(12, 0),
    },
    POPO: {
        "shift_start": time(14, 0),
        "shift_end": time(22, 0),
        "early_from": time(13, 0),
        "auto_until": time(20, 0),
    },
}


def data_path() -> Path:
    if root_paths is not None:
        try:
            return root_paths.get_data_root() / "ewidencja_obecnosci.json"
        except Exception:
            pass
    if ConfigManager is not None:
        try:
            return Path(ConfigManager().path_data("ewidencja_obecnosci.json"))
        except Exception:
            pass
    return Path("data") / "ewidencja_obecnosci.json"


def audit_path() -> Path:
    return data_path().with_name("ewidencja_obecnosci_audit.json")


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


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _profile_for_login(login: str) -> dict:
    key = str(login or "").strip().casefold()
    if not key:
        return {}
    try:
        from profiles_store import load_profiles_users
        for row in load_profiles_users():
            if str(row.get("login") or "").strip().casefold() == key:
                return dict(row)
    except Exception:
        pass
    try:
        from services.profile_service import get_user
        return dict(get_user(login) or {})
    except Exception:
        return {}


def user_id_for(login: str) -> str:
    profile = _profile_for_login(login)
    return str(profile.get("user_id") or profile.get("id") or login or "").strip()


def _is_guest(login: str) -> bool:
    profile = _profile_for_login(login)
    role = str(profile.get("rola") or profile.get("role") or "").strip().casefold()
    return role == "guest" or str(login or "").strip().casefold() in {"gość", "gosc", "guest"}


def _scheduled_slot(login: str, moment: datetime, fallback: str) -> str:
    """Preferuj grafik użytkownika, dopiero potem slot przekazany przez stare GUI."""
    profile = _profile_for_login(login)
    try:
        import gui_logowanie
        resolver = getattr(gui_logowanie, "_slot_for_user", None)
        if callable(resolver):
            value = resolver(profile, moment)
            if value in VALID_SLOTS:
                return value
    except Exception:
        pass
    return fallback if fallback in VALID_SLOTS else RANO


def _record(date_ymd: str, slot: str, login: str, *, create: bool = False) -> tuple[dict, dict, dict]:
    doc = _read(data_path(), {})
    if not isinstance(doc, dict):
        doc = {}
    day = doc.setdefault(date_ymd, {}) if create else doc.get(date_ymd, {})
    if not isinstance(day, dict):
        day = {}
        if create:
            doc[date_ymd] = day
    slot_map = day.setdefault(slot, {}) if create else day.get(slot, {})
    if not isinstance(slot_map, dict):
        slot_map = {}
        if create:
            day[slot] = slot_map
    key = str(login or "").strip().casefold()
    rec = slot_map.setdefault(key, {}) if create else slot_map.get(key, {})
    if not isinstance(rec, dict):
        rec = {}
        if create:
            slot_map[key] = rec
    return doc, slot_map, rec


def _audit(*, action: str, login: str, date_ymd: str, slot: str, actor: str, before: dict, after: dict, note: str = "") -> None:
    rows = _read(audit_path(), [])
    if not isinstance(rows, list):
        rows = []
    rows.append({
        "ts": _now_iso(),
        "action": action,
        "user_id": user_id_for(login),
        "login_snapshot": str(login or ""),
        "date": date_ymd,
        "slot": slot,
        "actor": str(actor or ""),
        "before": before,
        "after": after,
        "note": str(note or "").strip(),
    })
    if len(rows) > 5000:
        rows = rows[-5000:]
    _write(audit_path(), rows)


def classify_login(slot: str, moment: datetime, *, saturday: bool = False) -> str:
    if saturday:
        return STATUS_SATURDAY
    rules = SHIFT_RULES.get(slot) or SHIFT_RULES[RANO]
    t = moment.time().replace(second=0, microsecond=0)
    if rules["early_from"] <= t < rules["auto_until"]:
        return STATUS_PRESENT
    return STATUS_PENDING_LATE


def mark_login(date_ymd: str, slot: str, login: str, ts_iso: str) -> None:
    """Kompatybilny zamiennik attendance_utils.mark_login."""
    login_n = str(login or "").strip().casefold()
    if not login_n or _is_guest(login_n):
        return
    moment = _parse_dt(ts_iso) or datetime.now()
    resolved_slot = _scheduled_slot(login_n, moment, slot)
    doc, _slot_map, rec = _record(date_ymd, resolved_slot, login_n, create=True)
    before = dict(rec)

    # Nie nadpisuj pierwszego logowania. Stare pole logged_ts zachowujemy jako alias.
    first = str(rec.get("first_login_ts") or rec.get("logged_ts") or "").strip()
    if not first:
        first = str(ts_iso or moment.isoformat(timespec="seconds"))
    rec["first_login_ts"] = first
    rec["logged_ts"] = first
    rec["last_login_ts"] = str(ts_iso or moment.isoformat(timespec="seconds"))
    rec["login_count"] = int(rec.get("login_count") or 0) + 1
    rec["planned"] = bool(rec.get("planned", True))
    rec["user_id"] = user_id_for(login_n)
    rec["login_snapshot"] = login_n
    rec["reason"] = str(rec.get("reason") or "")

    is_saturday = moment.date().weekday() == 5
    status = classify_login(resolved_slot, moment, saturday=is_saturday)
    if rec.get("reason"):
        status = STATUS_EXCUSED

    if status == STATUS_PRESENT:
        rec["status"] = STATUS_PRESENT
        rec["day_value"] = float(rec.get("day_value") or 1.0)
        rec["confirmed"] = True
        rec.setdefault("confirmed_by", "AUTO")
        rec.setdefault("confirmed_ts", first)
        rec["source"] = rec.get("source") or "auto_login"
        rec["approval_required"] = False
    elif status == STATUS_SATURDAY:
        rec["status"] = STATUS_SATURDAY
        rec["day_value"] = 0.0
        rec["confirmed"] = False
        rec["approval_required"] = True
        rec["source"] = rec.get("source") or "auto_login"
        rec.setdefault("overtime", {})
        if isinstance(rec["overtime"], dict):
            rec["overtime"].update({
                "type": "sobota",
                "day_value": float(rec["overtime"].get("day_value") or 1.0),
                "hours": rec["overtime"].get("hours"),
                "status": rec["overtime"].get("status") or "pending",
                "source": rec["overtime"].get("source") or "auto_login",
            })
    else:
        # Bardzo późne logowanie: po 12:00 / po 20:00. Bez liczenia spóźnienia.
        if rec.get("status") != STATUS_PRESENT or not rec.get("confirmed"):
            rec["status"] = STATUS_PENDING_LATE
            rec["day_value"] = float(rec.get("day_value") or 0.0)
            rec["confirmed"] = False
            rec["approval_required"] = True
            rec["source"] = rec.get("source") or "auto_login"

    _write(data_path(), doc)
    if before != rec:
        _audit(
            action="login",
            login=login_n,
            date_ymd=date_ymd,
            slot=resolved_slot,
            actor="AUTO",
            before=before,
            after=dict(rec),
        )


def confirm_login(date_ymd: str, slot: str, login: str, bryg_login: str, ts_iso: str) -> None:
    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = _record(date_ymd, slot, login_n, create=True)
    before = dict(rec)
    rec["planned"] = True
    rec["status"] = STATUS_PRESENT
    rec["day_value"] = 1.0
    rec["confirmed"] = True
    rec["approval_required"] = False
    rec["confirmed_by"] = str(bryg_login or "")
    rec["confirmed_ts"] = str(ts_iso or _now_iso())
    rec["source"] = "foreman"
    rec["user_id"] = rec.get("user_id") or user_id_for(login_n)
    _write(data_path(), doc)
    _audit(action="confirm_day", login=login_n, date_ymd=date_ymd, slot=slot,
           actor=bryg_login, before=before, after=dict(rec))


def set_reason(date_ymd: str, slot: str, login: str, bryg_login: str, reason: str, ts_iso: str) -> None:
    login_n = str(login or "").strip().casefold()
    r = str(reason or "").strip().upper()
    if r == "SW":
        r = "ŚW"
    if r not in {"L4", "UR", "UŻ", "ŚW", "NN"}:
        return
    doc, _slot_map, rec = _record(date_ymd, slot, login_n, create=True)
    before = dict(rec)
    rec.update({
        "planned": True,
        "reason": r,
        "status": STATUS_EXCUSED,
        "day_value": 0.0,
        "confirmed": False,
        "approval_required": False,
        "confirmed_by": str(bryg_login or ""),
        "confirmed_ts": str(ts_iso or _now_iso()),
        "source": "foreman",
        "user_id": rec.get("user_id") or user_id_for(login_n),
    })
    _write(data_path(), doc)
    _audit(action="absence", login=login_n, date_ymd=date_ymd, slot=slot,
           actor=bryg_login, before=before, after=dict(rec), note=r)


def status_for(date_ymd: str, slot: str, login: str, shift_start: datetime,
               now: datetime, grace_hours: int = 4) -> str:
    _doc, _slot_map, rec = _record(date_ymd, slot, login, create=False)
    if rec.get("reason") or rec.get("status") == STATUS_EXCUSED:
        return "EXCUSED"
    status = str(rec.get("status") or "")
    if status == STATUS_PRESENT and rec.get("confirmed") is True:
        return "CONFIRMED"
    if status in {STATUS_PENDING_LATE, STATUS_SATURDAY} or rec.get("logged_ts"):
        return "LOGGED"
    try:
        if now >= shift_start + timedelta(hours=int(grace_hours)):
            return "OVERDUE"
    except Exception:
        pass
    return "PLANNED"


def set_manual_day(date_ymd: str, slot: str, login: str, value: float, actor: str,
                   note: str = "") -> dict:
    value = float(value)
    if value not in {0.0, 0.5, 1.0}:
        raise ValueError("Dniówka może mieć wartość 0, 0.5 albo 1.0.")
    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = _record(date_ymd, slot, login_n, create=True)
    before = dict(rec)
    rec.update({
        "planned": True,
        "status": STATUS_PRESENT if value > 0 else STATUS_MISSING,
        "day_value": value,
        "confirmed": value > 0,
        "approval_required": False,
        "confirmed_by": str(actor or ""),
        "confirmed_ts": _now_iso(),
        "source": "foreman_manual",
        "manual_note": str(note or "").strip(),
        "user_id": rec.get("user_id") or user_id_for(login_n),
    })
    _write(data_path(), doc)
    _audit(action="manual_day", login=login_n, date_ymd=date_ymd, slot=slot,
           actor=actor, before=before, after=dict(rec), note=note)
    return dict(rec)


def set_overtime(date_ymd: str, slot: str, login: str, hours: float, actor: str,
                 *, overtime_type: str = "zwykle", day_value: float | None = None,
                 note: str = "") -> dict:
    hours = max(0.0, float(hours))
    login_n = str(login or "").strip().casefold()
    doc, _slot_map, rec = _record(date_ymd, slot, login_n, create=True)
    before = dict(rec)
    overtime = dict(rec.get("overtime") or {})
    overtime.update({
        "type": str(overtime_type or "zwykle").strip().casefold(),
        "hours": hours,
        "status": "confirmed",
        "source": "foreman",
        "confirmed_by": str(actor or ""),
        "confirmed_ts": _now_iso(),
        "note": str(note or "").strip(),
    })
    if day_value is not None:
        overtime["day_value"] = float(day_value)
    elif overtime.get("type") == "sobota":
        overtime.setdefault("day_value", 1.0)
    rec["overtime"] = overtime
    rec["user_id"] = rec.get("user_id") or user_id_for(login_n)
    _write(data_path(), doc)
    _audit(action="overtime", login=login_n, date_ymd=date_ymd, slot=slot,
           actor=actor, before=before, after=dict(rec), note=note)
    return dict(rec)


def _effective_missing(rec: dict, day: date) -> bool:
    if rec.get("reason") or rec.get("logged_ts") or rec.get("first_login_ts"):
        return False
    if not rec.get("planned"):
        return False
    return day < date.today()


def summary_for_month(login: str, year: int, month: int) -> dict[str, float]:
    login_n = str(login or "").strip().casefold()
    doc = _read(data_path(), {})
    out = {
        "days": 0.0,
        "saturday_days": 0.0,
        "overtime_hours": 0.0,
        "vacation": 0.0,
        "l4": 0.0,
        "missing": 0.0,
        "pending": 0.0,
        "manual": 0.0,
    }
    prefix = f"{int(year):04d}-{int(month):02d}-"
    if not isinstance(doc, dict):
        return out
    for day_text, day_map in doc.items():
        if not str(day_text).startswith(prefix) or not isinstance(day_map, dict):
            continue
        try:
            day_obj = date.fromisoformat(str(day_text)[:10])
        except Exception:
            continue
        for slot in VALID_SLOTS:
            slot_map = day_map.get(slot)
            if not isinstance(slot_map, dict):
                continue
            rec = slot_map.get(login_n)
            if not isinstance(rec, dict):
                continue
            reason = str(rec.get("reason") or "").upper()
            if reason in {"UR", "UŻ"}:
                out["vacation"] += 1.0
            elif reason == "L4":
                out["l4"] += 1.0
            status = str(rec.get("status") or "")
            if status == STATUS_PRESENT:
                out["days"] += float(rec.get("day_value") or 0.0)
            elif status == STATUS_PENDING_LATE:
                out["pending"] += 1.0
            if _effective_missing(rec, day_obj):
                out["missing"] += 1.0
            if str(rec.get("source") or "").startswith("foreman"):
                out["manual"] += 1.0
            overtime = rec.get("overtime")
            if isinstance(overtime, dict):
                if overtime.get("status") == "confirmed":
                    out["overtime_hours"] += float(overtime.get("hours") or 0.0)
                    if str(overtime.get("type") or "").casefold() == "sobota":
                        out["saturday_days"] += float(overtime.get("day_value") or 1.0)
                elif status == STATUS_SATURDAY:
                    out["pending"] += 1.0
    return out


def month_records(login: str, year: int, month: int) -> list[dict]:
    login_n = str(login or "").strip().casefold()
    doc = _read(data_path(), {})
    prefix = f"{int(year):04d}-{int(month):02d}-"
    rows: list[dict] = []
    if not isinstance(doc, dict):
        return rows
    for day_text in sorted(doc):
        if not str(day_text).startswith(prefix):
            continue
        day_map = doc.get(day_text)
        if not isinstance(day_map, dict):
            continue
        for slot in (RANO, POPO):
            slot_map = day_map.get(slot)
            rec = slot_map.get(login_n) if isinstance(slot_map, dict) else None
            if not isinstance(rec, dict):
                continue
            row = dict(rec)
            row.update({"date": day_text, "slot": slot, "login": login_n})
            rows.append(row)
    return rows


def audit_for_login(login: str, limit: int = 200) -> list[dict]:
    key = str(login or "").strip().casefold()
    rows = _read(audit_path(), [])
    if not isinstance(rows, list):
        return []
    found = [dict(row) for row in rows if isinstance(row, dict)
             and str(row.get("login_snapshot") or "").strip().casefold() == key]
    return found[-max(1, int(limit)):]


__all__ = [
    "RANO", "POPO", "SHIFT_RULES", "STATUS_PRESENT", "STATUS_PENDING_LATE",
    "STATUS_MISSING", "STATUS_EXCUSED", "STATUS_SATURDAY", "data_path",
    "audit_path", "mark_login", "confirm_login", "set_reason", "status_for",
    "set_manual_day", "set_overtime", "summary_for_month", "month_records",
    "audit_for_login", "classify_login", "user_id_for",
]
