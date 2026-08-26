# version: 1.1
# Plik: grafiki/shifts_schedule.py
# Zmiany 1.1:
# - Tryby 121 i 212 przełączają zmianę naprzemiennie co tydzień; 111 i 222 pozostają stałe.
# Zmiany:
# - Silnik rotacji zmian oraz API

from __future__ import annotations

import json
import os
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config.paths import p_config, p_profiles, p_users
from config_manager import ConfigManager
from profile_utils import ensure_profiles_file

_DEFAULT_PATTERNS = {
    "112": "112",
    "111": "111",
    "222": "222",
    "12": "12",
    "121": "121",
    "212": "212",
    "211": "211",
    "1212": "1212",
}


def _default_users_file() -> str:
    try:
        cfg = ConfigManager()
        path = p_users(cfg)
    except Exception:
        path = Path(__file__).resolve().parent / "uzytkownicy.json"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return str(path)


_USERS_FILE = _default_users_file()

_USER_DEFAULTS: Dict[str, str] = {}
_LAST_USERS_SRC: Optional[str] = None
_LAST_USERS_COUNT: Optional[int] = None


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print("[ERROR]", e)
        return {}


def _load_modes() -> dict:
    cfg = ConfigManager()
    data = {
        "anchor_monday": cfg.get("shifts.anchor_monday", "2025-01-06"),
        "patterns": cfg.get("shifts.patterns", _DEFAULT_PATTERNS.copy()),
        "modes": cfg.get("shifts.modes", {}),
    }
    if not data["patterns"]:
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
    """Return the last modification date of the configuration file."""
    try:
        cfg = ConfigManager()
        path = p_config(cfg)
    except Exception:
        path = Path("config.json").resolve()
    try:
        ts = path.stat().st_mtime
    except OSError:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def _anchor_monday() -> date:
    modes = _load_modes()
    anchor = modes.get("anchor_monday")
    if not anchor:
        cfg = ConfigManager()
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
    cfg = ConfigManager()
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


def _log_user_count(src: str, users: List[Dict[str, str]]) -> None:
    """Log user count only when source or count changes."""

    global _LAST_USERS_SRC, _LAST_USERS_COUNT
    count = len(users)
    if src != _LAST_USERS_SRC or count != _LAST_USERS_COUNT:
        _LAST_USERS_SRC, _LAST_USERS_COUNT = src, count


