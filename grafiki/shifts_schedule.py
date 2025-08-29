# Wersja pliku: 1.0.0
# Plik: grafiki/shifts_schedule.py
# Zmiany:
# - Silnik rotacji zmian A/B/C oraz API

from __future__ import annotations

import json
import os
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional

_DEFAULT_PATTERNS = {"A": "112", "B": "111", "C": "12"}

_DATA_DIR = os.path.join("data", "grafiki")
_MODES_FILE = os.path.join(_DATA_DIR, "tryby_userow.json")
_CONFIG_FILE = "config.json"
_USERS_FILE = "uzytkownicy.json"

_USER_DEFAULTS: Dict[str, str] = {}


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print("[ERROR]", e)
        return {}


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_cfg() -> dict:
    cfg = _read_json(_CONFIG_FILE)
    print(f"[WM-DBG][SHIFTS] config loaded: {cfg}")
    return cfg


def _load_modes() -> dict:
    data = _read_json(_MODES_FILE)
    if not data:
        data = {
            "version": "1.0.0",
            "anchor_monday": "2025-01-06",
            "patterns": _DEFAULT_PATTERNS.copy(),
            "modes": {},
        }
        _save_json(_MODES_FILE, data)
    if not data.get("patterns"):
        data["patterns"] = _DEFAULT_PATTERNS.copy()
    return data


def _available_patterns(data: Optional[dict] = None) -> Dict[str, str]:
    data = data or _load_modes()
    patterns = data.get("patterns", {})
    if isinstance(patterns, list):
        patterns = {p: p for p in patterns}
    if not patterns:
        patterns = _DEFAULT_PATTERNS.copy()
    return patterns

TRYBY = list(_available_patterns().keys())


def _last_update_date() -> str:
    """Return the last modification date of the modes file."""
    try:
        ts = os.path.getmtime(_MODES_FILE)
    except OSError:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def _anchor_monday() -> date:
    modes = _load_modes()
    anchor = modes.get("anchor_monday")
    if not anchor:
        cfg = _load_cfg()
        anchor = cfg.get("rotacja_anchor_monday", "2025-01-06")
    try:
        d = datetime.strptime(anchor, "%Y-%m-%d").date()
    except Exception:
        d = date(2025, 1, 6)
    d = d - timedelta(days=d.weekday())
    return d


def _parse_time(txt: str) -> time:
    return datetime.strptime(txt, "%H:%M").time()


def _shift_times() -> Dict[str, time]:
    cfg = _load_cfg()
    r_s = cfg.get("zmiana_rano_start", "06:00")
    r_e = cfg.get("zmiana_rano_end", "14:00")
    p_s = cfg.get("zmiana_pop_start", "14:00")
    p_e = cfg.get("zmiana_pop_end", "22:00")
    return {
        "R_START": _parse_time(r_s),
        "R_END": _parse_time(r_e),
        "P_START": _parse_time(p_s),
        "P_END": _parse_time(p_e),
    }


def _load_users() -> List[Dict[str, str]]:
    global _USER_DEFAULTS
    defaults_raw = _read_json(_USERS_FILE) or []
    defaults_map = {}
    for u in defaults_raw:
        uid = str(u.get("id") or u.get("user_id") or u.get("login") or "")
        defaults_map[uid] = u.get("tryb_zmian", "B")
    try:
        import profiles

        raw = profiles.get_all_users()
        print(f"[WM-DBG][SHIFTS] users via profiles: {len(raw)}")
    except Exception:
        profiles_path = os.path.join("data", "profiles.json")
        raw_dict = _read_json(profiles_path)
        if raw_dict:
            raw = [
                {"login": login, **info} for login, info in raw_dict.items()
            ]
            print(
                f"[WM-DBG][SHIFTS] users via profiles.json: {len(raw)}"
            )
        else:
            path = os.path.join("data", "users", "users.json")
            raw = _read_json(path) or defaults_raw
            print(
                f"[WM-DBG][SHIFTS] users via fallback: {len(raw)}"
            )
    users: List[Dict[str, str]] = []
    _USER_DEFAULTS = {}
    for u in raw:
        uid = str(u.get("id") or u.get("user_id") or u.get("login") or "")
        name = (
            u.get("name")
            or u.get("full_name")
            or u.get("nazwa")
            or f"{u.get('imie', '')} {u.get('nazwisko', '')}".strip()
        )
        active = bool(u.get("active", True))
        default_mode = defaults_map.get(uid, "B")
        _USER_DEFAULTS[uid] = default_mode
        users.append(
            {
                "id": uid,
                "name": name,
                "active": active,
                "tryb_zmian": default_mode,
            }
        )
    return users


def _user_mode(user_id: str) -> str:
    modes = _load_modes().get("modes", {})
    if user_id not in _USER_DEFAULTS:
        _load_users()
    return modes.get(user_id, _USER_DEFAULTS.get(user_id, "B"))


def _week_idx(day: date) -> int:
    anchor = _anchor_monday()
    monday_today = day - timedelta(days=day.weekday())
    delta = monday_today - anchor
    return delta.days // 7


