# version: 1.0

# Wersja pliku: 1.0.0
# Plik: profile_utils.py
# Pomocnicze: odczyt/zapis uzytkownicy.json + bezpieczne rozszerzanie pól.

import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config.paths import p_profiles, p_users
from config_manager import ConfigManager, PATH_MAP, get_profiles_path
from io_utils import read_json, write_json

if TYPE_CHECKING:  # pragma: no cover - tylko do statycznych analiz
    from config_manager import ConfigManager


_LOGGER = logging.getLogger(__name__)


def _data_dir() -> str:
    """Zwraca aktualny DATA_ROOT, liczony dynamicznie po wyborze WM_ROOT."""

    try:
        from core import root_paths

        return str(root_paths.get_data_root())
    except Exception:
        try:
            return str(Path(ConfigManager().path_data()))
        except Exception:
            print("[WM-ROOT][WARN] profile_utils fallback DATA_DIR=data")
            return "data"


DATA_DIR = _data_dir()

def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(p)))


def profiles_path(cfg: "ConfigManager") -> str:
    return _norm(str(p_profiles(cfg)))


def ensure_profiles_file(cfg: "ConfigManager") -> str:
    path = Path(p_profiles(cfg))
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "users": [
                        {
                            "login": DEFAULT_ADMIN_LOGIN,
                            "haslo": DEFAULT_ADMIN_PASSWORD,
                            "rola": PRIMARY_ADMIN_ROLE,
                            "active": True,
                        }
                    ]
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"[WM-DBG][PROFILE] Utworzono domyślny plik profili: {path}")
    return str(path)


def load_profiles(cfg: "ConfigManager") -> dict:
    path = Path(ensure_profiles_file(cfg))
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {"users": data if isinstance(data, list) else []}
    print(f"[WM-DBG][SHIFTS] users via {path}: {len(data.get('users', []))}")
    return data


def reset_admin_profile_if_needed(cfg: "ConfigManager", data: dict) -> dict:
    """Ensure there is at least one admin profile in ``data``."""

    users = data.get("users", []) if isinstance(data, dict) else []
    if any(
        str(u.get("rola", "")).strip().lower() in ADMIN_ROLE_NAMES
        for u in users
        if isinstance(u, dict)
    ):
        return data
    path = Path(p_profiles(cfg))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "users": [
            {
                "login": DEFAULT_ADMIN_LOGIN,
                "haslo": DEFAULT_ADMIN_PASSWORD,
                "rola": PRIMARY_ADMIN_ROLE,
                "active": True,
            }
        ]
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[WM-DBG][PROFILE] Zresetowano konto admin → {path}")
    return payload


# --- [PROFILE] helpers stażu z zatrudniony_od (YYYY-MM) ---
_YM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _anchor_date_from_ym(ym: str) -> date | None:
    """Konwertuje 'YYYY-MM' -> date(YYYY, MM, 1); toleruje też 'YYYY-MM-DD'."""

    if not ym:
        return None
    ym = ym.strip()
    if _YM_RE.match(ym):
        y, m = map(int, ym.split("-"))
        return date(y, m, 1)
    # tolerancyjnie przyjmij 'YYYY-MM-DD' i zetnij do pierwszego dnia
    try:
        dt = datetime.fromisoformat(ym.replace("Z", "+00:00")).date()
        return date(dt.year, dt.month, 1)
    except Exception:
        return None


def staz_days_for_login(login: str) -> int:
    """Zwraca staż w dniach od 'zatrudniony_od' do dzisiaj (UTC). Brak daty => 0."""

    try:
        from services.profile_service import get_user as svc_get_user
    except Exception:
        svc_get_user = None

    try:
        fetch_user = svc_get_user or get_user
        user = fetch_user(login)
    except Exception:
        # W razie problemów z warstwą serwisową wróć do lokalnego odczytu
        user = get_user(login)

    u = user or {}
    ym = (u.get("zatrudniony_od") or "").strip()
    anchor = _anchor_date_from_ym(ym)
    if not anchor:
        return 0
    today = datetime.now(timezone.utc).date()
    delta = (today - anchor).days
    return max(0, delta)


