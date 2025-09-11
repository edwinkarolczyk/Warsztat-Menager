"""Service layer for user profile operations.

Provides a simple API used by GUI modules to access and
modify user profile data without touching files directly.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Dict, List, Optional

import profile_utils as _pu
from profile_utils import DEFAULT_USER
from logger import log_akcja
from utils.path_utils import cfg_path


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
    users = get_all_users(file_path)
    for user in users:
        if (
            str(user.get("login", "")).strip().lower() == login
            and str(user.get("pin", "")).strip() == pin
        ):
            return user
    if not file_path:
        legacy = cfg_path("uzytkownicy.json")
        if os.path.exists(legacy):
            for user in get_all_users(legacy):
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
    except Exception as e:
        log_akcja(f"[Presence] write error: {e}")
        raise


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
    except Exception as e:
        log_akcja(f"[Presence] read error: {e}")
    return False


OVERRIDE_DIR = os.path.join("data", "profil_overrides")


def _load_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_status_overrides(login: str) -> Dict[str, str]:
    """Return mapping of task ID to status overrides for ``login``."""
    path = os.path.join(OVERRIDE_DIR, f"status_{login}.json")
    return _load_json(path, {})


def save_status_override(login: str, task_id: str, status: str) -> None:
    """Persist status override for ``task_id`` and ``login``."""
    data = load_status_overrides(login)
    data[str(task_id)] = status
    path = os.path.join(OVERRIDE_DIR, f"status_{login}.json")
    _save_json(path, data)


def load_assign_orders() -> Dict[str, str]:
    """Return mapping of order number to login."""
    path = os.path.join(OVERRIDE_DIR, "assign_orders.json")
    return _load_json(path, {})


def save_assign_order(order_no: str, login: Optional[str]) -> None:
    """Assign ``order_no`` to ``login`` (``None`` removes assignment)."""
    data = load_assign_orders()
    key = str(order_no)
    if login:
        data[key] = str(login)
    else:
        data.pop(key, None)
    path = os.path.join(OVERRIDE_DIR, "assign_orders.json")
    _save_json(path, data)


def load_assign_tools() -> Dict[str, str]:
    """Return mapping of tool task ID to login."""
    path = os.path.join(OVERRIDE_DIR, "assign_tools.json")
    return _load_json(path, {})


def save_assign_tool(task_id: str, login: Optional[str]) -> None:
    """Assign tool task ``task_id`` to ``login`` (``None`` removes assignment)."""
    data = load_assign_tools()
    key = str(task_id)
    if login:
        data[key] = str(login)
    else:
        data.pop(key, None)
    path = os.path.join(OVERRIDE_DIR, "assign_tools.json")
    _save_json(path, data)


def count_presence(login: str, presence_file: str = "presence.json") -> int:
    """Return number of presence records for ``login``."""
    try:
        with open(presence_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return 0
    cnt = 0
    for rec in data.values():
        if str(rec.get("login", "")).lower() == str(login).lower():
            cnt += 1
    return cnt


__all__ = [
    "get_user",
    "save_user",
    "get_all_users",
    "write_users",
    "authenticate",
    "find_first_brygadzista",
    "sync_presence",
    "is_logged_in",
    "load_status_overrides",
    "save_status_override",
    "load_assign_orders",
    "save_assign_order",
    "load_assign_tools",
    "save_assign_tool",
    "count_presence",
    "DEFAULT_USER",
]
