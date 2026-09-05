# version: 1.3
"""Jedno źródło prawdy dla dniówek i nadgodzin WM.

Warstwa jest zgodna z istniejącym ``attendance_utils`` i rozszerza jego
``ewidencja_obecnosci.json`` bez destrukcyjnej migracji starych rekordów.
Nowe wpisy są wiązane przede wszystkim przez trwałe ``user_id``, a
``login_snapshot`` zachowuje login użyty przy utworzeniu wpisu.

Miesięczna ewidencja jest także wyprowadzana z Grafiku. Dzięki temu
zaplanowany dzień bez żadnego rekordu logowania nie znika z raportu: po
upływie okna automatycznego staje się pozycją ``MISSING`` do decyzji.
"""
from __future__ import annotations

import json
import os
from calendar import monthrange
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

try:
    from grafiki.shifts_schedule import _shift_times as _grafik_shift_times
except Exception:  # pragma: no cover
    _grafik_shift_times = None

RANO = "RANO"
POPO = "POPO"
VALID_SLOTS = {RANO, POPO}

STATUS_PRESENT = "PRESENT"
STATUS_PENDING_LATE = "PENDING_LATE"
STATUS_MISSING = "MISSING"
STATUS_EXCUSED = "EXCUSED"
STATUS_SATURDAY = "OVERTIME_SATURDAY"
STATUS_PLANNED = "PLANNED"


def _move_time(value: time, delta: timedelta) -> time:
    """Przesuń godzinę z poprawnym zawinięciem doby."""
    base = datetime.combine(date(2000, 1, 1), value) + delta
    return base.time().replace(second=0, microsecond=0)


def _shift_rules() -> dict[str, dict[str, time]]:
    """Buduj okna obecności z tego samego źródła godzin co Grafik."""
    try:
        if _grafik_shift_times is None:
            raise RuntimeError("Brak resolvera godzin Grafiku")
        (rano_start, rano_end), (popo_start, popo_end) = _grafik_shift_times()
    except Exception:
        rano_start, rano_end = time(6, 0), time(14, 0)
        popo_start, popo_end = time(14, 0), time(22, 0)
    return {
        RANO: {
            "shift_start": rano_start,
            "shift_end": rano_end,
            "early_from": _move_time(rano_start, timedelta(hours=-1)),
            "auto_until": _move_time(rano_end, timedelta(hours=-2)),
        },
        POPO: {
            "shift_start": popo_start,
            "shift_end": popo_end,
            "early_from": _move_time(popo_start, timedelta(hours=-1)),
            "auto_until": _move_time(popo_end, timedelta(hours=-2)),
        },
    }


# Zachowane dla zgodności importów starszych runtime'ów. Logika serwisu pobiera
# świeże wartości przez _shift_rules(), więc zmiana konfiguracji nie wymaga restartu.
SHIFT_RULES = _shift_rules()


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


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
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


def _is_employed_on(profile: dict, day: date) -> bool:
    active_from = _parse_date(profile.get("zatrudniony_od"))
    active_to = _parse_date(profile.get("zatrudniony_do"))
    if active_from and day < active_from:
        return False
    if active_to and day > active_to:
        return False
    return True


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


def _planned_slot_for_day(login: str, day: date) -> str | None:
    """Zwróć zmianę zaplanowaną w kanonicznym Grafiku albo ``None``."""
    if _is_guest(login):
        return None
    profile = _profile_for_login(login)
    if not profile or not _is_employed_on(profile, day):
        return None
    moment = datetime.combine(day, time(12, 0))
    try:
        import gui_logowanie
        resolver = getattr(gui_logowanie, "_slot_for_user", None)
        if callable(resolver):
            value = resolver(profile, moment)
            if value in VALID_SLOTS:
                return value
            if value is None:
                return None
    except Exception:
        pass

    raw_days = profile.get("workdays")
    if raw_days is None:
        raw_days = profile.get("dni_pracy")
    try:
        workdays = {int(item) for item in (raw_days or [0, 1, 2, 3, 4])}
    except Exception:
        workdays = {0, 1, 2, 3, 4}
    if day.weekday() not in workdays:
        return None

    mode = str(
        profile.get("tryb_zmian")
        or profile.get("shift_mode")
        or profile.get("zmiana")
        or "111"
    ).strip()
    first = "2" if mode.startswith("2") else "1"
    return POPO if first == "2" else RANO