def staz_years_floor_for_login(login: str) -> int:
    """Pełne lata stażu (floor)."""

    return staz_days_for_login(login) // 365

PRIMARY_ADMIN_ROLE = "administrator"
DEFAULT_ADMIN_LOGIN = "admin"
DEFAULT_ADMIN_PASSWORD = "nimda"
DEFAULT_ADMIN_PIN = "nimda"

DEFAULT_BRYGADZISTA_LOGIN = "brygadzista"
DEFAULT_BRYGADZISTA_PASSWORD = "brygadzista"

ADMIN_ROLE_NAMES = {PRIMARY_ADMIN_ROLE}


def can_access_jarvis(user) -> bool:
    """Return ``True`` if ``user`` is allowed to open the Jarvis panel."""

    from config_manager import ConfigManager

    try:
        roles = ConfigManager().get("jarvis.role_access", [])
    except Exception:
        roles = []

    if not isinstance(roles, (list, tuple, set)):
        roles = []

    normalized_roles = {
        str(role).strip().lower()
        for role in roles
        if role is not None and str(role).strip()
    }
    if not normalized_roles:
        return False

    if user is None:
        return False

    if isinstance(user, dict):
        candidate = user.get("rola") or user.get("role")
    else:
        candidate = getattr(user, "role", None) or getattr(user, "rola", None)

    if candidate is None:
        return False

    return str(candidate).strip().lower() in normalized_roles


def _default_admin_payload() -> list[dict]:
    user = {
        "login": DEFAULT_ADMIN_LOGIN,
        "rola": PRIMARY_ADMIN_ROLE,
        "haslo": DEFAULT_ADMIN_PASSWORD,
        "pin": DEFAULT_ADMIN_PIN,
        "imie": "",
        "nazwisko": "",
        "staz": 0,
        "umiejetnosci": {},
        "kursy": [],
        "ostrzezenia": [],
        "nagrody": [],
        "historia_maszyn": [],
        "awarie": [],
        "sugestie": [],
        "opis": "",
        "preferencje": {"motyw": "dark", "widok_startowy": "panel"},
        "zadania": [],
        "ostatnia_wizyta": "1970-01-01T00:00:00Z",
        "disabled_modules": [],
    }
    return [user]


def _ask_root_directory_gui(initial: Path) -> Path | None:
    try:
        import tkinter as tk  # pragma: no cover - opcjonalne GUI
        from tkinter import filedialog
    except Exception:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        selection = filedialog.askdirectory(
            parent=root,
            initialdir=str(initial),
            title="Wskaż Folder WM (<root>)",
        )
        root.destroy()
    except Exception:
        return None

    if not selection:
        return None
    try:
        return Path(selection).expanduser().resolve()
    except Exception:
        return Path(selection).expanduser()


def _data_container(root: Path) -> Path:
    data_dir = root / "data"
    if root.name.lower() == "data" and not data_dir.exists():
        return root
    return data_dir


_ROOT_DEFAULTS = {
    "machines": {"maszyny": []},
    "warehouse": {"items": []},
    "bom": {"produkty": []},
    "tools.types": {"types": []},
    "tools.statuses": {"statuses": []},
    "tools.tasks": {"tasks": []},
    "tools.zadania": {"zadania": []},
    "orders": {"zlecenia": []},
    "data.profiles": {"profiles": []},
    "tools.dir": None,
    "root.logs": None,
    "root.backup": None,
}


