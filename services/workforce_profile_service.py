# version: 1.4
"""Spójna warstwa profili pracowników WM.

Normalizuje historyczne formaty profiles.json przez profiles_store, nadaje
trwałe user_id i ustala jedno pole limitu urlopu:
``entitlements.urlop_rocznie``. Login pozostaje edytowalny, user_id nie.

Od 1.3 katalog trybów grafiku pochodzi bezpośrednio z silnika Grafiku.
Migracja konfiguracji patrzy na realną warstwę globalną, a nie na merged defaults,
dzięki czemu zwykły odczyt profili nie uruchamia w pętli ``save_all()``.

Od 1.4 ``workdays`` ma jedno znaczenie w całym Profilu: brak pola oznacza
poniedziałek-piątek, a jawnie zapisana pusta lista oznacza brak dni pracy.
"""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Iterable

from config_manager import ConfigManager
from grafiki.shifts_schedule import (
    _available_patterns as _schedule_available_patterns,
    _normalize_mode as _schedule_normalize_mode,
)
from profiles_store import load_profiles_users, resolve_profiles_path, save_profiles_users


_BASE_SHIFT_PATTERNS: dict[str, str] = dict(_schedule_available_patterns())
DEFAULT_WORKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)


def _key(value: object) -> str:
    return str(value or "").strip().casefold()


def normalize_shift_mode(value: object, *, fallback: str = "111") -> str:
    return _schedule_normalize_mode(value, fallback=fallback)


def merge_shift_patterns(raw: object) -> dict[str, str]:
    """Zwróć dokładnie kanoniczne wzorce z silnika Grafiku WM."""
    return dict(_schedule_available_patterns())


def _global_shifts_config(cfg: ConfigManager) -> dict:
    """Zwróć tylko zapisaną warstwę ``shifts`` bez domieszek defaults.

    ``cfg.get()`` zwraca konfigurację scaloną. Dla migracji jest to zły wybór,
    bo usunięte historyczne klucze z defaults pojawiają się ponownie i dawniej
    powodowały nieskończone ``set() -> save_all()`` przy każdym odczycie profili.
    """
    raw = getattr(cfg, "global_cfg", {})
    if not isinstance(raw, dict):
        return {}
    shifts = raw.get("shifts")
    return dict(shifts) if isinstance(shifts, dict) else {}


def ensure_required_shift_patterns() -> dict[str, str]:
    """Idempotentnie ustaw kanoniczne wzorce i migruj stare kody trybów.

    Funkcja może być wołana wielokrotnie podczas renderowania Profilu/Kalendarza,
    ale zapisuje config wyłącznie wtedy, gdy *faktycznie zapisana* warstwa globalna
    wymaga zmiany. Odczyt merged defaults nie może już wywołać zapisu.
    """
    desired_patterns = dict(_schedule_available_patterns())
    try:
        cfg = ConfigManager()
        changed = False
        shifts_cfg = _global_shifts_config(cfg)

        raw_patterns = shifts_cfg.get("patterns")
        current_patterns: dict[str, str] = {}
        if isinstance(raw_patterns, dict):
            current_patterns = {
                str(key): str(value)
                for key, value in raw_patterns.items()
                if str(key).strip()
            }
        if current_patterns != desired_patterns:
            cfg.set("shifts.patterns", desired_patterns)
            changed = True

        raw_modes = shifts_cfg.get("modes")
        if not isinstance(raw_modes, dict):
            raw_modes = {}
            cfg.set("shifts.modes", {})
            changed = True
        modes = dict(raw_modes)
        normalized_modes = {
            str(user_key): normalize_shift_mode(mode)
            for user_key, mode in modes.items()
            if str(user_key or "").strip()
        }
        if modes != normalized_modes:
            cfg.set("shifts.modes", normalized_modes)
            changed = True

        raw_anchors = shifts_cfg.get("user_anchor")
        if not isinstance(raw_anchors, dict):
            cfg.set("shifts.user_anchor", {})
            changed = True

        if changed:
            cfg.save_all()
        return desired_patterns
    except Exception:
        return desired_patterns


