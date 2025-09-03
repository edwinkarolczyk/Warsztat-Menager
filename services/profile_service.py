"""Service layer for user profile operations.

Provides a simple API used by GUI modules to access and
modify user profile data without touching files directly.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Dict, List, Optional

import profile_utils as _pu
from profile_utils import DEFAULT_USER


@contextmanager
def _use_users_file(path: str):
    """Temporarily point ``profile_utils`` to another users file."""
    original = _pu.USERS_FILE
    _pu.USERS_FILE = path
    try:
        yield
    finally:
        _pu.USERS_FILE = original


def get_user(login: str, file_path: Optional[str] = None) -> Optional[Dict]:
    """Return profile dictionary for ``login`` or ``None`` if missing."""
    if file_path:
        with _use_users_file(file_path):
            return _pu.get_user(login)
    return _pu.get_user(login)


def save_user(user: Dict, file_path: Optional[str] = None) -> None:
    """Persist ``user`` profile data."""
    if file_path:
        with _use_users_file(file_path):
            _pu.save_user(user)
    else:
        _pu.save_user(user)


def get_all_users(file_path: Optional[str] = None) -> List[Dict]:
    """Return list of all user profiles."""
    if file_path:
        with _use_users_file(file_path):
            return _pu.read_users()
    return _pu.read_users()


def write_users(users: List[Dict], file_path: Optional[str] = None) -> None:
    """Persist entire list of ``users``."""
    if file_path:
        with _use_users_file(file_path):
            _pu.write_users(users)
    else:
        _pu.write_users(users)


def authenticate(login: str, pin: str, file_path: Optional[str] = None) -> Optional[Dict]:
    """Return user dict matching ``login`` and ``pin`` or ``None``."""
    login = str(login).strip().lower()
    pin = str(pin).strip()
    for user in get_all_users(file_path):
        if (
            str(user.get("login", "")).strip().lower() == login
            and str(user.get("pin", "")).strip() == pin
        ):
            return user
    return None


def find_first_brygadzista(file_path: Optional[str] = None) -> Optional[Dict]:
    """Return first user with role 'brygadzista' or ``None``."""
    for user in get_all_users(file_path):
        if str(user.get("rola", "")).strip().lower() == "brygadzista":
            return user
    return None


def sync_presence(
    users: List[Dict], presence_file: str = "uzytkownicy_presence.json"
) -> None:
    """Synchronise auxiliary presence file with ``users`` list."""
    try:
        with open(presence_file, encoding="utf-8") as f:
            presence_data = json.load(f)
        if not isinstance(presence_data, list):
            presence_data = []
    except Exception:
        presence_data = []

    presence_map = {
        p.get("login"): p for p in presence_data if isinstance(p, dict)
    }
    current = set()
    for u in users:
        login = u.get("login")
        if not login:
            continue
        current.add(login)
        rec = presence_map.get(login)
        if rec:
            rec["rola"] = u.get("rola", "")
            rec["zmiana_plan"] = u.get("zmiana_plan", "")
            rec["imie"] = u.get("imie", "")
            rec["nazwisko"] = u.get("nazwisko", "")
        else:
            presence_map[login] = {
                "login": login,
                "rola": u.get("rola", ""),
                "zmiana_plan": u.get("zmiana_plan", ""),
                "status": "",
                "imie": u.get("imie", ""),
                "nazwisko": u.get("nazwisko", ""),
            }
    for login in list(presence_map.keys()):
        if login not in current:
            presence_map.pop(login, None)
    try:
        with open(presence_file, "w", encoding="utf-8") as f:
            json.dump(list(presence_map.values()), f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def is_logged_in(login: str) -> bool:
    """Return ``True`` if user ``login`` is currently online."""
    if not login:
        return False
    try:
        import presence

        recs, _ = presence.read_presence()
        for r in recs:
            if r.get("login") == login and r.get("online"):
                return True
    except Exception:
        pass
    return False


__all__ = [
    "get_user",
    "save_user",
    "get_all_users",
    "write_users",
    "authenticate",
    "find_first_brygadzista",
    "sync_presence",
    "is_logged_in",
    "DEFAULT_USER",
]
