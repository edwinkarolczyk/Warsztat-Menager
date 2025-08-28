# Plik: logika_magazyn.py
# Wersja pliku: 1.1.0
# Zmiany 1.1.0:
# - Dodano słownik typów w meta.item_types (domyślnie: komponent/półprodukt/materiał)
# - API: get_item_types(), add_item_type(), remove_item_type()
# - Walidacja przy usuwaniu typu (nie usuwa, jeśli typ jest w użyciu)
# - Reszta 1.0.1 bez zmian

import json
import os
from contextlib import contextmanager, nullcontext
from datetime import datetime
from threading import RLock
import fcntl

try:
    import logger
    _log_info = getattr(logger, "log_akcja", lambda m: print(f"[INFO] {m}"))
    _log_mag = getattr(logger, "log_magazyn", lambda a, d: print(f"[MAGAZYN] {a}: {d}"))
except Exception:
    def _log_info(msg): print(f"[INFO] {msg}")
    def _log_mag(akcja, dane): print(f"[MAGAZYN] {akcja}: {dane}")

MAGAZYN_PATH = os.path.join("data", "magazyn.json")
MAGAZYN_LOCK_PATH = MAGAZYN_PATH + ".lock"
_LOCK = RLock()

DEFAULT_ITEM_TYPES = ["komponent", "półprodukt", "materiał"]

