# version: 1.0
"""
Profile service – aktywny użytkownik i operacje profili.

Zmiany (2025-10):
 - stabilny odczyt aktywnego użytkownika z fallbackami
   (ENV → sesja w pamięci → dopasowanie do systemowego loginu → None),
 - publiczne API:
     set_active_user(login: str) -> None
     get_active_user() -> str | None
     get_active_profile() -> dict | None
     ensure_active_user_or_none() -> str | None
 - bez zmian w GUI; istniejące wywołania korzystające z get_active_user()
   zaczną działać („Przypisz mnie”) jeśli profil da się ustalić.
"""
from __future__ import annotations

import getpass
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import profile_utils as _pu
from config.paths import p_assign_orders, p_assign_tools, p_presence
from config_manager import ConfigManager
from profile_utils import (
    DEFAULT_USER,
    DEFAULT_BRYGADZISTA_LOGIN,
    DEFAULT_BRYGADZISTA_PASSWORD,
)
from profile_tasks import get_tasks_for as _get_tasks_for, workload_for as _workload_for
from logger import log_akcja
from profiles_store import resolve_profiles_path

try:
    from core import root_paths
except Exception:  # pragma: no cover
    root_paths = None


def _data_root() -> Path:
    if root_paths is not None:
        return root_paths.get_data_root()
    try:
        return Path(ConfigManager().path_data())
    except Exception:
        print("[WM-ROOT][WARN] profile_service fallback DATA_ROOT=data")
        return Path("data")


def _profiles_dir() -> Path:
    path = _data_root() / "profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Zachowane dla kompatybilności z kodem, który może importować te nazwy.
DATA_ROOT = str(_data_root())
PROFILES_DIR = _profiles_dir()


def _app_root() -> Path:
    """Prefer configured root (WM_APP_ROOT/WM_DATA_ROOT) or fallback to CWD."""

    env_root = os.environ.get("WM_APP_ROOT")
    if env_root:
        try:
            return Path(env_root).expanduser().resolve()
        except Exception:
            pass
    return Path.cwd()


def _profiles_path() -> Path:
    """Standard path to ``profiles.json`` resolved via config."""

    return resolve_profiles_path(None)


def _users_file_path(file_path: Optional[str] = None) -> Path:
    if file_path:
        return Path(file_path)
    resolved = resolve_profiles_path(None)
    if resolved.exists():
        return resolved
    cwd_candidates = [(Path.cwd() / "uzytkownicy.json").resolve()]
    for candidate in cwd_candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return resolved


