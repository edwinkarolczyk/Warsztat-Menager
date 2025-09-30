
# Wersja pliku: 1.0.0
# Plik: profile_utils.py
# Pomocnicze: odczyt/zapis uzytkownicy.json + bezpieczne rozszerzanie pól.

from datetime import date, datetime, timezone
import re
from pathlib import Path

from io_utils import read_json, write_json
from utils.path_utils import cfg_path


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

USERS_FILE = cfg_path("data/uzytkownicy.json")
_DEFAULT_USERS_FILE = USERS_FILE


def _ensure_users_file_path() -> None:
    """Ensure target directory exists and migrate legacy file if present."""
    global USERS_FILE
    if USERS_FILE == _DEFAULT_USERS_FILE:
        USERS_FILE = cfg_path("data/uzytkownicy.json")
    Path(USERS_FILE).parent.mkdir(parents=True, exist_ok=True)
    legacy = Path(cfg_path("uzytkownicy.json"))
    if legacy.exists() and not Path(USERS_FILE).exists():
        legacy.replace(USERS_FILE)

SIDEBAR_MODULES: list[tuple[str, str]] = [
    ("zlecenia", "Zlecenia"),
    ("narzedzia", "Narzędzia"),
    ("maszyny", "Maszyny"),
    ("magazyn", "Magazyn"),
    ("feedback", "Wyślij opinię"),
    ("uzytkownicy", "Użytkownicy"),
    ("ustawienia", "Ustawienia"),
    ("profil", "Profil"),
]

# Domyślny profil użytkownika z rozszerzonymi polami
DEFAULT_USER = {
    "login": "operator",
    "rola": "operator",
    "pin": "1234",
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

def get_tasks_for(login:str):
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
    "read_users",
    "write_users",
    "list_user_ids",
    "find_user_by_pin",
    "get_tasks_for",
    "get_user",
    "save_user",
    "ensure_user_fields",
    "staz_days_for_login",
    "staz_years_floor_for_login",
]
