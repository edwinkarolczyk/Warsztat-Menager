"""Service layer for user profile operations.

Provides a simple API used by GUI modules to access and
modify user profile data without touching files directly.
"""
from __future__ import annotations

from typing import List, Optional, Dict

from profile_utils import (
    get_user as _get_user,
    save_user as _save_user,
    read_users as _read_users,
    DEFAULT_USER,
)


def get_user(login: str) -> Optional[Dict]:
    """Return profile dictionary for ``login`` or ``None`` if missing."""
    return _get_user(login)


def save_user(user: Dict) -> None:
    """Persist ``user`` profile data."""
    _save_user(user)


def get_all_users() -> List[Dict]:
    """Return list of all user profiles."""
    return _read_users()


def authenticate(login: str, pin: str) -> Optional[Dict]:
    """Return user dict matching ``login`` and ``pin`` or ``None``."""
    login = str(login).strip().lower()
    pin = str(pin).strip()
    for user in get_all_users():
        if (
            str(user.get("login", "")).strip().lower() == login
            and str(user.get("pin", "")).strip() == pin
        ):
            return user
    return None


def find_first_brygadzista() -> Optional[Dict]:
    """Return first user with role 'brygadzista' or ``None``."""
    for user in get_all_users():
        if str(user.get("rola", "")).strip().lower() == "brygadzista":
            return user
    return None


__all__ = [
    "get_user",
    "save_user",
    "get_all_users",
    "authenticate",
    "find_first_brygadzista",
    "DEFAULT_USER",
]
