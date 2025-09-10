# Plik: logika_magazyn.py
# Wersja pliku: 1.1.0
# Zmiany 1.1.0:
# - Dodano słownik typów w meta.item_types (domyślnie: komponent/półprodukt/materiał)
# - API: get_item_types(), add_item_type(), remove_item_type()
# - Walidacja przy usuwaniu typu (nie usuwa, jeśli typ jest w użyciu)
# - Reszta 1.0.1 bez zmian

import json
import os
from datetime import datetime
from threading import RLock
import logging

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("WM_DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

from config_manager import ConfigManager
from magazyn_io import append_history
try:
    from tkinter import messagebox
except Exception:  # pragma: no cover - środowiska bez GUI
    messagebox = None
try:
    import fcntl

    def lock_file(f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def unlock_file(f):
        fcntl.flock(f, fcntl.LOCK_UN)
except ImportError:  # pragma: no cover - Windows path
    try:
        import msvcrt

        def lock_file(f):
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

        def unlock_file(f):
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
    except ImportError:
        try:
            import portalocker

            def lock_file(f):
                portalocker.lock(f, portalocker.LOCK_EX)

            def unlock_file(f):
                portalocker.unlock(f)
        except ImportError:
            import logging

            logging.warning(
                "Brak bibliotek blokowania plików; operacje mogą być niezabezpieczone"
            )

            def lock_file(_):  # pragma: no cover - brak blokady
                return None

            def unlock_file(_):  # pragma: no cover - brak blokady
                return None

try:
    import logger
    _log_info = getattr(logger, "log_akcja", lambda m: logging.info(m))
    _log_mag = getattr(
        logger, "log_magazyn", lambda a, d: logging.info(f"[MAGAZYN] {a}: {d}")
    )
except Exception:
    def _log_info(msg):
        logging.info(msg)

    def _log_mag(akcja, dane):
        logging.info(f"[MAGAZYN] {akcja}: {dane}")


_CFG = ConfigManager()


MAGAZYN_PATH = "data/magazyn/magazyn.json"
"""Ścieżka do głównego pliku magazynu."""

POLPRODUKTY_PATH = "data/magazyn/polprodukty.json"
"""Ścieżka do pliku półproduktów magazynu."""

_LOCK = RLock()

DEFAULT_ITEM_TYPES = ["komponent", "półprodukt", "materiał"]


def _magazyn_dir() -> str:
    """Zwraca katalog zawierający plik magazynu."""
    return os.path.dirname(MAGAZYN_PATH)


def _ensure_dirs():
    """Tworzy wymagane katalogi dla pliku magazynu."""
    os.makedirs(_magazyn_dir(), exist_ok=True)


def _history_path():
    return os.path.join(_magazyn_dir(), "magazyn_history.json")

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _default_magazyn():
    return {
        "wersja": "1.1.0",
        "items": {},
        "meta": {"updated": _now(), "item_types": list(DEFAULT_ITEM_TYPES)}
    }

def load_magazyn():
    """
    Wczytuje magazyn, a jeśli plik nie istnieje lub struktura jest niekompletna,
    tworzy/naprawia ją i nadpisuje na dysku.
    """
    _ensure_dirs()
    if not os.path.exists(MAGAZYN_PATH):
        _log_info(f"Tworzę nowy magazyn: {MAGAZYN_PATH}")
        save_magazyn(_default_magazyn())

    # wczytaj i AUTONAPRAWY
    try:
        with open(MAGAZYN_PATH, "r", encoding="utf-8") as f:
            mj = json.load(f)
    except Exception as e:
        _log_info(f"Problem z wczytaniem magazynu ({e}) – przywracam domyślny.")
        mj = _default_magazyn()
        save_magazyn(mj)
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
    # order list
    if "order" not in mj["meta"] or not isinstance(mj["meta"].get("order"), list):
        mj["meta"]["order"] = list((mj.get("items") or {}).keys()); fixed = True
    else:
        items_keys = list((mj.get("items") or {}).keys())
        new_order = []
        for iid in mj["meta"]["order"]:
            if iid in items_keys and iid not in new_order:
                new_order.append(iid)
        for iid in items_keys:
            if iid not in new_order:
                new_order.append(iid)
        if new_order != mj["meta"]["order"]:
            mj["meta"]["order"] = new_order
            fixed = True

    # per-item progi_alertow_pct
    items = mj.get("items") or {}
    global_progi = _CFG.get("progi_alertow_pct", [100])
    for it in items.values():
        if "progi_alertow_pct" not in it:
            it["progi_alertow_pct"] = list(global_progi)
            fixed = True

    # uaktualnij timestamp meta
    mj["meta"]["updated"] = _now()
    if fixed:
        _log_info("Naprawiono strukturę magazyn.json (dopisano brakujące klucze).")
        save_magazyn(mj)
    return mj

def save_magazyn(data):
    """Zapisuje magazyn na dysku.

    Operacja korzysta z blokady międzyprocesowej opartej na pliku
    ``.lock`` aby zserializować równoległe zapisy. Blokada jest zawsze
    zwalniana w bloku ``finally``.
    """
    _ensure_dirs()
    data.setdefault("meta", {})["updated"] = _now()
    # sanity: item_types zawsze lista
    if not isinstance(data["meta"].get("item_types"), list):
        data["meta"]["item_types"] = list(DEFAULT_ITEM_TYPES)
    # sanitize order list
    items_keys = list((data.get("items") or {}).keys())
    order = data["meta"].get("order")
    if not isinstance(order, list):
        data["meta"]["order"] = items_keys
    else:
        new_order = [i for i in order if i in items_keys]
        for iid in items_keys:
            if iid not in new_order:
                new_order.append(iid)
        data["meta"]["order"] = new_order
    lock_path = MAGAZYN_PATH + ".lock"
    lock_f = open(lock_path, "w")
    try:
        lock_file(lock_f)
        tmp = MAGAZYN_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                _log_info(f"save_magazyn dump error: {e}")
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                raise
        try:
            os.replace(tmp, MAGAZYN_PATH)
        except Exception as e:
            _log_info(f"save_magazyn replace error: {e}")
            try:
                if os.path.exists(MAGAZYN_PATH):
                    os.remove(MAGAZYN_PATH)
                os.rename(tmp, MAGAZYN_PATH)
            except Exception as e2:
                _log_info(f"save_magazyn rename error: {e2}")
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                raise
    finally:
        unlock_file(lock_f)
        lock_f.close()

def _append_history(*args, **kwargs):
    """Append a history entry with backward-compatible schema.

    Supports both the new API ``(items, item_id, user, op, qty, ctx)`` and a
    legacy single-event dict. Returns the stored/received event with keys
    ``operacja`` and ``ilosc``.
    """

    if len(args) == 1 and isinstance(args[0], dict):
        # Legacy direct-event call used in tests
        return args[0]

    items, item_id, uzytkownik, op, ilosc, *rest = args
    kontekst = rest[0] if rest else kwargs.get("kontekst")

    append_history(items, item_id, uzytkownik, op, ilosc, kontekst or "")

    mapping = {
        "RESERVE": "rezerwacja",
        "UNRESERVE": "zwolnienie",
        "ZW": "zwrot",
        "RW": "zuzycie",
        "PZ": "przyjecie",
        "DEL": "usun",
        "CREATE": "utworz",
    }
    entry = {
        "operacja": mapping.get(op, op.lower()),
        "ilosc": float(ilosc),
    }

    try:
        items[item_id]["historia"][-1] = entry
    except Exception:
        pass
    return entry


def save_polprodukt(record: dict) -> bool:
    """Zapisuje nowy półprodukt do pliku ``POLPRODUKTY_PATH``.

    Tworzy plik, jeśli nie istnieje. Zwraca ``True`` po udanym zapisie,
    ``False`` gdy w pliku znajduje się już rekord o tym samym kodzie/ID.
    Zapis wykonywany jest atomowo przez plik tymczasowy i ``os.replace``.
    """

    kod = str(record.get("kod") or record.get("id") or "").strip()
    if not kod:
        raise ValueError("Record must contain 'kod' or 'id'.")

    data_rec = record.copy()
    data_rec.pop("kod", None)
    data_rec.pop("id", None)
    if "stan" in data_rec:
        data_rec["stan"] = float(data_rec["stan"])

    with _LOCK:
        os.makedirs(os.path.dirname(POLPRODUKTY_PATH), exist_ok=True)
        try:
            with open(POLPRODUKTY_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if not isinstance(data, dict):
                    data = {}
        except FileNotFoundError:
            data = {}
        except Exception:
            data = {}
        if kod in data:
            return False
        data[kod] = data_rec
        tmp = POLPRODUKTY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, POLPRODUKTY_PATH)
        _log_mag("polprodukt_zapisany", {"kod": kod})
        return True


def zapisz_stan_magazynu(mag=None):
    """Zapisuje uproszczone stany magazynu do pliku ``stany.json``.

    ``mag`` może być już wczytanym słownikiem magazynu. Jeśli jest ``None``,
    funkcja sama wczyta dane z dysku. Zapis obejmuje identyfikator, nazwę,
    bieżący stan oraz minimalny poziom (jako ``prog_alert``).
    """

    _ensure_dirs()
    if mag is None:
        mag = load_magazyn()
    items = (mag.get("items") or {}).values()
    out = {}
    for it in items:
        out[it["id"]] = {
            "nazwa": it.get("nazwa", it["id"]),
            "stan": float(it.get("stan", 0)),
            "prog_alert": float(it.get("min_poziom", 0)),
        }
    p = os.path.join(_magazyn_dir(), "stany.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


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
        m = load_magazyn()
        arr = (m.get("meta") or {}).get("item_types") or []
        if any(str(x).strip().lower() == nm.lower() for x in arr):
            return False
        arr.append(nm)
        m["meta"]["item_types"] = arr
        save_magazyn(m)
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
        m = load_magazyn()
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
        save_magazyn(m)
        _log_info(f"[MAGAZYN] Usunięto typ: {nm}")
        _log_mag("typ_usuniety", {"typ": nm, "by": uzytkownik})
        return True

def upsert_item(item):
    """item: {id, nazwa, typ, jednostka, stan, min_poziom} + opcjonalnie rezerwacje, historia"""
    with _LOCK:
        m = load_magazyn()
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
            "progi_alertow_pct": list(
                item.get(
                    "progi_alertow_pct",
                    it.get(
                        "progi_alertow_pct",
                        _CFG.get("progi_alertow_pct", [100]),
                    ),
                )
            ),
            "historia": it.get("historia", [])
        })
        order = m.setdefault("meta", {}).setdefault("order", list(items.keys()))
        if item["id"] not in order:
            order.append(item["id"])
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_info(f"Upsert item {item['id']} ({it['nazwa']})")
        return it


def delete_item(item_id: str, uzytkownik: str = "system", kontekst=None) -> bool:
    """Usuwa element z magazynu.

    Po usunięciu aktualizuje listę ``meta.order`` oraz zapisuje stan
    magazynu. Operacja jest logowana i dopisywana do historii globalnej.

    Args:
        item_id: Identyfikator elementu do usunięcia.
        uzytkownik: Nazwa użytkownika wykonującego operację.
        kontekst: Opcjonalny kontekst operacji.

    Returns:
        ``True`` gdy element usunięto.

    Raises:
        KeyError: Gdy element o podanym identyfikatorze nie istnieje.
    """

    with _LOCK:
        m = load_magazyn()
        items = m.get("items") or {}
        if item_id not in items:
            raise KeyError(f"Brak pozycji {item_id} w magazynie")
        _append_history({"operacja": "usun", "item_id": item_id, "ilosc": 1})
        del items[item_id]
        order = (m.setdefault("meta", {}).get("order") or [])
        m["meta"]["order"] = [iid for iid in order if iid != item_id]
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_mag("usun", {"item_id": item_id, "by": uzytkownik, "ctx": kontekst})
        return True

def zuzyj(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość zużycia musi być > 0")
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            raise KeyError(f"Brak pozycji {item_id} w magazynie")
        dok = float(ilosc)
        if it["stan"] < dok:
            raise ValueError(
                f"Niewystarczający stan {item_id}: {it['stan']} < {dok}"
            )
        it["stan"] -= dok
        _append_history(m["items"], item_id, uzytkownik, "RW", dok, kontekst)
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_mag(
            "zuzycie",
            {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst},
        )
        res = it
    for al in filter(lambda a: a["item_id"] == item_id, sprawdz_progi()):
        _log_mag("prog_alert", al)
    return res

def zwrot(item_id, ilosc, uzytkownik, kontekst=None):
    if ilosc <= 0:
        raise ValueError("Ilość zwrotu musi być > 0")
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            raise KeyError(f"Brak pozycji {item_id} w magazynie")
        dok = float(ilosc)
        it["stan"] += dok
        _append_history(m["items"], item_id, uzytkownik, "ZW", dok, kontekst)
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_mag(
            "zwrot",
            {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst},
        )
        res = it
    for al in filter(lambda a: a["item_id"] == item_id, sprawdz_progi()):
        _log_mag("prog_alert", al)
    return res

def rezerwuj(item_id, ilosc, uzytkownik, kontekst=None):
    if not _CFG.get("magazyn_rezerwacje", True):
        raise RuntimeError("Rezerwacje są wyłączone w konfiguracji")
    if ilosc <= 0:
        raise ValueError("Ilość rezerwacji musi być > 0")
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            raise KeyError(f"Brak pozycji {item_id} w magazynie")
        dok = float(ilosc)
        wolne = float(it.get("stan", 0)) - float(it.get("rezerwacje", 0.0))
        wolne = max(0.0, wolne)
        faktyczne = min(dok, wolne)
        if faktyczne <= 0:
            return 0.0
        it["rezerwacje"] = float(it.get("rezerwacje", 0.0)) + faktyczne
        _append_history(m["items"], item_id, uzytkownik, "RESERVE", faktyczne, kontekst)
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_mag(
            "rezerwacja",
            {"item_id": item_id, "ilosc": faktyczne, "by": uzytkownik, "ctx": kontekst},
        )
        return faktyczne

def zwolnij_rezerwacje(item_id, ilosc, uzytkownik, kontekst=None):
    if not _CFG.get("magazyn_rezerwacje", True):
        raise RuntimeError("Rezerwacje są wyłączone w konfiguracji")
    if ilosc <= 0:
        raise ValueError("Ilość zwolnienia musi być > 0")
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            raise KeyError(f"Brak pozycji {item_id} w magazynie")
        dok = float(ilosc)
        if float(it.get("rezerwacje", 0.0)) < dok:
            raise ValueError(f"Nie można zwolnić {dok}, rezerwacje={it.get('rezerwacje',0.0)}")
        it["rezerwacje"] = float(it.get("rezerwacje", 0.0)) - dok
        _append_history(m["items"], item_id, uzytkownik, "UNRESERVE", dok, kontekst)
        save_magazyn(m)
        zapisz_stan_magazynu(m)
        _log_mag(
            "zwolnienie_rezerwacji",
            {"item_id": item_id, "ilosc": dok, "by": uzytkownik, "ctx": kontekst},
        )
        return it


def rezerwuj_materialy(bom, ilosc):
    """Dekrementuje stany magazynu według BOM.

    Zwraca tuple ``(ok, braki, zlecenie)`` gdzie ``ok`` to bool informujący,
    czy wszystkie materiały były dostępne, ``braki`` to lista słowników
    ``{kod, nazwa, ilosc_potrzebna}``, a ``zlecenie`` zawiera dane
    utworzonego zlecenia zakupów (``{nr, sciezka}``) lub ``None``.
    """

    braki = []
    with _LOCK:
        m = load_magazyn()
        items = m.get("items") or {}
        for kod, info in (bom or {}).items():
            req = float(info.get("ilosc", 0)) * float(ilosc)
            it = items.get(kod)
            if not it:
                braki.append({"kod": kod, "nazwa": kod, "ilosc_potrzebna": req})
                continue
            stan = float(it.get("stan", 0))
            if stan < req:
                braki.append(
                    {
                        "kod": kod,
                        "nazwa": it.get("nazwa", kod),
                        "ilosc_potrzebna": req - stan,
                    }
                )
                zuzyte = stan
                it["stan"] = 0.0
            else:
                zuzyte = req
                it["stan"] = stan - req
            _append_history(items, kod, "system", "RESERVE", zuzyte, "rezerwuj_materialy")
            _log_mag("rezerwacja_materialu", {"item_id": kod, "ilosc": zuzyte})
        save_magazyn(m)
        zapisz_stan_magazynu(m)

    zlec_info = None
    for brak in braki:
        _log_mag(
            "brak_materialu",
            {
                "item_id": brak["kod"],
                "brakuje": float(brak["ilosc_potrzebna"]),
                "zamowiono": True,
            },
        )

    if braki:
        try:
            from logika_zakupy import utworz_zlecenie_zakupow

            nr, sciezka = utworz_zlecenie_zakupow(braki)
            _log_mag("utworzono_zlecenie_zakupow", {"nr": nr})
            zlec_info = {"nr": nr, "sciezka": sciezka}
        except Exception as e:
            _log_mag("blad_zlecenia_zakupow", {"err": str(e)})

    ok = not braki
    return ok, braki, zlec_info

def set_order(order_ids):
    """Ustawia kolejność elementów magazynu zgodnie z listą identyfikatorów."""
    with _LOCK:
        m = load_magazyn()
        items = m.get("items") or {}
        new_order = [iid for iid in order_ids if iid in items]
        for iid in items.keys():
            if iid not in new_order:
                new_order.append(iid)
        m.setdefault("meta", {})["order"] = new_order
        save_magazyn(m)
        return new_order

def lista_items():
    with _LOCK:
        m = load_magazyn()
        items = m.get("items") or {}
        order = (m.get("meta") or {}).get("order") or list(items.keys())
        return [items[i] for i in order if i in items]

def sprawdz_progi():
    """Zwraca listę alertów dla progów procentowych."""
    al = []
    global_progi = _CFG.get("progi_alertow_pct", [100])
    with _LOCK:
        m = load_magazyn()
        for it in (m.get("items") or {}).values():
            stan = float(it.get("stan", 0))
            min_poziom = float(it.get("min_poziom", 0))
            progi = it.get("progi_alertow_pct", global_progi)
            for pct in sorted(set(progi), reverse=True):
                threshold = min_poziom * pct / 100.0
                if stan <= threshold:
                    al.append({
                        "item_id": it["id"],
                        "nazwa": it["nazwa"],
                        "stan": stan,
                        "min_poziom": min_poziom,
                        "prog_pct": pct,
                        "prog_alert": threshold,
                    })
                    break
    return al

def historia_item(item_id, limit=100):
    with _LOCK:
        m = load_magazyn()
        it = (m.get("items") or {}).get(item_id)
        if not it:
            return []
        h = it.get("historia", [])
        return h[-limit:]


def performance_table(limit=None):
    """Zwraca zestawienie operacji magazynu.

    Funkcja agreguje wpisy z pliku historii magazynu i zwraca listę
    słowników zawierających ``item_id``, ``operacja``, sumę ilości oraz
    liczbę wystąpień. Wyniki są posortowane malejąco po sumarycznej
    ilości, co ułatwia analizę najbardziej obciążonych pozycji.

    Args:
        limit: Maksymalna liczba ostatnich wpisów historii do
            uwzględnienia. ``None`` oznacza analizę całej historii.

    Returns:
        list[dict]: Każdy słownik ma klucze ``item_id``, ``operacja``,
        ``ilosc`` i ``liczba``.
    """

    hp = _history_path()
    try:
        with open(hp, "r", encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        return []

    if not isinstance(hist, list):
        return []

    if limit is not None:
        hist = hist[-limit:]

    stats = {}
    for rec in hist:
        item = rec.get("item_id")
        op = rec.get("operacja")
        qty = float(rec.get("ilosc", 0) or 0)
        if not item or not op:
            continue
        key = (item, op)
        if key not in stats:
            stats[key] = {"item_id": item, "operacja": op, "ilosc": 0.0, "liczba": 0}
        stats[key]["ilosc"] += qty
        stats[key]["liczba"] += 1

    return sorted(
        stats.values(),
        key=lambda d: (-d["ilosc"], d["item_id"], d["operacja"]),
    )
