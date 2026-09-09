# version: 1.3
# Plik: grafiki/shifts_schedule.py
# Zmiany 1.2:
# - Kanoniczne wzorce grafiku: 111, 112, 121, 212, 222.
# - 121/212 są literalnym cyklem trzytygodniowym.
# - Każdy pracownik ma własną datę kotwiczną tygodnia 1.
# - Konfiguracja grafiku jest wiązana z trwałym user_id z fallbackiem do loginu.
"""Silnik grafiku zmian Warsztat Menager."""

from __future__ import annotations

import json
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from config.paths import p_config, p_profiles, p_users
from config_manager import ConfigManager
from profile_utils import ensure_profiles_file

_DEFAULT_PATTERNS = {
    "111": "111",
    "112": "112",
    "222": "222",
    "121": "121",
    "212": "212",
}

_LEGACY_MODE_ALIASES = {
    "1111": "111",
    "2222": "222",
    "1212": "121",
    "2121": "212",
    "I": "111",
    "1": "111",
    "II": "222",
    "2": "222",
}


def _normalize_mode(value: object, *, fallback: str = "111") -> str:
    raw = str(value or "").strip().upper()
    raw = _LEGACY_MODE_ALIASES.get(raw, raw)
    if raw in _DEFAULT_PATTERNS:
        return raw
    return fallback if fallback in _DEFAULT_PATTERNS else "111"


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
    except Exception as exc:
        print("[ERROR]", exc)
        return {}


def _load_modes() -> dict:
    cfg = ConfigManager()
    raw_modes = cfg.get("shifts.modes", {})
    raw_anchors = cfg.get("shifts.user_anchor", {})
    return {
        "anchor_monday": cfg.get("shifts.anchor_monday", "2025-01-06"),
        "patterns": _DEFAULT_PATTERNS.copy(),
        "modes": dict(raw_modes) if isinstance(raw_modes, dict) else {},
        "user_anchor": dict(raw_anchors) if isinstance(raw_anchors, dict) else {},
    }


def _available_patterns(data: Optional[dict] = None) -> Dict[str, str]:
    """Zwróć kanoniczne wzorce grafiku WM.

    Stare/customowe wpisy w config nie rozszerzają semantyki grafiku.
    """
    return _DEFAULT_PATTERNS.copy()


TRYBY = list(_DEFAULT_PATTERNS)


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


def _normalize_monday(value: object, *, fallback: date | None = None) -> date:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        raw = str(value or "").strip()
        try:
            parsed = date.fromisoformat(raw[:10])
        except Exception:
            parsed = fallback or date(2025, 1, 6)
    return parsed - timedelta(days=parsed.weekday())


def _anchor_monday() -> date:
    modes = _load_modes()
    anchor = modes.get("anchor_monday")
    if not anchor:
        try:
            anchor = ConfigManager().get("rotacja_anchor_monday", "2025-01-06")
        except Exception:
            anchor = "2025-01-06"
    return _normalize_monday(anchor, fallback=date(2025, 1, 6))


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
    global _LAST_USERS_SRC, _LAST_USERS_COUNT
    count = len(users)
    if src != _LAST_USERS_SRC or count != _LAST_USERS_COUNT:
        _LAST_USERS_SRC, _LAST_USERS_COUNT = src, count