def _matching_record(slot_map: dict, login: str) -> tuple[str, dict] | tuple[None, None]:
    """Najpierw szukaj po user_id, potem po historycznym loginie."""
    login_key = str(login or "").strip().casefold()
    user_id = user_id_for(login)
    user_key = str(user_id or "").strip().casefold()

    if user_key:
        direct = slot_map.get(user_id)
        if isinstance(direct, dict):
            return str(user_id), direct
        direct = slot_map.get(user_key)
        if isinstance(direct, dict):
            return user_key, direct
        for storage_key, candidate in slot_map.items():
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("user_id") or "").strip().casefold() == user_key:
                return str(storage_key), candidate

    if login_key:
        direct = slot_map.get(login_key)
        if isinstance(direct, dict):
            return login_key, direct
        for storage_key, candidate in slot_map.items():
            if not isinstance(candidate, dict):
                continue
            snapshot = str(candidate.get("login_snapshot") or candidate.get("login") or "").strip().casefold()
            if snapshot == login_key or str(storage_key).strip().casefold() == login_key:
                return str(storage_key), candidate
    return None, None


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

    _storage_key, rec = _matching_record(slot_map, login)
    if not isinstance(rec, dict):
        rec = {}
        if create:
            uid = user_id_for(login)
            storage_key = str(uid or login or "").strip()
            if not storage_key:
                storage_key = str(login or "").strip().casefold()
            rec = slot_map.setdefault(storage_key, {})

    if create:
        uid = user_id_for(login)
        if uid:
            rec.setdefault("user_id", uid)
        rec.setdefault("login_snapshot", str(login or "").strip().casefold())
    return doc, slot_map, rec


def _absence_label(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"SW", "ŚW", "SILA_WYZSZA", "SIŁA_WYŻSZA", "SILA WYZSZA", "SIŁA WYŻSZA"}:
        return "ŚW"
    if raw == "URLOP":
        return "UR"
    return raw


def absence_conflict(date_ymd: str, login: str) -> dict:
    """Zwróć nieobecność, która faktycznie blokuje zapis dniówki dla wskazanego dnia."""
    reasons: list[str] = []
    reason_slot = ""
    doc = _read(data_path(), {})
    day = doc.get(str(date_ymd), {}) if isinstance(doc, dict) else {}
    if isinstance(day, dict):
        for slot in (RANO, POPO):
            slot_map = day.get(slot)
            if not isinstance(slot_map, dict):
                continue
            _storage_key, rec = _matching_record(slot_map, login)
            if not isinstance(rec, dict):
                continue
            reason = _absence_label(rec.get("reason"))
            if reason:
                reasons.append(reason)
                reason_slot = reason_slot or slot

    leave_types: list[str] = []
    try:
        from services import leave_workflow_service
        for row in leave_workflow_service.active_absences_for_day(login, str(date_ymd)):
            kind = _absence_label(row.get("type"))
            # Siła wyższa z kanonicznej ewidencji może współistnieć z obecnością.
            # Wpisana bezpośrednio jako reason w obecności nadal blokuje nadpisanie.
            if kind and kind != "ŚW":
                leave_types.append(kind)
    except Exception:
        pass

    labels: list[str] = []
    for value in [*reasons, *leave_types]:
        if value and value not in labels:
            labels.append(value)
    return {"has_conflict": bool(labels), "reasons": labels, "slot": reason_slot}


def _audit(*, action: str, login: str, date_ymd: str, slot: str, actor: str,
           before: dict, after: dict, note: str = "") -> None:
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
    _write(audit_path(), rows)