def _read_json_safe(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


class ProfileService:
    """Zarządzanie aktywnym użytkownikiem (loginem) i dostępem do profili."""

    _active_user: Optional[str] = None
    _profiles_cache: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def set_active_user(cls, login: str) -> None:
        """Store login of the last poprawnie zalogowany użytkownik."""

        login = (login or "").strip()
        cls._active_user = login or None
        if cls._active_user:
            os.environ["WM_ACTIVE_USER"] = cls._active_user

    @classmethod
    def get_active_user(cls) -> Optional[str]:
        """Return login zapamiętany przy ostatnim logowaniu."""

        if cls._active_user:
            return cls._active_user

        env_login = os.environ.get("WM_ACTIVE_USER")
        if env_login:
            cls._active_user = env_login.strip() or None
            if cls._active_user:
                return cls._active_user

        sys_login = (getpass.getuser() or "").strip().lower()
        if sys_login:
            profile = cls._find_profile(
                lambda entry: str(entry.get("login", "")).strip().lower() == sys_login
            )
            if profile:
                cls._active_user = profile.get("login")
                if cls._active_user:
                    os.environ["WM_ACTIVE_USER"] = cls._active_user
                    return cls._active_user

        return None

    @classmethod
    def get_active_profile(cls) -> Optional[Dict[str, Any]]:
        """Return full profile dictionary for the active user (if any)."""

        login = cls.get_active_user()
        if not login:
            return None
        return cls._find_profile(
            lambda entry: str(entry.get("login", "")).strip() == str(login).strip()
        )

    @classmethod
    def clear_active_user(cls) -> None:
        """Forget the active user and remove env flag."""

        cls._active_user = None
        os.environ.pop("WM_ACTIVE_USER", None)

    @classmethod
    def ensure_active_user_or_none(cls) -> Optional[str]:
        """Safe variant returning login or ``None`` without propagating errors."""

        try:
            return cls.get_active_user()
        except Exception:
            return None

    # ── PUBLIC: lista profili (login, imię/nazwisko, rola) ───────────────────
    @classmethod
    def list_profiles(cls) -> List[Dict[str, str]]:
        """Return profiles formatted for GUI selection lists."""

        items: List[Dict[str, str]] = []
        for profile in cls._load_profiles():
            items.append(
                {
                    "login": str(profile.get("login", "")),
                    "name": str(
                        profile.get("name")
                        or profile.get("imie")
                        or profile.get("user")
                        or profile.get("login")
                        or ""
                    ),
                    "role": str(profile.get("role") or profile.get("rola") or ""),
                }
            )

        items.sort(key=lambda entry: (entry["name"].lower(), entry["login"].lower()))
        return items

    @classmethod
    def _load_profiles(cls) -> List[Dict[str, Any]]:
        if cls._profiles_cache is not None:
            return cls._profiles_cache

        path = _profiles_path()
        raw = _read_json_safe(path, default=[])
        if isinstance(raw, dict):
            items = raw.get("profiles") or raw.get("uzytkownicy") or []
        elif isinstance(raw, list):
            items = raw
        else:
            items = []

        normalized: List[Dict[str, Any]] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            entry.setdefault("login", entry.get("name") or entry.get("user") or "")
            normalized.append(entry)
        cls._profiles_cache = normalized
        return cls._profiles_cache

    @classmethod
    def _find_profile(cls, predicate: Callable[[Dict[str, Any]], bool]) -> Optional[Dict[str, Any]]:
        for entry in cls._load_profiles():
            try:
                if predicate(entry):
                    return entry
            except Exception:
                continue
        return None


def _invalidate_profiles_cache() -> None:
    ProfileService._profiles_cache = None


@contextmanager
def _use_users_file(path: str):
    """Temporarily point ``profile_utils`` to another users file."""
    original = _pu.USERS_FILE
    _pu.USERS_FILE = path
    try:
        yield
    finally:
        _pu.USERS_FILE = original


def _config_manager_or_none() -> ConfigManager | None:
    try:
        return ConfigManager()
    except Exception:
        return None


def _presence_path() -> Path:
    path = _profiles_dir() / "presence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _assign_orders_path() -> Path:
    path = _profiles_dir() / "assign_orders.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _assign_tools_path() -> Path:
    path = _profiles_dir() / "assign_tools.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _overrides_dir() -> Path:
    return _profiles_dir()


def _status_override_path(login: str) -> Path:
    return _overrides_dir() / f"status_{login}.json"


def get_user(login: str, file_path: Optional[str] = None) -> Optional[Dict]:
    """Return profile dictionary for ``login`` or ``None`` if missing."""
    path = _users_file_path(file_path)
    if not path.exists():
        return None
    original = _pu.USERS_FILE
    try:
        with _use_users_file(str(path)):
            return _pu.get_user(login)
    finally:
        _pu.USERS_FILE = original


def save_user(user: Dict, file_path: Optional[str] = None) -> None:
    """Persist ``user`` profile data."""
    path = _users_file_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    original = _pu.USERS_FILE
    try:
        with _use_users_file(str(path)):
            _pu.save_user(user)
    finally:
        _pu.USERS_FILE = original
    _invalidate_profiles_cache()


def get_all_users(file_path: Optional[str] = None) -> List[Dict]:
    """Return list of all user profiles."""
    path = _users_file_path(file_path)
    if not path.exists():
        return []
    original = _pu.USERS_FILE
    try:
        with _use_users_file(str(path)):
            return _pu.read_users()
    finally:
        _pu.USERS_FILE = original


def get_all_logins(file_path: Optional[str] = None) -> List[str]:
    """Return sorted list of user logins."""

    logins: List[str] = []
    for user in get_all_users(file_path):
        login = str(user.get("login", "")).strip()
        if login and login not in logins:
            logins.append(login)
    logins.sort(key=lambda value: value.lower())
    return logins


def write_users(users: List[Dict], file_path: Optional[str] = None) -> None:
    """Persist entire list of ``users``."""
    path = _users_file_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    original = _pu.USERS_FILE
    try:
        with _use_users_file(str(path)):
            _pu.write_users(users)
    finally:
        _pu.USERS_FILE = original
    _invalidate_profiles_cache()


def _is_user_active(user: Dict) -> bool:
    """Return ``True`` when user entry should be treated as aktywny."""

    if isinstance(user, dict):
        active = user.get("active")
        if active is not None and active is not True:
            return False
        status = str(user.get("status", "")).strip().lower()
        if status in {"nieaktywny", "zablokowany", "dezaktywowany"}:
            return False
    return True


def authenticate(login: str, pin: str, file_path: Optional[str] = None) -> Optional[Dict]:
    """Return user dict matching ``login`` and ``pin`` or ``None``."""
    login = str(login).strip().lower()
    secret = str(pin).strip()
    users = get_all_users(file_path)
    for user in users:
        if str(user.get("login", "")).strip().lower() != login:
            continue
        if not _is_user_active(user):
            continue
        pin_match = secret and str(user.get("pin", "")).strip() == secret
        pass_match = secret and str(user.get("haslo", "")).strip() == secret
        if pin_match or pass_match:
            return user
    return None


def find_first_brygadzista(file_path: Optional[str] = None) -> Optional[Dict]:
    """Return first user with role 'brygadzista' or ``None``."""
    for user in get_all_users(file_path):
        if str(user.get("rola", "")).strip().lower() == "brygadzista":
            return user
    return None


def ensure_brygadzista_account(
    file_path: Optional[str] = None,
    login: str = DEFAULT_BRYGADZISTA_LOGIN,
    password: str = DEFAULT_BRYGADZISTA_PASSWORD,
) -> Dict:
    """Ensure at least one brygadzista account exists and return it."""

    normalized_login = str(login).strip().lower()
    desired_password = str(password).strip() or DEFAULT_BRYGADZISTA_PASSWORD

    users = get_all_users(file_path)
    target: Optional[Dict] = None
    for user in users:
        user_login = str(user.get("login", "")).strip().lower()
        user_role = str(user.get("rola", "")).strip().lower()
        if user_login == normalized_login:
            target = user
            break
        if target is None and user_role == "brygadzista":
            target = user

    if target is None:
        target = dict(DEFAULT_USER)
        target.update(
            {
                "login": login,
                "rola": "brygadzista",
                "pin": desired_password,
                "haslo": desired_password,
                "active": True,
                "disabled_modules": [],
            }
        )
        users.append(target)
    else:
        target["login"] = login
        target["rola"] = "brygadzista"
        target["pin"] = desired_password
        target["haslo"] = desired_password
        target["active"] = True
        target.setdefault("disabled_modules", [])

    write_users(users, file_path=file_path)
    try:
        sync_presence(users)
    except Exception:
        pass
    return target


def sync_presence(
    users: List[Dict], presence_file: Optional[str] = None
) -> None:
    """Synchronise auxiliary presence file with ``users`` list."""
    target = Path(presence_file) if presence_file else _presence_path()
    try:
        with target.open(encoding="utf-8") as f:
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
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
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


def _load_json(path: Path, default):
    try:
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_status_overrides(login: str) -> Dict[str, str]:
    """Return mapping of task ID to status overrides for ``login``."""
    path = _status_override_path(login)
    return _load_json(path, {})


def save_status_override(login: str, task_id: str, status: str) -> None:
    """Persist status override for ``task_id`` and ``login``."""
    data = load_status_overrides(login)
    data[str(task_id)] = status
    path = _status_override_path(login)
    _save_json(path, data)


def load_assign_orders() -> Dict[str, str]:
    """Return mapping of order number to login."""
    path = _assign_orders_path()
    return _load_json(path, {})


def save_assign_order(order_no: str, login: Optional[str]) -> None:
    """Assign ``order_no`` to ``login`` (``None`` removes assignment)."""
    data = load_assign_orders()
    key = str(order_no)
    if login:
        data[key] = str(login)
    else:
        data.pop(key, None)
    path = _assign_orders_path()
    _save_json(path, data)


def load_assign_tools() -> Dict[str, str]:
    """Return mapping of tool task ID to login."""
    path = _assign_tools_path()
    return _load_json(path, {})


def save_assign_tool(task_id: str, login: Optional[str]) -> None:
    """Assign tool task ``task_id`` to ``login`` (``None`` removes assignment)."""
    data = load_assign_tools()
    key = str(task_id)
    if login:
        data[key] = str(login)
    else:
        data.pop(key, None)
    path = _assign_tools_path()
    _save_json(path, data)


def count_presence(login: str, presence_file: Optional[str] = None) -> int:
    """Return number of presence records for ``login``."""
    target = Path(presence_file) if presence_file else _presence_path()
    try:
        with target.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return 0
    cnt = 0
    for rec in data.values():
        if str(rec.get("login", "")).lower() == str(login).lower():
            cnt += 1
    return cnt


def get_tasks_for(login: str, **kwargs):
    """Proxy to :func:`profile_tasks.get_tasks_for`."""

    return _get_tasks_for(login, **kwargs)


def workload_for(users, **kwargs):
    """Proxy to :func:`profile_tasks.workload_for`."""

    return _workload_for(users, **kwargs)


def _task_files() -> List[str]:
    try:
        _cfg = ConfigManager()
        return [
            _cfg.path_data("zlecenia.json"),
            _cfg.path_data("zadania.json"),
        ]
    except Exception:
        base = _data_root()
        print(f"[WM-ROOT][WARN] profile_service task files fallback={base}")
        return [
            str(base / "zlecenia.json"),
            str(base / "zadania.json"),
        ]


try:
    _load_tasks_raw  # type: ignore[name-defined]
except NameError:

    def _load_tasks_raw() -> List[Dict[str, Any]]:
        for fp in _task_files():
            if os.path.exists(fp):
                try:
                    with open(fp, encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    continue
                if isinstance(data, dict):
                    return [v for v in data.values() if isinstance(v, dict)]
                if isinstance(data, list):
                    return [v for v in data if isinstance(v, dict)]
        return []


def tasks_data_status() -> Tuple[bool, Optional[str], int]:
    """Return information about the availability of task data sources."""

    for fp in _task_files():
        if os.path.exists(fp):
            try:
                with open(fp, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                return False, fp, 0
            if isinstance(data, dict):
                count = len([v for v in data.values() if isinstance(v, dict)])
            elif isinstance(data, list):
                count = len([v for v in data if isinstance(v, dict)])
            else:
                count = 0
            return True, fp, count
    return False, None, 0


__all__ = [
    "get_user",
    "save_user",
    "get_all_users",
    "write_users",
    "authenticate",
    "find_first_brygadzista",
    "ensure_brygadzista_account",
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
    "get_tasks_for",
    "tasks_data_status",
    "workload_for",
]