def _load_users() -> List[Dict[str, str]]:
    """Wczytaj aktywne dane profili potrzebne do grafiku.

    ``id`` jest stabilnym user_id, a ``login`` pozostaje aliasem migracyjnym.
    """
    global _USER_DEFAULTS
    defaults_raw = _read_json(_USERS_FILE) or []
    if isinstance(defaults_raw, dict):
        defaults_raw = defaults_raw.get("users", []) if isinstance(defaults_raw.get("users"), list) else []
    defaults_map: Dict[str, str] = {}
    for raw_user in defaults_raw if isinstance(defaults_raw, list) else []:
        if not isinstance(raw_user, dict):
            continue
        uid = str(raw_user.get("user_id") or raw_user.get("id") or raw_user.get("login") or "").strip()
        login = str(raw_user.get("login") or "").strip()
        mode = _normalize_mode(raw_user.get("tryb_zmian") or raw_user.get("zmiana_plan") or "111")
        if uid:
            defaults_map[uid] = mode
        if login:
            defaults_map[login] = mode

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
                users_payload = data.get("users")
                if isinstance(users_payload, list):
                    raw = users_payload
                    _log_user_count(profile_path, raw)
                else:
                    raw_dict = data
                    _log_user_count(profile_path, list(raw_dict.values()))
                active_source = profile_path
            elif isinstance(data, list):
                raw = data
                _log_user_count(profile_path, data)
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
                if isinstance(data, dict) and data:
                    users_payload = data.get("users")
                    if isinstance(users_payload, list):
                        raw = users_payload
                    else:
                        raw_dict = data
                    active_source = profile_candidate
                    break
                if isinstance(data, list) and data:
                    raw = data
                    active_source = profile_candidate
                    break

        if raw_dict:
            normalized: List[Dict[str, str]] = []
            for login, info in raw_dict.items():
                if login in {"users", "profiles", "uzytkownicy"} and isinstance(info, list):
                    for item in info:
                        if isinstance(item, dict):
                            normalized.append(dict(item))
                    continue
                entry: Dict[str, str] = {"login": str(login)}
                if isinstance(info, dict):
                    entry.update(info)
                elif isinstance(info, list):
                    primary = info[0] if info else {}
                    if isinstance(primary, dict):
                        entry.update(primary)
                    elif isinstance(primary, str):
                        entry["name"] = primary
                    elif primary is not None:
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
            _log_user_count(active_source or "fallback", raw)
        else:
            raw = defaults_raw if isinstance(defaults_raw, list) else []

    users: List[Dict[str, str]] = []
    _USER_DEFAULTS = {}
    for user in raw:
        if not isinstance(user, dict):
            continue
        login = str(user.get("login") or "").strip()
        uid = str(user.get("user_id") or user.get("id") or login).strip()
        if not uid:
            continue
        name = (
            user.get("name")
            or user.get("display_name")
            or user.get("full_name")
            or user.get("nazwa")
            or f"{user.get('imie', '')} {user.get('nazwisko', '')}".strip()
            or login
            or uid
        )
        active = bool(user.get("active", True))
        status = str(user.get("status") or "").strip().casefold()
        if status in {"nieaktywny", "zablokowany", "dezaktywowany"}:
            active = False
        default_mode = _normalize_mode(
            user.get("tryb_zmian")
            or user.get("zmiana_plan")
            or defaults_map.get(uid)
            or defaults_map.get(login)
            or "111"
        )
        _USER_DEFAULTS[uid] = default_mode
        if login:
            _USER_DEFAULTS[login] = default_mode
        users.append(
            {
                "id": uid,
                "login": login,
                "name": str(name),
                "active": active,
                "tryb_zmian": default_mode,
                "rotacja_start": str(user.get("rotacja_start") or user.get("shift_start") or "").strip(),
            }
        )
    return users


def _find_user(user_id_or_login: str) -> dict | None:
    wanted = str(user_id_or_login or "").strip().casefold()
    if not wanted:
        return None
    for user in _load_users():
        if str(user.get("id") or "").strip().casefold() == wanted:
            return user
        if str(user.get("login") or "").strip().casefold() == wanted:
            return user
    return None


def get_user_schedule(user_id: str, fallback_mode: str = "") -> tuple[str, str]:
    """Zwróć kanoniczny tryb i poniedziałek tygodnia 1 dla pracownika."""
    key = str(user_id or "").strip()
    user = _find_user(key)
    stable_id = str((user or {}).get("id") or key).strip()
    login = str((user or {}).get("login") or "").strip()

    data = _load_modes()
    modes = data.get("modes") if isinstance(data.get("modes"), dict) else {}
    anchors = data.get("user_anchor") if isinstance(data.get("user_anchor"), dict) else {}

    raw_mode = (
        modes.get(stable_id)
        or (modes.get(login) if login else None)
        or fallback_mode
        or (user or {}).get("tryb_zmian")
        or _USER_DEFAULTS.get(stable_id)
        or (_USER_DEFAULTS.get(login) if login else None)
        or "111"
    )
    mode = _normalize_mode(raw_mode)

    # Grafik pracownika nie korzysta już z globalnej kotwicy.
    # Stary shifts.anchor_monday pozostaje wyłącznie zgodnością danych i nie steruje grafikiem.
    raw_anchor = (
        anchors.get(stable_id)
        or (anchors.get(login) if login else None)
        or (user or {}).get("rotacja_start")
        or "2025-01-06"
    )
    anchor = _normalize_monday(raw_anchor, fallback=date(2025, 1, 6))
    return mode, anchor.isoformat()


def set_user_schedule(user_id: str, mode: str, anchor_date: str | date) -> None:
    """Zapisz wzorzec i indywidualną datę kotwiczną pod trwałym user_id."""
    key = str(user_id or "").strip()
    if not key:
        raise ValueError("user_id is required")
    raw_mode = str(mode or "").strip().upper()
    canonical = _LEGACY_MODE_ALIASES.get(raw_mode, raw_mode)
    if canonical not in _DEFAULT_PATTERNS:
        allowed = ", ".join(_DEFAULT_PATTERNS)
        raise ValueError(f"mode must be one of: {allowed}")

    user = _find_user(key)
    stable_id = str((user or {}).get("id") or key).strip()
    login = str((user or {}).get("login") or "").strip()
    monday = _normalize_monday(anchor_date, fallback=date.today())

    data = _load_modes()
    modes = dict(data.get("modes") or {})
    anchors = dict(data.get("user_anchor") or {})
    modes[stable_id] = canonical
    anchors[stable_id] = monday.isoformat()
    if login and login != stable_id:
        modes.pop(login, None)
        anchors.pop(login, None)

    cfg = ConfigManager()
    cfg.set("shifts.modes", modes)
    cfg.set("shifts.user_anchor", anchors)
    cfg.save_all()
    print(f"[WM-DBG][SHIFTS] schedule saved: {stable_id} -> {canonical}, anchor={monday.isoformat()}")