def _prepare_root_structure(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    for key, template in _ROOT_DEFAULTS.items():
        rel = PATH_MAP.get(key, "")
        if not rel:
            continue
        target = root.joinpath(*Path(rel).parts)
        if template is None:
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        try:
            write_json(str(target), template)
        except Exception as exc:
            print(f"[PROFILE] Nie udało się utworzyć pliku {target}: {exc}")


def _prompt_for_users_root(preferred: Path | None = None) -> Path:
    preferred_dir = preferred or Path.cwd()
    try:
        preferred_dir = preferred_dir.expanduser().resolve()
    except Exception:
        preferred_dir = preferred_dir.expanduser()

    if not sys.stdin or not sys.stdin.isatty():
        preferred_dir.mkdir(parents=True, exist_ok=True)
        return preferred_dir

    gui_choice = _ask_root_directory_gui(preferred_dir)
    if gui_choice is not None:
        gui_choice.mkdir(parents=True, exist_ok=True)
        return gui_choice

    prompt = (
        "[PROFILE] Brak Folderu WM (<root>).\n"
        "Podaj katalog główny przechowywania danych (utworzymy w nim strukturę).\n"
        f"(ENTER = {preferred_dir}): "
    )

    while True:
        try:
            raw = input(prompt)
        except EOFError:
            raw = ""

        candidate = raw.strip() or str(preferred_dir)
        path = Path(candidate).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            try:
                path = path.resolve()
            except Exception:
                path = path.expanduser()
        except Exception as exc:  # pragma: no cover - interaktywne ostrzeżenie
            print(f"[PROFILE] Nie można utworzyć katalogu '{candidate}': {exc}")
            continue

        if path.is_dir():
            return path
        print(f"[PROFILE] Ścieżka nie jest katalogiem: {path}")


def _ensure_default_users_file(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_json(str(path), _default_admin_payload())
        print(f"[PROFILE] Utworzono domyślny plik użytkowników: {path}")
    return str(path)


def _configured_users_path(cfg: ConfigManager) -> Path | None:
    configured = cfg.get("profiles.users_file")
    if isinstance(configured, str) and configured.strip():
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return path.resolve()
        except Exception:
            return path
    return None


def _profiles_target_path(cfg: ConfigManager | None) -> Path:
    try:
        from core import root_paths

        resolved = root_paths.path_profiles()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        print(f"[WM-ROOT][PROFILES] target={resolved}")
        return resolved
    except Exception:
        pass
    raw_cfg = None
    if cfg is not None:
        raw_cfg = getattr(cfg, "global_cfg", None)
    try:
        raw_path = get_profiles_path(raw_cfg)
    except Exception:
        raw_path = ""
    path = Path(raw_path) if raw_path else Path("data") / "profiles.json"
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _legacy_profiles_sources(target: Path, cfg: ConfigManager | None) -> list[Path]:
    sources: list[Path] = []
    names = ("profiles.json", "uzytkownicy.json", "users.json")
    if cfg is not None:
        try:
            sources.append(Path(p_users(cfg)))
        except Exception:
            pass
    for name in names:
        sources.append(target.with_name(name))
        sources.append(Path("data") / name)
        sources.append(Path(name))
    sources.append(Path(__file__).resolve().parent / "uzytkownicy.json")
    normalized: list[Path] = []
    seen: set[str] = set()
    for source in sources:
        try:
            candidate = source.expanduser().resolve()
        except Exception:
            candidate = source.expanduser()
        key = str(candidate)
        if key in seen or candidate == target:
            continue
        seen.add(key)
        normalized.append(candidate)
    return normalized


def _normalize_legacy_payload(payload: Any) -> list[dict] | None:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("users", "profiles", "uzytkownicy"):
            seq = payload.get(key)
            if isinstance(seq, list):
                return [dict(item) for item in seq if isinstance(item, dict)]
        candidates = [value for value in payload.values() if isinstance(value, dict)]
        if candidates:
            return [dict(item) for item in candidates]
    return None


def _migrate_legacy_profiles(target: Path, cfg: ConfigManager | None) -> bool:
    for source in _legacy_profiles_sources(target, cfg):
        if not source.exists() or source == target:
            continue
        try:
            with source.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            _LOGGER.error(
                "[WM-ERR][PROFILES] invalid legacy profiles JSON %s: %s",
                source,
                exc,
            )
            continue
        except OSError as exc:
            _LOGGER.error(
                "[WM-ERR][PROFILES] cannot read legacy profiles %s: %s",
                source,
                exc,
            )
            continue
        normalized = _normalize_legacy_payload(payload)
        if normalized is None:
            _LOGGER.error(
                "[WM-ERR][PROFILES] unsupported legacy profiles structure: %s",
                source,
            )
            continue
        write_json(str(target), normalized)
        _LOGGER.warning(
            "[WM-WARN][PROFILES] migrated user profiles from %s to %s",
            source,
            target,
        )
        return True
    return False


def _default_users_file() -> str:
    try:
        cfg = ConfigManager()
    except Exception:
        cfg = None

    target = _profiles_target_path(cfg)
    if target.exists():
        return str(target)

    if _migrate_legacy_profiles(target, cfg):
        return str(target)

    return _ensure_default_users_file(target)


USERS_FILE = _default_users_file()
_DEFAULT_USERS_FILE = USERS_FILE


def refresh_users_file() -> str:
    global USERS_FILE, _DEFAULT_USERS_FILE
    USERS_FILE = _default_users_file()
    _DEFAULT_USERS_FILE = USERS_FILE
    return USERS_FILE


def current_users_file() -> str:
    """Zwraca aktualną ścieżkę users/profiles po zmianie ROOT."""

    return refresh_users_file()


def _ensure_users_file_path() -> None:
    """Ensure target directory exists and migrate legacy file if present."""
    global USERS_FILE
    USERS_FILE = _default_users_file()
    target = Path(USERS_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[WM-ROOT][PROFILES] users_file={target}")
    legacy = Path(__file__).resolve().parent / "uzytkownicy.json"
    if legacy.exists() and not target.exists():
        legacy.replace(USERS_FILE)

try:
    from utils.moduly import lista_modulow as _lista_modulow
except Exception:  # pragma: no cover - fallback na brak manifestu
    _lista_modulow = None

_SIDEBAR_BASE: list[tuple[str, str]] = [
    ("zlecenia", "Zlecenia"),
    ("narzedzia", "Narzędzia"),
    ("maszyny", "Maszyny"),
    ("magazyn", "Magazyn"),
    ("planowanie", "Planowanie"),
    ("jarvis", "Jarvis"),
    ("feedback", "Wyślij opinię"),
    ("uzytkownicy", "Użytkownicy"),
    ("ustawienia", "Ustawienia"),
    ("profil", "Profil"),
]

_SIDEBAR_ALWAYS = {"feedback", "uzytkownicy", "ustawienia", "profil"}


def _load_manifest_modules() -> set[str]:
    """Zwróć zestaw ID modułów zdefiniowanych w manifeście."""

    if _lista_modulow is None:
        _LOGGER.warning(
            "[PROFILE] Brak manifestu modułów – włączam domyślne moduły panelu."
        )
        return set()
    try:
        modules: Iterable[str] = _lista_modulow()
    except Exception:
        _LOGGER.warning(
            "[PROFILE] Błąd odczytu manifestu modułów – włączam domyślne moduły panelu.",
            exc_info=True,
        )
        return set()
    return {str(module).strip() for module in modules if module}


def _compute_sidebar_modules() -> list[tuple[str, str]]:
    """Zbuduj listę modułów bocznego panelu w oparciu o manifest."""

    manifest_modules = _load_manifest_modules()
    core_keys = {key for key, _ in _SIDEBAR_BASE if key not in _SIDEBAR_ALWAYS}
    if not manifest_modules:
        manifest_modules = set(core_keys)
        _LOGGER.warning(
            "[PROFILE] Manifest modułów pusty – dołączam podstawowe moduły: %s",
            ", ".join(sorted(core_keys)),
        )
    else:
        missing_core = core_keys - manifest_modules
        if missing_core:
            manifest_modules = set(manifest_modules) | core_keys
            _LOGGER.warning(
                "[PROFILE] Manifest modułów nie zawiera podstawowych modułów (%s) – "
                "dodaję zestaw domyślny, aby Panel był kompletny.",
                ", ".join(sorted(missing_core)),
            )
    modules: list[tuple[str, str]] = []
    for key, label in _SIDEBAR_BASE:
        if key in manifest_modules or key in _SIDEBAR_ALWAYS:
            modules.append((key, label))
    return modules


SIDEBAR_MODULES: list[tuple[str, str]] = _compute_sidebar_modules()

# Domyślny profil użytkownika z rozszerzonymi polami
DEFAULT_USER = {
    "login": DEFAULT_ADMIN_LOGIN,
    "rola": PRIMARY_ADMIN_ROLE,
    "haslo": DEFAULT_ADMIN_PASSWORD,
    "pin": DEFAULT_ADMIN_PIN,
    "active": True,
    "imie": "",
    "nazwisko": "",
    "staz": 0,
    "umiejetnosci": {},  # np. {"spawanie": 3}
    "kursy": [],
    "ostrzezenia": [],
    "nagrody": [],
    "historia_maszyn": [],
    "awarie": [],
    "sugestie": [],
    "opis": "",
    "preferencje": {"motyw": "dark", "widok_startowy": "panel"},
    "zadania": [],
    "ostatnia_wizyta": "1970-01-01T00:00:00Z",
    "disabled_modules": [],
}

def read_users():
    """
    Obsługuje 2 formaty:
    - lista użytkowników: [ {...}, {...} ]
    - dict z kluczem "users": {"users":[...]}
    Przy braku pliku – tworzy z DEFAULT_USER.
    Po odczycie uzupełnia brakujące pola przez ``ensure_user_fields``.
    """
    _ensure_users_file_path()
    data = read_json(USERS_FILE)
    if data is None:
        users = [DEFAULT_USER.copy()]
        write_json(USERS_FILE, users)
        return ensure_user_fields(users)
    if isinstance(data, list):
        users = data
    elif isinstance(data, dict) and "users" in data and isinstance(data["users"], list):
        users = data["users"]
    else:
        # Nieznany format -> spróbuj odczytać pole 'users' lub zamienić na listę
        users = [DEFAULT_USER.copy()]
    return ensure_user_fields(users)

def write_users(users):
    """ Zapisuje jako listę (najprościej i spójnie). """
    _ensure_users_file_path()
    # dopilnuj podstawowych pól
    norm = []
    for u in users:
        u = dict(u)
        u.setdefault("login", "user")
        u.setdefault("rola", "operator")
        u.setdefault("pin", "")
        if "active" not in u:
            u["active"] = True
        u.setdefault("imie", "")
        u.setdefault("nazwisko", "")
        u.setdefault("staz", 0)
        u.setdefault("umiejetnosci", {})
        u.setdefault("kursy", [])
        u.setdefault("ostrzezenia", [])
        u.setdefault("nagrody", [])
        u.setdefault("historia_maszyn", [])
        u.setdefault("awarie", [])
        u.setdefault("sugestie", [])
        u.setdefault("opis", "")
        u.setdefault("preferencje", {"motyw": "dark", "widok_startowy": "panel"})
        u.setdefault("zadania", [])
        u.setdefault("ostatnia_wizyta", "1970-01-01T00:00:00Z")
        u.setdefault("disabled_modules", [])
        norm.append(u)
    return write_json(USERS_FILE, norm)


def list_user_ids() -> list[str]:
    """Return a list of user logins from the profiles file."""
    return [u.get("login", "") for u in read_users()]

def find_user_by_pin(pin):
    users = read_users()
    sp = str(pin).strip()
    for u in users:
        if str(u.get("pin", "")).strip() == sp and sp != "":
            return u
    return None


def load_task_queue() -> list[Any]:
    data_dir = _data_dir()
    path_zadania = os.path.join(data_dir, "zadania.json")
    path_zlecenia = os.path.join(data_dir, "zlecenia.json")

    # Auto-tworzenie pustych plików jeśli nie istnieją
    for path in (path_zadania, path_zlecenia):
        if not os.path.exists(path):
            write_json(path, [])

    tasks: list[Any] = []
    if os.path.exists(path_zadania):
        data = read_json(path_zadania)
        if isinstance(data, list):
            tasks += data
        elif isinstance(data, dict):
            tasks += list(data.values())
    if os.path.exists(path_zlecenia):
        data = read_json(path_zlecenia)
        if isinstance(data, list):
            tasks += data
        elif isinstance(data, dict):
            tasks += list(data.values())
    return tasks


def get_tasks_for(login: str):
    users = read_users()
    for u in users:
        if str(u.get("login","")).lower() == str(login).lower():
            return list(u.get("zadania", []))
    return []

def get_user(login: str):
    """Zwraca słownik profilu użytkownika o podanym loginie."""
    for u in read_users():
        if str(u.get("login", "")).lower() == str(login).lower():
            return u
    return None

def save_user(user: dict):
    """Aktualizuje lub dodaje użytkownika w pliku konfiguracyjnym."""
    users = read_users()
    login = user.get("login")
    for idx, u in enumerate(users):
        if str(u.get("login")) == str(login):
            users[idx] = user
            break
    else:
        users.append(user)
    return write_users(users)

def ensure_user_fields(users):
    """Uzupełnia brakujące pola w przekazanej liście użytkowników."""
    changed = False
    for u in users:
        if "haslo" not in u: u["haslo"] = ""; changed = True
        if "active" not in u: u["active"] = True; changed = True
        if "preferencje" not in u: u["preferencje"] = {"motyw": "dark", "widok_startowy": "panel"}; changed = True
        if "zadania" not in u: u["zadania"] = []; changed = True
        if "imie" not in u: u["imie"] = ""; changed = True
        if "nazwisko" not in u: u["nazwisko"] = ""; changed = True
        if "staz" not in u: u["staz"] = 0; changed = True
        if "umiejetnosci" not in u: u["umiejetnosci"] = {}; changed = True
        if "kursy" not in u: u["kursy"] = []; changed = True
        if "ostrzezenia" not in u: u["ostrzezenia"] = []; changed = True
        if "nagrody" not in u: u["nagrody"] = []; changed = True
        if "historia_maszyn" not in u: u["historia_maszyn"] = []; changed = True
        if "awarie" not in u: u["awarie"] = []; changed = True
        if "sugestie" not in u: u["sugestie"] = []; changed = True
        if "opis" not in u: u["opis"] = ""; changed = True
        if "ostatnia_wizyta" not in u: u["ostatnia_wizyta"] = "1970-01-01T00:00:00Z"; changed = True
        if "disabled_modules" not in u: u["disabled_modules"] = []; changed = True
    if changed:
        write_json(USERS_FILE, users)
    return users


__all__ = [
    "USERS_FILE",
    "SIDEBAR_MODULES",
    "DEFAULT_USER",
    "DEFAULT_ADMIN_LOGIN",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_ADMIN_PIN",
    "DEFAULT_BRYGADZISTA_LOGIN",
    "DEFAULT_BRYGADZISTA_PASSWORD",
    "PRIMARY_ADMIN_ROLE",
    "ADMIN_ROLE_NAMES",
    "current_users_file",
    "read_users",
    "write_users",
    "list_user_ids",
    "find_user_by_pin",
    "can_access_jarvis",
    "load_task_queue",
    "get_tasks_for",
    "get_user",
    "save_user",
    "ensure_user_fields",
    "staz_days_for_login",
    "staz_years_floor_for_login",
]
