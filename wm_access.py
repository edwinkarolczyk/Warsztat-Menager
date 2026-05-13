# version: 1.0
import json
from pathlib import Path

from config.paths import p_profiles
from config_manager import ConfigManager
from profile_utils import ensure_profiles_file
from utils.moduly import module_active, zaladuj_manifest


def _profiles_path() -> Path:
    """Return preferred path to ``profiles.json``."""

    cfg = None
    try:
        cfg = ConfigManager()
        preferred = Path(ensure_profiles_file(cfg))
        return preferred
    except Exception:
        pass
    if cfg is not None:
        try:
            return p_profiles(cfg)
        except Exception:
            pass
    return Path("profiles.json").resolve()


def _ensure_dirs():
    path = _profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)


def load_profiles():
    """Ładuje słownik profili z pliku profiles.json w katalogu danych (lub pusty)."""
    _ensure_dirs()
    path = _profiles_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _profiles_users_list(profiles_payload) -> list[dict]:
    """Zwróć listę użytkowników z różnych formatów profiles.json."""

    if isinstance(profiles_payload, list):
        return [dict(item) for item in profiles_payload if isinstance(item, dict)]

    if isinstance(profiles_payload, dict):
        users = profiles_payload.get("users")
        if isinstance(users, list):
            return [dict(item) for item in users if isinstance(item, dict)]

        profiles = profiles_payload.get("profiles")
        if isinstance(profiles, list):
            return [dict(item) for item in profiles if isinstance(item, dict)]

        uzytkownicy = profiles_payload.get("uzytkownicy")
        if isinstance(uzytkownicy, list):
            return [dict(item) for item in uzytkownicy if isinstance(item, dict)]

        out: list[dict] = []
        for key, value in profiles_payload.items():
            if not isinstance(value, dict):
                continue
            user = dict(value)
            user.setdefault("login", key)
            out.append(user)
        return out

    return []


def _find_profile_user(profiles_payload, login: str) -> dict:
    login_norm = str(login or "").strip().casefold()
    if not login_norm:
        return {}
    for user in _profiles_users_list(profiles_payload):
        if str(user.get("login", "") or "").strip().casefold() == login_norm:
            return user
    return {}


def save_profiles(profiles_dict: dict):
    """Zapisuje słownik profili do pliku profiles.json w katalogu danych."""
    _ensure_dirs()
    path = _profiles_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles_dict, f, ensure_ascii=False, indent=2)


def get_disabled_modules_for(login: str):
    """Zwraca listę disabled_modules dla danego loginu (lista lub [])."""
    profiles = load_profiles()
    user = _find_profile_user(profiles, login)
    disabled = user.get("disabled_modules")
    if isinstance(disabled, list):
        return [str(item) for item in disabled]
    return []


def set_modules_visibility(login: str, show_maszyny: bool, show_narzedzia: bool):
    """Ustawia widoczność modułów dla użytkownika."""
    profiles = load_profiles()
    user = _find_profile_user(profiles, login)
    disabled = user.get("disabled_modules")
    if not isinstance(disabled, list):
        disabled = []

    def add_disabled(name):
        if name not in disabled:
            disabled.append(name)

    def remove_disabled(name):
        if name in disabled:
            disabled.remove(name)

    if show_maszyny:
        remove_disabled("maszyny")
    else:
        add_disabled("maszyny")

    if show_narzedzia:
        remove_disabled("narzedzia")
    else:
        add_disabled("narzedzia")

    user["disabled_modules"] = disabled
    _replace_profile_user(profiles, login, user)
    save_profiles(profiles)


def _replace_profile_user(profiles_payload, login: str, user: dict) -> None:
    login_norm = str(login or user.get("login", "") or "").strip().casefold()
    if not login_norm:
        return

    if isinstance(profiles_payload, dict) and isinstance(profiles_payload.get("users"), list):
        users = profiles_payload["users"]
        for idx, item in enumerate(users):
            if str(item.get("login", "") or "").strip().casefold() == login_norm:
                users[idx] = user
                return
        users.append(user)
        return

    if isinstance(profiles_payload, list):
        for idx, item in enumerate(profiles_payload):
            if str(item.get("login", "") or "").strip().casefold() == login_norm:
                profiles_payload[idx] = user
                return
        profiles_payload.append(user)
        return

    if isinstance(profiles_payload, dict):
        profiles_payload[str(user.get("login") or login)] = user


_ALIASES = {
    "panel główny": "panel_glowny",
    "panel glowny": "panel_glowny",
    "narzędzia": "narzedzia",
    "narzedzia": "narzedzia",
    "maszyny": "maszyny",
    "magazyn": "magazyn",
    "zlecenia": "zlecenia",
    "ustawienia": "ustawienia",
    "profil": "profile",
    "profile": "profile",
    "jjarvis": "jarvis",
    "wyślij opinię": "wyslij_opinie",
    "wyslij opinie": "wyslij_opinie",
}


def normalize_module_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    key = name.strip().lower()
    return _ALIASES.get(key, key.replace(" ", "_"))


def set_modules_visibility_map(login: str, show_map: dict):
    """Ustawia widoczność wielu modułów naraz."""
    profiles = load_profiles()
    user = _find_profile_user(profiles, login)
    disabled_modules = user.get("disabled_modules")
    if not isinstance(disabled_modules, list):
        disabled_modules = []
    disabled_modules = [normalize_module_name(module) for module in disabled_modules]
    disabled_modules = list(dict.fromkeys(module for module in disabled_modules if module))

    for module, show in (show_map or {}).items():
        module = normalize_module_name(module)
        if not module:
            continue
        if show:
            if module in disabled_modules:
                disabled_modules.remove(module)
        else:
            if module not in disabled_modules:
                disabled_modules.append(module)

    user["disabled_modules"] = disabled_modules
    _replace_profile_user(profiles, login, user)
    save_profiles(profiles)


def get_effective_allowed_modules(login: str, all_modules: list[str]) -> list[str]:
    """Zwraca listę dozwolonych modułów po uwzględnieniu disabled_modules."""
    if not isinstance(all_modules, (list, tuple, set)):
        all_modules = []
    normalized_all = [normalize_module_name(module) for module in all_modules]
    disabled = {
        normalize_module_name(module)
        for module in get_disabled_modules_for(login)
    }
    skip = {"panel_glowny"}
    try:
        _manifest = zaladuj_manifest()
    except Exception:
        _manifest = None
    return [
        module
        for module in normalized_all
        if module
        and module not in disabled
        and module not in skip
        and module_active(module, manifest=_manifest)
    ]