def _user_mode(user_id: str) -> str:
    return get_user_schedule(user_id)[0]


def _user_anchor_monday(user_id: str) -> date:
    return date.fromisoformat(get_user_schedule(user_id)[1])


def _week_idx(day: date) -> int:
    anchor = _anchor_monday()
    monday_today = day - timedelta(days=day.weekday())
    return (monday_today - anchor).days // 7


def _week_idx_for_user(user_id: str, day: date) -> int:
    monday_today = day - timedelta(days=day.weekday())
    anchor = _user_anchor_monday(user_id)
    return (monday_today - anchor).days // 7


_user_week_idx = _week_idx_for_user


def _slot_for_mode(mode: str, week_idx: int) -> str:
    """Zwróć zmianę dla literalnego trzytygodniowego wzorca."""
    canonical = _normalize_mode(mode)
    pattern = _DEFAULT_PATTERNS[canonical]
    digit = pattern[int(week_idx) % 3]
    return "RANO" if digit == "1" else "POPO"


def who_is_on_now(now: Optional[datetime] = None) -> Dict[str, List[str]]:
    now = now or datetime.now()
    times = _shift_times()
    slot = None
    if times["R_START"] <= now.time() < times["R_END"]:
        slot = "RANO"
    elif times["P_START"] <= now.time() < times["P_END"]:
        slot = "POPO"
    if slot is None:
        return {"slot": None, "users": []}

    users = []
    for user in _load_users():
        if not user.get("active"):
            continue
        uid = user["id"]
        widx = _week_idx_for_user(uid, now.date())
        if _slot_for_mode(_user_mode(uid), widx) == slot:
            users.append(user["name"])
    return {"slot": slot, "users": users}


def today_summary(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    info = who_is_on_now(now)
    if info["slot"] is None:
        return "Poza godzinami zmian"
    last_update = _last_update_date()
    times = _shift_times()
    if info["slot"] == "RANO":
        start = times["R_START"].strftime("%H:%M")
        end = times["R_END"].strftime("%H:%M")
        label = "Poranna"
    else:
        start = times["P_START"].strftime("%H:%M")
        end = times["P_END"].strftime("%H:%M")
        label = "Popołudniowa"
    names = ", ".join(info["users"]) if info["users"] else "—"
    return f"Ostatnia aktualizacja {last_update} | {label} {start}–{end} → {names}"


def week_matrix(start_date: date) -> Dict[str, List[Dict]]:
    week_start = start_date - timedelta(days=start_date.weekday())
    times = _shift_times()
    rows: List[Dict] = []
    for user in _load_users():
        if not user.get("active"):
            continue
        uid = user["id"]
        mode = _user_mode(uid)
        slot = _slot_for_mode(mode, _week_idx_for_user(uid, week_start))
        days = []
        for idx in range(7):
            current = week_start + timedelta(days=idx)
            weekday = current.weekday()
            if weekday == 6:
                continue
            if weekday == 5:
                code = "R"
            else:
                code = "R" if slot == "RANO" else "P"
            start = times["R_START"] if code == "R" else times["P_START"]
            end = times["R_END"] if code == "R" else times["P_END"]
            days.append(
                {
                    "date": current.strftime("%Y-%m-%d"),
                    "dow": current.strftime("%a"),
                    "shift": code,
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                }
            )
        rows.append(
            {
                "user": user["name"],
                "user_id": uid,
                "mode": mode,
                "slot": slot,
                "days": days,
            }
        )
    return {"week_start": week_start.strftime("%Y-%m-%d"), "rows": rows}


def set_user_mode(user_id: str, mode: str) -> None:
    _old_mode, anchor = get_user_schedule(user_id)
    set_user_schedule(user_id, mode, anchor)


def set_anchor_monday(iso_date: str) -> None:
    """Ustaw globalną kotwicę awaryjną dla starszych danych."""
    try:
        parsed = date.fromisoformat(str(iso_date or "")[:10])
    except ValueError as exc:
        raise ValueError(f"invalid date format: {iso_date}") from exc

    monday = parsed - timedelta(days=parsed.weekday())
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
    "get_user_schedule",
    "set_user_schedule",
    "set_user_mode",
    "set_anchor_monday",
    "TRYBY",
]

# ⏹ KONIEC KODU