def _ensure_dirs():
    d = os.path.dirname(MAGAZYN_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _default_magazyn():
    return {
        "wersja": "1.1.0",
        "items": {},
        "meta": {"updated": _now(), "item_types": list(DEFAULT_ITEM_TYPES)}
    }


@contextmanager
def _file_lock():
    fd = open(MAGAZYN_LOCK_PATH, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()

def load_magazyn(use_lock=True):
    """
    Wczytuje magazyn, a jeśli plik nie istnieje lub struktura jest niekompletna,
    tworzy/naprawia ją i nadpisuje na dysku.
    """
    _ensure_dirs()
    if not os.path.exists(MAGAZYN_PATH):
        _log_info(f"Tworzę nowy magazyn: {MAGAZYN_PATH}")
        save_magazyn(_default_magazyn(), use_lock=use_lock)

    # wczytaj i AUTONAPRAWY
    try:
        with open(MAGAZYN_PATH, "r", encoding="utf-8") as f:
            mj = json.load(f)
    except Exception as e:
        _log_info(f"Problem z wczytaniem magazynu ({e}) – przywracam domyślny.")
        mj = _default_magazyn()
        save_magazyn(mj, use_lock=use_lock)
        return mj

    fixed = False
    if not isinstance(mj, dict):
        mj = _default_magazyn(); fixed = True
    if "items" not in mj or not isinstance(mj.get("items"), dict):
        mj["items"] = {}; fixed = True
    if "meta" not in mj or not isinstance(mj.get("meta"), dict):
        mj["meta"] = {}; fixed = True
    # item_types
    if "item_types" not in mj["meta"] or not isinstance(mj["meta"].get("item_types"), list):
        mj["meta"]["item_types"] = list(DEFAULT_ITEM_TYPES); fixed = True

    # uaktualnij timestamp meta
    mj["meta"]["updated"] = _now()
    if fixed:
        _log_info("Naprawiono strukturę magazyn.json (dopisano brakujące klucze).")
        save_magazyn(mj, use_lock=use_lock)
    return mj

def save_magazyn(data, use_lock=True):
    """Zapisuje strukturę magazynu na dysku.

    Operacja jest chroniona prostą blokadą plikową, aby uniknąć
    równoległego zapisu. Blokada jest zawsze zwalniana w klauzuli
    ``finally``.
    """
    _ensure_dirs()
    data.setdefault("meta", {})["updated"] = _now()
    # sanity: item_types zawsze lista
    if not isinstance(data["meta"].get("item_types"), list):
        data["meta"]["item_types"] = list(DEFAULT_ITEM_TYPES)
    ctx = _file_lock() if use_lock else nullcontext()
    with ctx:
        tmp = MAGAZYN_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, MAGAZYN_PATH)

def _history_entry(typ_op, item_id, ilosc, uzytkownik, kontekst=None):
    return {
        "czas": _now(),
        "operacja": typ_op,
        "item_id": item_id,
        "ilosc": float(ilosc),
        "uzytkownik": uzytkownik or "system",
        "kontekst": kontekst or ""
    }

def get_item(item_id):
    with _LOCK:
        m = load_magazyn()
        return (m.get("items") or {}).get(item_id)

def get_item_types():
    with _LOCK:
        m = load_magazyn()
        t = (m.get("meta") or {}).get("item_types") or []
        # porządek bez duplikatów (case-insensitive)
        seen = set(); out = []
        for x in t:
            k = str(x).strip().lower()
            if k and k not in seen:
                seen.add(k); out.append(str(x).strip())
        if not out:
            out = list(DEFAULT_ITEM_TYPES)
        return out

def add_item_type(nazwa: str, uzytkownik: str = "system") -> bool:
    """
    Dodaje nowy typ do meta.item_types. Zwraca True, gdy dodano; False, gdy już był.
    """
    nm = str(nazwa or "").strip()
    if not nm:
        raise ValueError("Nazwa typu nie może być pusta.")
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            arr = (m.get("meta") or {}).get("item_types") or []
            if any(str(x).strip().lower() == nm.lower() for x in arr):
                return False
            arr.append(nm)
            m["meta"]["item_types"] = arr
            save_magazyn(m, use_lock=False)
            _log_info(f"[MAGAZYN] Dodano typ: {nm}")
            _log_mag("typ_dodany", {"typ": nm, "by": uzytkownik})
            return True

def remove_item_type(nazwa: str, uzytkownik: str = "system") -> bool:
    """
    Usuwa typ z meta.item_types. Nie usuwa, jeśli typ jest w użyciu przez jakikolwiek item.
    Zwraca True, gdy usunięto; False, gdy nie było lub w użyciu.
    """
    nm = str(nazwa or "").strip()
    if not nm:
        return False
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            # blokada: typ w użyciu
            for it in (m.get("items") or {}).values():
                if str(it.get("typ","")).strip().lower() == nm.lower():
                    # w użyciu – nie ruszamy
                    return False
            arr = (m.get("meta") or {}).get("item_types") or []
            new_arr = [x for x in arr if str(x).strip().lower() != nm.lower()]
            if len(new_arr) == len(arr):
                return False
            m["meta"]["item_types"] = new_arr
            save_magazyn(m, use_lock=False)
            _log_info(f"[MAGAZYN] Usunięto typ: {nm}")
            _log_mag("typ_usuniety", {"typ": nm, "by": uzytkownik})
            return True

def upsert_item(item):
    """item: {id, nazwa, typ, jednostka, stan, min_poziom} + opcjonalnie rezerwacje, historia"""
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            items = m.setdefault("items", {})
            it = items.setdefault(item["id"], {})
            it.update({
                "id": item["id"],
                "nazwa": item.get("nazwa", it.get("nazwa", "")),
                "typ": item.get("typ", it.get("typ", "komponent")),
                "jednostka": item.get("jednostka", it.get("jednostka", "szt")),
                "stan": float(item.get("stan", it.get("stan", 0))),
                "min_poziom": float(item.get("min_poziom", it.get("min_poziom", 0))),
                "rezerwacje": float(item.get("rezerwacje", it.get("rezerwacje", 0))),
                "historia": it.get("historia", [])
            })
            save_magazyn(m, use_lock=False)
            _log_info(f"Upsert item {item['id']} ({it['nazwa']})")
            return it

def zuzyj(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość zużycia musi być > 0")
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            it = (m.get("items") or {}).get(item_id)
            if not it:
                raise KeyError(f"Brak pozycji {item_id} w magazynie")
            dok = float(ilosc)
            if it["stan"] < dok:
                raise ValueError(f"Niewystarczający stan {item_id}: {it['stan']} < {dok}")
            it["stan"] -= dok
            it["historia"].append(_history_entry("zuzycie", item_id, dok, uzytkownik, kontekst))
            save_magazyn(m, use_lock=False)
            _log_mag("zuzycie", {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst})
            return it

def zwrot(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość zwrotu musi być > 0")
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            it = (m.get("items") or {}).get(item_id)
            if not it:
                raise KeyError(f"Brak pozycji {item_id} w magazynie")
            dok = float(ilosc)
            it["stan"] += dok
            it["historia"].append(_history_entry("zwrot", item_id, dok, uzytkownik, kontekst))
            save_magazyn(m, use_lock=False)
            _log_mag("zwrot", {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst})
            return it

def rezerwuj(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość rezerwacji musi być > 0")
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            it = (m.get("items") or {}).get(item_id)
            if not it:
                raise KeyError(f"Brak pozycji {item_id} w magazynie")
            dok = float(ilosc)
            wolne = float(it.get("stan", 0)) - float(it.get("rezerwacje", 0.0))
            if wolne < dok:
                raise ValueError(f"Za mało wolnego (stan - rezerwacje) dla {item_id}")
            it["rezerwacje"] = float(it.get("rezerwacje", 0.0)) + dok
            it["historia"].append(_history_entry("rezerwacja", item_id, dok, uzytkownik, kontekst))
            save_magazyn(m, use_lock=False)
            _log_mag("rezerwacja", {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst})
            return it

def zwolnij_rezerwacje(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość zwolnienia musi być > 0")
    with _LOCK:
        with _file_lock():
            m = load_magazyn(use_lock=False)
            it = (m.get("items") or {}).get(item_id)
            if not it:
                raise KeyError(f"Brak pozycji {item_id} w magazynie")
            dok = float(ilosc)
            if float(it.get("rezerwacje", 0.0)) < dok:
                raise ValueError(f"Nie można zwolnić {dok}, rezerwacje={it.get('rezerwacje',0.0)}")
            it["rezerwacje"] = float(it.get("rezerwacje", 0.0)) - dok
            it["historia"].append(_history_entry("zwolnienie_rezerwacji", item_id, dok, uzytkownik, kontekst))
            save_magazyn(m, use_lock=False)
            _log_mag("zwolnienie_rezerwacji", {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst})
            return it

def lista_items():
    with _LOCK:
        m = load_magazyn()
        return list((m.get("items") or {}).values())

def sprawdz_progi():
    """Zwraca listę alertów: {item_id, nazwa, stan, min_poziom} gdzie stan <= min_poziom."""
    al = []
    with _LOCK:
        m = load_magazyn()
        for it in (m.get("items") or {}).values():
            if float(it.get("stan", 0)) <= float(it.get("min_poziom", 0)):
                al.append({
                    "item_id": it["id"], "nazwa": it["nazwa"],
                    "stan": float(it.get("stan", 0)), "min_poziom": float(it.get("min_poziom", 0))
                })
    return al

def historia_item(item_id, limit=100):
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            return []
        h = it.get("historia", [])
        return h[-limit:]