def _load_users() -> List[Dict[str, str]]:
    global _USER_DEFAULTS
    defaults_raw = _read_json(_USERS_FILE) or []
    defaults_map: Dict[str, str] = {}
    for u in defaults_raw:
        uid = str(u.get("id") or u.get("user_id") or u.get("login") or "")
        defaults_map[uid] = u.get("tryb_zmian", "111")
    try:  # pragma: no cover - profiles module rarely available
        import profiles

        raw = profiles.get_all_users()
        _log_user_count("profiles", raw)
    except Exception:
        raw: list[Dict[str, str]] = []
        raw_dict: Dict[str, Dict[str, str]] | None = None
        active_source: str | None = None
        try:
            cfg = ConfigManager()
            profile_path = ensure_profiles_file(cfg)
            data = _read_json(profile_path)
            if isinstance(data, dict):
                users_payload = data.get("users", [])
                users_list = users_payload if isinstance(users_payload, list) else []
                _log_user_count(profile_path, users_list)
                raw_dict = data
                active_source = profile_path
            elif isinstance(data, list):
                _log_user_count(profile_path, data)
                raw = data
                active_source = profile_path
        except Exception:
            raw = []
            raw_dict = None
            active_source = None

        if raw_dict is None and not raw:
            candidates = []
            try:
                cfg = ConfigManager()
                candidates.append(str(p_profiles(cfg)))
                candidates.append(str(p_users(cfg)))
            except Exception:
                pass
            candidates.append(_USERS_FILE)

            for profile_candidate in candidates:
                profile_candidate = str(profile_candidate or "").strip()
                if not profile_candidate:
                    continue
                data = _read_json(profile_candidate)
                if data and isinstance(data, dict):
                    _log_user_count(profile_candidate, data.get("users", []))
                    raw_dict = data
                    active_source = profile_candidate
                    break
                if data:
                    _log_user_count(profile_candidate, data)
                    raw = data  # prawdopodobnie users.json
                    active_source = profile_candidate
                    break

        if raw_dict:
            normalized: List[Dict[str, str]] = []
            for login, info in raw_dict.items():
                entry: Dict[str, str] = {"login": str(login)}
                if isinstance(info, dict):
                    entry.update(info)
                elif isinstance(info, list):
                    primary = info[0] if info else {}
                    if isinstance(primary, dict):
                        entry.update(primary)
                    elif isinstance(primary, str):
                        entry["name"] = primary
                    else:
                        entry["name"] = str(primary)
                elif isinstance(info, str):
                    entry["name"] = info
                elif info is not None:
                    entry["name"] = str(info)
                normalized.append(entry)
            raw = normalized
            source_path = active_source or "profiles.json"
            try:
                source_path = str(Path(source_path).resolve())
            except Exception:
                pass
            _log_user_count(source_path, raw)
        elif raw:
            normalized = []
            for item in raw:
                if isinstance(item, dict):
                    normalized.append(item)
                elif isinstance(item, str):
                    normalized.append({"login": item, "name": item})
                else:
                    normalized.append({"login": str(item), "name": str(item)})
            raw = normalized
            _log_user_count("fallback", raw)
        else:
            raw = defaults_raw
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
        default_mode = defaults_map.get(uid, "111")
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
    return modes.get(user_id, _USER_DEFAULTS.get(user_id, "111"))


def _week_idx(day: date) -> int:
    anchor = _anchor_monday()
    monday_today = day - timedelta(days=day.weekday())
    delta = monday_today - anchor
    return delta.days // 7


def _slot_for_mode(mode: str, week_idx: int) -> str:
    patterns = _available_patterns()
    pattern = patterns.get(mode, mode)
    digits = [c for c in str(pattern or "1") if c in ("1", "2")]
    if not digits:
        digits = ["1"]

    normalized_mode = "".join(digits)
    if normalized_mode in {"111", "222"}:
        digit = normalized_mode[0]
    elif normalized_mode in {"121", "212"}:
        first = normalized_mode[0]
        digit = first if week_idx % 2 == 0 else ("2" if first == "1" else "1")
    else:
        digit = digits[week_idx % len(digits)]
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
        days = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            wd = d.weekday()
            if wd == 6:
                continue
            if wd == 5:
                shift = "R"
                start = times["R_START"]
                end = times["R_END"]
            else:
                shift = "R" if slot == "RANO" else "P"
                start = times["R_START"] if shift == "R" else times["P_START"]
                end = times["R_END"] if shift == "R" else times["P_END"]
            days.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "dow": d.strftime("%a"),
                    "shift": shift,
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
    modes = data.get("modes", {})
    modes[user_id] = mode
    cfg = ConfigManager()
    cfg.set("shifts.modes", modes)
    cfg.save_all()
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
    except ValueError as exc:
        raise ValueError(f"invalid date format: {iso_date}") from exc

    monday = d - timedelta(days=d.weekday())
    today = date.today()
    if monday < today:
        raise ValueError("anchor date cannot be in the past")
    if monday > today + timedelta(days=365):
        raise ValueError("anchor date is too far in the future")

    cfg = ConfigManager()
    cfg.set("shifts.anchor_monday", monday.isoformat())
    cfg.save_all()
    print(f"[WM-DBG][SHIFTS] anchor saved: {monday.isoformat()}")


__all__ = [
    "who_is_on_now",
    "today_summary",
    "week_matrix",
    "set_user_mode",
    "set_anchor_monday",
    "TRYBY",
]

# ⏹ KONIEC KODU
