
# Wersja pliku: 1.0.0
# Plik: profile_utils.py
# Pomocnicze: odczyt/zapis uzytkownicy.json + bezpieczne rozszerzanie pól.

import os, json

USERS_FILE = "uzytkownicy.json"

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
    "zadania": []
}

def _load_json(path):
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def read_users():
    """
    Obsługuje 2 formaty:
    - lista użytkowników: [ {...}, {...} ]
    - dict z kluczem "users": {"users":[...]}
    Przy braku pliku – tworzy z DEFAULT_USER.
    Po odczycie uzupełnia brakujące pola przez ``ensure_user_fields``.
    """
    data = _load_json(USERS_FILE)
    if data is None:
        users = [DEFAULT_USER.copy()]
        _save_json(USERS_FILE, users)
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
        norm.append(u)
    return _save_json(USERS_FILE, norm)

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
    if changed:
        _save_json(USERS_FILE, users)
    return users