def _next_user_id(users: list[dict]) -> str:
    used: set[int] = set()
    for row in users:
        raw = str(row.get("user_id") or row.get("id") or "").strip().upper()
        if raw.startswith("USR-"):
            try:
                used.add(int(raw.split("-", 1)[1]))
            except Exception:
                pass
    number = 1
    while number in used:
        number += 1
    return f"USR-{number:04d}"


def _backup_once(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(path.name + ".before_workforce_v1.bak")
    if backup.exists():
        return
    try:
        shutil.copy2(path, backup)
    except Exception:
        pass


def _normalize_one(row: dict, users: list[dict]) -> tuple[dict, bool]:
    user = dict(row)
    changed = False

    uid = str(user.get("user_id") or "").strip()
    if not uid:
        legacy_id = str(user.get("id") or "").strip()
        if legacy_id.upper().startswith("USR-"):
            uid = legacy_id
        else:
            uid = _next_user_id(users)
        user["user_id"] = uid
        changed = True

    ent = user.get("entitlements")
    if not isinstance(ent, dict):
        ent = {}
        user["entitlements"] = ent
        changed = True
    if "urlop_rocznie" not in ent:
        old = user.get("urlop")
        nalezne = old.get("nalezne") if isinstance(old, dict) else None
        try:
            ent["urlop_rocznie"] = float(nalezne if nalezne is not None else 26)
        except Exception:
            ent["urlop_rocznie"] = 26
        changed = True

    if "zatrudniony_do" not in user:
        user["zatrudniony_do"] = ""
        changed = True

    for field in ("tryb_zmian", "zmiana_plan"):
        if field in user and str(user.get(field) or "").strip():
            normalized_mode = normalize_shift_mode(user.get(field))
            if user.get(field) != normalized_mode:
                user[field] = normalized_mode
                changed = True

    return user, changed


def ensure_profile_schema() -> list[dict]:
    """Idempotentnie normalizuj profiles.json bez utraty danych."""
    ensure_required_shift_patterns()
    path = resolve_profiles_path(None)
    try:
        users = load_profiles_users(path=path)
    except Exception:
        return []
    normalized: list[dict] = []
    changed = False
    working = [dict(row) for row in users if isinstance(row, dict)]
    for row in working:
        norm, row_changed = _normalize_one(row, normalized + working)
        normalized.append(norm)
        changed = changed or row_changed
    if changed:
        _backup_once(path)
        save_profiles_users(normalized, path=path)
    return normalized


def list_users(*, active_only: bool = False) -> list[dict]:
    users = ensure_profile_schema()
    out: list[dict] = []
    for row in users:
        if not isinstance(row, dict):
            continue
        user = dict(row)
        if active_only:
            active = user.get("active", True)
            status = _key(user.get("status"))
            if active is False or status in {"nieaktywny", "zablokowany", "dezaktywowany"}:
                continue
        out.append(user)
    return out


def get_user(login_or_id: str) -> dict | None:
    wanted = _key(login_or_id)
    if not wanted:
        return None
    for row in list_users():
        if _key(row.get("login")) == wanted or _key(row.get("user_id")) == wanted:
            return row
    return None


def workdays_for(user_or_login: dict | str) -> set[int]:
    """Zwróć jawnie zapisane dni pracy jako numery ``date.weekday()``.

    Brak pola ``workdays``/``dni_pracy`` zachowuje historyczne domyślne Pn-Pt.
    Jawnie zapisana pusta lista pozostaje pusta i nie jest zamieniana na Pn-Pt.
    """
    user = dict(user_or_login) if isinstance(user_or_login, dict) else (get_user(str(user_or_login or "")) or {})
    raw = user.get("workdays")
    if raw is None:
        raw = user.get("dni_pracy")
    if raw is None:
        return set(DEFAULT_WORKDAYS)
    if not isinstance(raw, (list, tuple, set)):
        return set(DEFAULT_WORKDAYS)
    out: set[int] = set()
    for item in raw:
        try:
            value = int(item)
        except Exception:
            continue
        if 0 <= value <= 6:
            out.add(value)
    return out


def is_workday(user_or_login: dict | str, day_value: date | str) -> bool:
    """Czy data jest skonfigurowanym dniem pracy danego pracownika."""
    if isinstance(day_value, date):
        parsed = day_value
    else:
        try:
            parsed = date.fromisoformat(str(day_value or "").strip()[:10])
        except Exception:
            return False
    return parsed.weekday() in workdays_for(user_or_login)


def save_user(user: dict, *, actor: str = "") -> dict:
    """Zapisz profil; istniejącego user_id nie wolno podmienić."""
    users = list_users()
    incoming = dict(user)
    login = _key(incoming.get("login"))
    uid = _key(incoming.get("user_id"))
    index = None
    current = None
    for idx, row in enumerate(users):
        if uid and _key(row.get("user_id")) == uid:
            index, current = idx, row
            break
        if login and _key(row.get("login")) == login:
            index, current = idx, row
            break

    if current is not None:
        old_uid = str(current.get("user_id") or "").strip()
        if old_uid:
            incoming["user_id"] = old_uid
    elif not str(incoming.get("user_id") or "").strip():
        incoming["user_id"] = _next_user_id(users)

    ent = incoming.get("entitlements")
    if not isinstance(ent, dict):
        ent = {}
        incoming["entitlements"] = ent
    if "urlop_rocznie" not in ent:
        old = incoming.get("urlop")
        try:
            ent["urlop_rocznie"] = (
                float(old.get("nalezne", 26)) if isinstance(old, dict) else 26
            )
        except Exception:
            ent["urlop_rocznie"] = 26
    incoming.setdefault("zatrudniony_do", "")

    if index is None:
        users.append(incoming)
    else:
        users[index] = incoming
    path = resolve_profiles_path(None)
    _backup_once(path)
    save_profiles_users(users, path=path)
    return incoming


def write_users(users: Iterable[dict]) -> None:
    current = list_users()
    id_by_login = {
        _key(row.get("login")): str(row.get("user_id") or "")
        for row in current
    }
    rows: list[dict] = []
    used: set[str] = set()
    for raw in users:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        login = _key(row.get("login"))
        existing_id = id_by_login.get(login, "")
        if existing_id:
            row["user_id"] = existing_id
        if not str(row.get("user_id") or "").strip():
            row["user_id"] = _next_user_id(rows + current)
        uid = _key(row.get("user_id"))
        if uid in used:
            row["user_id"] = _next_user_id(rows + current)
            uid = _key(row.get("user_id"))
        used.add(uid)
        norm, _ = _normalize_one(row, rows + current)
        rows.append(norm)
    path = resolve_profiles_path(None)
    _backup_once(path)
    save_profiles_users(rows, path=path)


def is_foreman(login: str) -> bool:
    user = get_user(login) or {}
    return _key(user.get("rola") or user.get("role")) == "brygadzista"


def display_name(user: dict) -> str:
    value = str(user.get("display_name") or "").strip()
    if value:
        return value
    parts = [
        str(user.get("imie") or "").strip(),
        str(user.get("nazwisko") or "").strip(),
    ]
    joined = " ".join(part for part in parts if part)
    return joined or str(user.get("login") or "—")


__all__ = [
    "DEFAULT_WORKDAYS",
    "ensure_profile_schema",
    "ensure_required_shift_patterns",
    "merge_shift_patterns",
    "normalize_shift_mode",
    "list_users",
    "get_user",
    "workdays_for",
    "is_workday",
    "save_user",
    "write_users",
    "is_foreman",
    "display_name",
]