def classify_login(slot: str, moment: datetime, *, saturday: bool = False) -> str:
    if saturday:
        return STATUS_SATURDAY
    rules_map = _shift_rules()
    rules = rules_map.get(slot) or rules_map[RANO]
    t = moment.time().replace(second=0, microsecond=0)
    if rules["early_from"] <= t <= rules["auto_until"]:
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

    first = str(rec.get("first_login_ts") or rec.get("logged_ts") or "").strip()
    if not first:
        first = str(ts_iso or moment.isoformat(timespec="seconds"))
    rec["first_login_ts"] = first
    rec["logged_ts"] = first
    rec["last_login_ts"] = str(ts_iso or moment.isoformat(timespec="seconds"))
    rec["login_count"] = int(rec.get("login_count") or 0) + 1
    rec["planned"] = bool(rec.get("planned", True))
    rec["user_id"] = rec.get("user_id") or user_id_for(login_n)
    rec.setdefault("login_snapshot", login_n)
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
    rec.setdefault("login_snapshot", login_n)
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
    rec.setdefault("login_snapshot", login_n)
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
                   note: str = "", *, replace_absence: bool = False) -> dict:
    value = float(value)
    if value not in {0.0, 0.5, 1.0}:
        raise ValueError("Dniówka może mieć wartość 0, 0.5 albo 1.0.")
    login_n = str(login or "").strip().casefold()
    conflict = absence_conflict(date_ymd, login_n)
    conflict_slot = str(conflict.get("slot") or "")
    if conflict.get("has_conflict"):
        if conflict_slot and conflict_slot != slot:
            raise ValueError(
                f"Nieobecność jest zapisana na zmianie {conflict_slot}. "
                "Korektę wykonaj dla tej samej zmiany."
            )
        if not replace_absence:
            labels = ", ".join(conflict.get("reasons") or []) or "nieobecność"
            raise ValueError(
                f"Dzień ma wpis {labels}. Najpierw potwierdź zastąpienie nieobecności korektą."
            )

    doc, _slot_map, rec = _record(date_ymd, slot, login_n, create=True)
    before = dict(rec)
    rec.update({
        "planned": True,
        "reason": "" if replace_absence else str(rec.get("reason") or ""),
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
    rec.setdefault("login_snapshot", login_n)
    _write(data_path(), doc)

    if replace_absence:
        try:
            from services import leave_workflow_service
            leave_workflow_service.cancel_absences_for_day(login_n, date_ymd, actor, note)
        except Exception:
            rec.clear()
            rec.update(before)
            _write(data_path(), doc)
            raise

    action = "manual_day_replace_absence" if conflict.get("has_conflict") else "manual_day"
    audit_note = str(note or "").strip()
    if conflict.get("has_conflict"):
        labels = ", ".join(conflict.get("reasons") or [])
        audit_note = f"Zastąpiono {labels}. {audit_note}".strip()
    _audit(action=action, login=login_n, date_ymd=date_ymd, slot=slot,
           actor=actor, before=before, after=dict(rec), note=audit_note)
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
    rec["approval_required"] = False
    rec["user_id"] = rec.get("user_id") or user_id_for(login_n)
    rec.setdefault("login_snapshot", login_n)
    _write(data_path(), doc)
    _audit(action="overtime", login=login_n, date_ymd=date_ymd, slot=slot,
           actor=actor, before=before, after=dict(rec), note=note)
    return dict(rec)


def _decision_due(day_obj: date, slot: str, now: datetime) -> bool:
    if day_obj < now.date():
        return True
    if day_obj > now.date():
        return False
    rules_map = _shift_rules()
    rules = rules_map.get(slot) or rules_map[RANO]
    current = now.time().replace(second=0, microsecond=0)
    return current > rules["auto_until"]


def _actual_month_records(login: str, year: int, month: int) -> list[dict]:
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
            if not isinstance(slot_map, dict):
                continue
            _storage_key, rec = _matching_record(slot_map, login_n)
            if not isinstance(rec, dict):
                continue
            row = dict(rec)
            row.update({"date": str(day_text)[:10], "slot": slot, "login": login_n, "synthetic": False})
            rows.append(row)
    return rows


def month_records(login: str, year: int, month: int, *, now: datetime | None = None) -> list[dict]:
    """Zwróć rzeczywiste rekordy oraz brakujące dni wyprowadzone z Grafiku."""
    now = now or datetime.now()
    login_n = str(login or "").strip().casefold()
    actual = _actual_month_records(login_n, year, month)
    rows = [dict(row) for row in actual]

    actual_days = {str(row.get("date") or "") for row in actual}
    _last_day = monthrange(int(year), int(month))[1]
    month_start = date(int(year), int(month), 1)
    month_end = date(int(year), int(month), _last_day)
    synth_end = min(month_end, now.date())
    if synth_end >= month_start:
        current = month_start
        while current <= synth_end:
            day_text = current.isoformat()
            if day_text not in actual_days:
                slot = _planned_slot_for_day(login_n, current)
                if slot in VALID_SLOTS:
                    due = _decision_due(current, slot, now)
                    rows.append({
                        "date": day_text,
                        "slot": slot,
                        "login": login_n,
                        "user_id": user_id_for(login_n),
                        "login_snapshot": login_n,
                        "planned": True,
                        "status": STATUS_MISSING if due else STATUS_PLANNED,
                        "day_value": 0.0,
                        "confirmed": False,
                        "approval_required": bool(due),
                        "source": "schedule",
                        "reason": "",
                        "first_login_ts": "",
                        "logged_ts": "",
                        "synthetic": True,
                    })
            current += timedelta(days=1)

    normalized: list[dict] = []
    for row in rows:
        item = dict(row)
        day_obj = _parse_date(item.get("date"))
        slot = str(item.get("slot") or RANO)
        has_login = bool(str(item.get("first_login_ts") or item.get("logged_ts") or "").strip())
        reason = str(item.get("reason") or "").strip()
        status = str(item.get("status") or "")
        if (
            day_obj
            and item.get("planned")
            and not has_login
            and not reason
            and status not in {STATUS_PRESENT, STATUS_EXCUSED}
            and _decision_due(day_obj, slot, now)
            and item.get("approval_required") is not False
        ):
            item["status"] = STATUS_MISSING
            item["approval_required"] = True
        elif not status and item.get("planned"):
            item["status"] = STATUS_PLANNED
        normalized.append(item)

    normalized.sort(key=lambda row: (str(row.get("date") or ""), 0 if row.get("slot") == RANO else 1))
    return normalized


def decision_records(login: str, year: int, month: int, *, now: datetime | None = None) -> list[dict]:
    """Pozycje, dla których Brygadzista ma podjąć decyzję."""
    now = now or datetime.now()
    out: list[dict] = []
    for row in month_records(login, year, month, now=now):
        if row.get("reason") or str(row.get("status") or "") == STATUS_EXCUSED:
            continue
        if row.get("approval_required") is False:
            continue
        status = str(row.get("status") or "")
        if status not in {STATUS_PENDING_LATE, STATUS_SATURDAY, STATUS_MISSING}:
            continue
        item = dict(row)
        if status == STATUS_MISSING:
            item["decision_label"] = "Brak logowania"
        elif status == STATUS_SATURDAY:
            item["decision_label"] = "Sobota — potwierdź"
        else:
            item["decision_label"] = "Logowanie po oknie — decyzja"
        out.append(item)
    return out


def summary_for_month(login: str, year: int, month: int, *, now: datetime | None = None) -> dict[str, float]:
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
    for rec in month_records(login, year, month, now=now):
        reason = str(rec.get("reason") or "").upper()
        if reason in {"UR", "UŻ"}:
            out["vacation"] += 1.0
        elif reason == "L4":
            out["l4"] += 1.0

        status = str(rec.get("status") or "")
        if status == STATUS_PRESENT:
            out["days"] += float(rec.get("day_value") or 0.0)
        elif status == STATUS_MISSING:
            out["missing"] += 1.0
            if rec.get("approval_required"):
                out["pending"] += 1.0
        elif status == STATUS_PENDING_LATE:
            out["pending"] += 1.0
        elif status == STATUS_SATURDAY and rec.get("approval_required"):
            out["pending"] += 1.0

        if str(rec.get("source") or "").startswith("foreman"):
            out["manual"] += 1.0

        overtime = rec.get("overtime")
        if isinstance(overtime, dict) and overtime.get("status") == "confirmed":
            out["overtime_hours"] += float(overtime.get("hours") or 0.0)
            if str(overtime.get("type") or "").casefold() == "sobota":
                out["saturday_days"] += float(overtime.get("day_value") or 1.0)
    return out


def audit_for_login(login: str, limit: int = 200) -> list[dict]:
    key = str(login or "").strip().casefold()
    uid = str(user_id_for(login) or "").strip().casefold()
    rows = _read(audit_path(), [])
    if not isinstance(rows, list):
        return []
    found = [
        dict(row)
        for row in rows
        if isinstance(row, dict)
        and (
            (uid and str(row.get("user_id") or "").strip().casefold() == uid)
            or str(row.get("login_snapshot") or "").strip().casefold() == key
        )
    ]
    return found[-max(1, int(limit)):]


__all__ = [
    "RANO", "POPO", "SHIFT_RULES", "STATUS_PRESENT", "STATUS_PENDING_LATE",
    "STATUS_MISSING", "STATUS_EXCUSED", "STATUS_SATURDAY", "STATUS_PLANNED",
    "data_path", "audit_path", "mark_login", "confirm_login", "set_reason",
    "status_for", "set_manual_day", "set_overtime", "summary_for_month",
    "month_records", "decision_records", "audit_for_login", "classify_login",
    "user_id_for", "absence_conflict",
]