def _slot_for_mode(mode: str, week_idx: int) -> str:
    patterns = _available_patterns()
    pattern = patterns.get(mode, mode)
    if not pattern:
        pattern = "1"
    idx = week_idx % len(pattern)
    digit = pattern[idx]
    return "RANO" if digit == "1" else "POPO"


def who_is_on_now(now: Optional[datetime] = None) -> Dict[str, List[str]]:
    """Return the current shift slot and active user names.

    Args:
        now (datetime, optional): Moment to check. Defaults to the current
            time.

    Returns:
        Dict[str, List[str]]: Mapping with keys ``slot`` (``"RANO"``,
        ``"POPO"`` or ``None``) and ``users`` containing display names of
        active users.
    """
    now = now or datetime.now()
    times = _shift_times()
    slot = None
    if times["R_START"] <= now.time() < times["R_END"]:
        slot = "RANO"
    elif times["P_START"] <= now.time() < times["P_END"]:
        slot = "POPO"
    if slot is None:
        return {"slot": None, "users": []}
    widx = _week_idx(now.date())
    users = [
        u["name"]
        for u in _load_users()
        if u.get("active") and _slot_for_mode(_user_mode(u["id"]), widx) == slot
    ]
    return {"slot": slot, "users": users}


def today_summary(now: Optional[datetime] = None) -> str:
    """Generate a human readable summary for today's shift.

    Args:
        now (datetime, optional): Moment used to determine the current day
            and shift. Defaults to the current time.

    Returns:
        str: Formatted text with today's date, shift label and participating
        users. When outside shift hours a default message is returned.
    """
    now = now or datetime.now()
    info = who_is_on_now(now)
    if info["slot"] is None:
        return "Poza godzinami zmian"
    last_update = _last_update_date()
    times = _shift_times()
    if info["slot"] == "RANO":
        s = times["R_START"].strftime("%H:%M")
        e = times["R_END"].strftime("%H:%M")
        label = "Poranna"
    else:
        s = times["P_START"].strftime("%H:%M")
        e = times["P_END"].strftime("%H:%M")
        label = "Popołudniowa"
    names = ", ".join(info["users"]) if info["users"] else "—"
    return f"Ostatnia aktualizacja {last_update} | {label} {s}–{e} → {names}"


def week_matrix(start_date: date) -> Dict[str, List[Dict]]:
    """Build a weekly schedule matrix starting from the given date.

    Args:
        start_date (date): Any day within the week for which the matrix
            should be produced.

    Returns:
        Dict[str, List[Dict]]: Structure containing the ISO formatted
        ``week_start`` and ``rows`` with shift details for each active user.
    """
    week_start = start_date - timedelta(days=start_date.weekday())
    times = _shift_times()
    rows: List[Dict] = []
    widx = _week_idx(week_start)
    for u in _load_users():
        if not u.get("active"):
            continue
        mode = _user_mode(u["id"])
        slot = _slot_for_mode(mode, widx)
        start = times["R_START"] if slot == "RANO" else times["P_START"]
        end = times["R_END"] if slot == "RANO" else times["P_END"]
        days = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            days.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "dow": d.strftime("%a"),
                    "shift": "R" if slot == "RANO" else "P",
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                }
            )
        rows.append(
            {
                "user": u["name"],
                "user_id": u["id"],
                "mode": mode,
                "slot": slot,
                "days": days,
            }
        )
    return {"week_start": week_start.strftime("%Y-%m-%d"), "rows": rows}


def set_user_mode(user_id: str, mode: str) -> None:
    """Persist rotation mode for a specific user.

    Args:
        user_id (str): Identifier of the user whose mode will be stored.
        mode (str): Rotation pattern identifier available in configuration.

    Returns:
        None
    """
    data = _load_modes()
    patterns = _available_patterns(data)
    if mode not in patterns:
        allowed = ", ".join(sorted(patterns))
        raise ValueError(f"mode must be one of: {allowed}")
    data.setdefault("modes", {})[user_id] = mode
    _save_json(_MODES_FILE, data)
    print(f"[WM-DBG][SHIFTS] mode saved: {user_id} -> {mode}")


def set_anchor_monday(iso_date: str) -> None:
    """Set the Monday used as the rotation anchor date.

    Args:
        iso_date (str): Date in ``YYYY-MM-DD`` format representing any day of
            the desired anchor week.

    Returns:
        None
    """
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except Exception:
        print("[ERROR] invalid date format:", iso_date)
        return
    d = d - timedelta(days=d.weekday())
    data = _load_modes()
    data["anchor_monday"] = d.isoformat()
    _save_json(_MODES_FILE, data)
    print(f"[WM-DBG][SHIFTS] anchor saved: {d.isoformat()}")


__all__ = [
    "who_is_on_now",
    "today_summary",
    "week_matrix",
    "set_user_mode",
    "set_anchor_monday",
    "TRYBY",
]

# ⏹ KONIEC KODU
