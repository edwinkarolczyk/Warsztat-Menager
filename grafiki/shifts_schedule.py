# Wersja pliku: 1.0.0
# Plik: grafiki/shifts_schedule.py
# Zmiany:
# - Silnik rotacji zmian A/B/C oraz API

from __future__ import annotations

import json
import os
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional

TRYBY = ["A", "B", "C"]

_DATA_DIR = os.path.join("data", "grafiki")
_MODES_FILE = os.path.join(_DATA_DIR, "tryby_userow.json")
_CONFIG_FILE = "config.json"


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
        data = {"version": "1.0.0", "anchor_monday": "2025-01-06", "modes": {}}
        _save_json(_MODES_FILE, data)
    return data


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
    try:
        import profiles

        raw = profiles.get_all_users()
        print(f"[WM-DBG][SHIFTS] users via profiles: {len(raw)}")
    except Exception:
        path = os.path.join("data", "users", "users.json")
        raw = _read_json(path) or []
        print(f"[WM-DBG][SHIFTS] users via fallback: {len(raw)}")
    users: List[Dict[str, str]] = []
    for u in raw:
        uid = str(u.get("id") or u.get("user_id") or u.get("login") or "")
        name = (
            u.get("name")
            or u.get("full_name")
            or f"{u.get('imie', '')} {u.get('nazwisko', '')}".strip()
        )
        active = bool(u.get("active", True))
        users.append({"id": uid, "name": name, "active": active})
    return users


def _user_mode(user_id: str) -> str:
    modes = _load_modes().get("modes", {})
    return modes.get(user_id, "B")


def _week_idx(day: date) -> int:
    anchor = _anchor_monday()
    monday_today = day - timedelta(days=day.weekday())
    delta = monday_today - anchor
    return delta.days // 7


def _slot_for_mode(mode: str, week_idx: int) -> str:
    if mode == "A":
        return "RANO" if week_idx % 3 in (0, 1) else "POPO"
    if mode == "B":
        return "RANO"
    if mode == "C":
        return "RANO" if week_idx % 2 == 0 else "POPO"
    return "RANO"


def who_is_on_now(now: Optional[datetime] = None) -> Dict[str, List[str]]:
    """Return the current shift slot and active user names.

    Parameters:
        now: Optional ``datetime`` representing the moment to check. If
            omitted, the current time is used.

    Returns:
        dict: Mapping with keys ``slot`` (``"RANO"``, ``"POPO"`` or ``None``)
            and ``users`` (list of user display names).
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

    Parameters:
        now: Optional ``datetime`` used to determine the current day and
            shift. Defaults to the current time.

    Returns:
        str: Formatted string describing today's date, shift label and
            participating users. When outside shift hours a default message is
            returned.
    """
    now = now or datetime.now()
    info = who_is_on_now(now)
    if info["slot"] is None:
        return "Poza godzinami zmian"
    times = _shift_times()
    if info["slot"] == "RANO":
        s = times["R_START"].strftime("%H:%M")
        e = times["R_END"].strftime("%H:%M")
        label = "Poranna"
    else:
        s = times["P_START"].strftime("%H:%M")
        e = times["P_END"].strftime("%H:%M")
        label = "Popołudniowa"
    dow_pl = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"][now.weekday()]
    names = ", ".join(info["users"]) if info["users"] else "—"
    return f"Dziś {dow_pl} {now.strftime('%d.%m.%Y')} | {label} {s}–{e} → {names}"


def week_matrix(start_date: date) -> Dict[str, List[Dict]]:
    """Build a weekly schedule matrix starting from the given date.

    Parameters:
        start_date: Date from which the week begins; any day within the week
            may be provided.

    Returns:
        dict: Structure with the ISO formatted ``week_start`` and ``rows`` for
            each active user containing shift details for every day.
    """
    week_start = start_date - timedelta(days=start_date.weekday())
    times = _shift_times()
    rows: List[Dict] = []
    widx = _week_idx(week_start)
    modes = _load_modes().get("modes", {})
    for u in _load_users():
        if not u.get("active"):
            continue
        mode = modes.get(u["id"], "B")
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

    Parameters:
        user_id: Identifier of the user whose mode will be stored.
        mode: Rotation mode, one of ``"A"``, ``"B"`` or ``"C"``.

    Returns:
        None
    """
    if mode not in TRYBY:
        raise ValueError("mode must be A, B or C")
    data = _load_modes()
    data.setdefault("modes", {})[user_id] = mode
    _save_json(_MODES_FILE, data)
    print(f"[WM-DBG][SHIFTS] mode saved: {user_id} -> {mode}")


def set_anchor_monday(iso_date: str) -> None:
    """Set the Monday used as the rotation anchor date.

    Parameters:
        iso_date: Date string in ``YYYY-MM-DD`` format representing any day of
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

# ⏹ KONIEC KODU
