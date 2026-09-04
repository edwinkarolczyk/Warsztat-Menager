# version: 1.1
"""Spójna warstwa profili pracowników WM.

Normalizuje wszystkie historyczne formaty profiles.json przez profiles_store,
nadaje trwałe user_id i ustala jedno pole limitu urlopu:
``entitlements.urlop_rocznie``. Login pozostaje edytowalny, user_id nie.

Od 1.1 naprawia też historyczny config grafiku: własne ``shifts.patterns``
rozszerzają wzorce WM zamiast usuwać obowiązkowe tryby 111/222/121/212.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from config_manager import ConfigManager
from profiles_store import load_profiles_users, resolve_profiles_path, save_profiles_users


_BASE_SHIFT_PATTERNS: dict[str, str] = {
    "112": "112",
    "111": "111",
    "222": "222",
    "12": "12",
    "121": "121",
    "212": "212",
    "211": "211",
    "1212": "1212",
}


def _key(value: object) -> str:
    return str(value or "").strip().casefold()


def merge_shift_patterns(raw: object) -> dict[str, str]:
    """Połącz stare/customowe wzorce z pełnym zestawem bazowym WM."""
    merged = dict(_BASE_SHIFT_PATTERNS)
    if isinstance(raw, dict):
        for key, value in raw.items():
            name = str(key or "").strip()
            if not name:
                continue
            pattern = str(value or name).strip() or name
            merged[name] = pattern
    elif isinstance(raw, (list, tuple, set)):
        for value in raw:
            name = str(value or "").strip()
            if name:
                merged[name] = name
    return merged


def ensure_required_shift_patterns() -> dict[str, str]:
    """Uzupełnij config grafiku bez usuwania istniejących wzorców."""
    try:
        cfg = ConfigManager()
        raw = cfg.get("shifts.patterns", {})
        merged = merge_shift_patterns(raw)
        current = {}
        if isinstance(raw, dict):
            current = {str(k): str(v) for k, v in raw.items() if str(k).strip()}
        elif isinstance(raw, (list, tuple, set)):
            current = {str(v): str(v) for v in raw if str(v).strip()}
        if current != merged:
            cfg.set("shifts.patterns", merged)
            cfg.save_all()
        return merged
    except Exception:
        return dict(_BASE_SHIFT_PATTERNS)


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
    # Każdy odczyt przez kanoniczny serwis gwarantuje trwałe user_id.
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
            ent["urlop_rocznie"] = float(old.get("nalezne", 26)) if isinstance(old, dict) else 26
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
    id_by_login = {_key(row.get("login")): str(row.get("user_id") or "") for row in current}
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
    parts = [str(user.get("imie") or "").strip(), str(user.get("nazwisko") or "").strip()]
    joined = " ".join(part for part in parts if part)
    return joined or str(user.get("login") or "—")


__all__ = [
    "ensure_profile_schema", "ensure_required_shift_patterns", "merge_shift_patterns",
    "list_users", "get_user", "save_user", "write_users", "is_foreman", "display_name",
]
