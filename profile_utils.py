
# Wersja pliku: 1.0.0
# Plik: profile_utils.py
# Pomocnicze: odczyt/zapis uzytkownicy.json + bezpieczne rozszerzanie pól.

import os, json

USERS_FILE = "uzytkownicy.json"

DEFAULT_USER = {
    "login": "operator",
    "rola": "operator",
    "pin": "1234",
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
    """
    data = _load_json(USERS_FILE)
    if data is None:
        users = [DEFAULT_USER.copy()]
        _save_json(USERS_FILE, users)
        return users
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "users" in data and isinstance(data["users"], list):
        return data["users"]
    # Nieznany format -> spróbuj odczytać pole 'users' lub zamienić na listę
    return [DEFAULT_USER.copy()]

def write_users(users):
    """ Zapisuje jako listę (najprościej i spójnie). """
    # dopilnuj podstawowych pól
    norm = []
    for u in users:
        u = dict(u)
        u.setdefault("login", "user")
        u.setdefault("rola", "operator")
        u.setdefault("pin", "")
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

def ensure_user_fields():
    """ Uzupełnia brakujące pola w uzytkownicy.json (nie nadpisuje istniejących). """
    users = read_users()
    changed = False
    for u in users:
        if "preferencje" not in u: u["preferencje"] = {"motyw": "dark", "widok_startowy": "panel"}; changed = True
        if "zadania" not in u: u["zadania"] = []; changed = True
    if changed:
        write_users(users)
