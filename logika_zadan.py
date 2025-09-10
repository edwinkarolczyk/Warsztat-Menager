# Wersja pliku: 1.0.0
# Plik: logika_zadan.py
# Zmiany 1.0.0:
# - Pomost między zadaniami a magazynem: zużycie materiałów zdefiniowanych w zadaniu albo z definicji produktu
# - API: consume_for_task(tool_id, task_dict, uzytkownik)
# ⏹ KONIEC KODU

import json
import os
from datetime import datetime
import logging
from typing import Any, Dict

import logika_magazyn as LM
import bom
from config_manager import ConfigManager
import tools_autocheck

logger = logging.getLogger(__name__)

HISTORY_PATH = os.path.join("data", "zadania_history.json")
TOOL_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOL_TASKS_CACHE: dict[str, list[dict]] | None = None
_TOOL_TASKS_MTIME: float | None = None


class ToolTasksError(RuntimeError):
    """Wyjątek dla błędów w strukturze zadania_narzedzia.json."""


def _save_tasks_file(data: dict) -> None:
    """Zapisuje ``data`` do pliku z zachowaniem atomowości."""

    d = os.path.dirname(TOOL_TASKS_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    tmp = TOOL_TASKS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TOOL_TASKS_PATH)


def _load_tool_tasks(force: bool = False) -> dict[str, list[dict]]:
    """Ładuje definicje zadań narzędzi z pliku JSON.

    Dane są zorganizowane w kolekcje → typy → statusy. Brakujący plik jest
    tworzony na podstawie ustawień ``tools.collections_enabled``. Każda
    kolekcja może zawierać maksymalnie 8 typów, a każdy typ do 8 statusów.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    if _TOOL_TASKS_CACHE is not None and not force:
        try:
            mtime = os.path.getmtime(TOOL_TASKS_PATH)
        except OSError:
            mtime = None
        if _TOOL_TASKS_MTIME == mtime:
            return _TOOL_TASKS_CACHE

    cfg = ConfigManager()
    enabled = cfg.get("tools.collections_enabled", []) or []
    default_coll = cfg.get(
        "tools.default_collection", enabled[0] if enabled else "default"
    )

    try:
        with open(TOOL_TASKS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"collections": {cid: {"types": []} for cid in enabled}}
        _save_tasks_file(data)

    if isinstance(data, list):
        types = data
        data = {"collections": {cid: {"types": []} for cid in enabled}}
        data["collections"].setdefault(default_coll, {"types": []})["types"] = types
        _save_tasks_file(data)
    elif "types" in data and "collections" not in data:
        types = data.get("types") or []
        data = {"collections": {cid: {"types": []} for cid in enabled}}
        data["collections"].setdefault(default_coll, {"types": []})["types"] = types
        _save_tasks_file(data)

    collections = data.get("collections") or {}
    if not isinstance(collections, dict):
        raise ToolTasksError("Nieprawidłowa struktura kolekcji")
    changed = False
    for cid in enabled:
        if cid not in collections:
            collections[cid] = {"types": []}
            changed = True
    if changed:
        data["collections"] = collections
        _save_tasks_file(data)

    out: dict[str, list[dict]] = {}
    for cid, coll in collections.items():
        types = coll.get("types") or []
        if len(types) > 8:
            raise ToolTasksError("Przekroczono maksymalną liczbę typów (8)")
        type_ids: set[str] = set()
        for typ in types:
            type_id = typ.get("id")
            if type_id in type_ids:
                raise ToolTasksError(f"Powtarzające się id typu: {type_id}")
            type_ids.add(type_id)

            statuses = typ.get("statuses") or []
            if len(statuses) > 8:
                raise ToolTasksError(
                    f"Przekroczono maksymalną liczbę statusów dla typu {type_id}"
                )

            status_ids: set[str] = set()
            for status in statuses:
                status_id = status.get("id")
                if status_id in status_ids:
                    raise ToolTasksError(
                        f"Powtarzające się id statusu {status_id} w typie {type_id}"
                    )
                status_ids.add(status_id)
        out[cid] = types

    _TOOL_TASKS_CACHE = out
    try:
        _TOOL_TASKS_MTIME = os.path.getmtime(TOOL_TASKS_PATH)
    except OSError:
        _TOOL_TASKS_MTIME = None
    return out


def _default_collection() -> str:
    cfg = ConfigManager()
    enabled = cfg.get("tools.collections_enabled", []) or []
    return cfg.get("tools.default_collection", enabled[0] if enabled else "default")


def get_tool_types_list(
    collection: str | None = None, force: bool = False
) -> list[dict]:
    """Zwraca listę typów narzędzi dla danej kolekcji."""

    coll = collection or _default_collection()
    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in _load_tool_tasks(force=force).get(coll, [])
    ]


def _find_type(
    type_id: str, collection: str | None = None, force: bool = False
) -> dict | None:
    coll = collection or _default_collection()
    for t in _load_tool_tasks(force=force).get(coll, []):
        if t.get("id") == type_id:
            return t
    return None


def get_statuses_for_type(
    type_id: str, collection: str | None = None, force: bool = False
) -> list[dict]:
    """Zwraca listę statusów dostępnych dla danego typu."""

    typ = _find_type(type_id, collection=collection, force=force)
    if not typ:
        return []
    return [
        {"id": s.get("id"), "name": s.get("name", s.get("id"))}
        for s in (typ.get("statuses") or [])
    ]


def get_tasks_for(
    type_id: str,
    status_id: str,
    collection: str | None = None,
    force: bool = False,
) -> list[str]:
    """Zwraca listę zadań dla kombinacji typu i statusu w kolekcji."""

    typ = _find_type(type_id, collection=collection, force=force)
    if not typ:
        return []
    for st in typ.get("statuses") or []:
        if st.get("id") == status_id:
            return list(st.get("tasks") or [])
    return []


def invalidate_cache() -> None:
    """Clear cached tool task definitions and stored mtime."""
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    _TOOL_TASKS_CACHE = None
    _TOOL_TASKS_MTIME = None


def get_collections(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    """Return list of available collections based on *settings*."""

    cfg = settings or ConfigManager()
    if isinstance(cfg, dict):
        getter = lambda k, d=None: cfg.get(k, d)
    else:
        getter = cfg.get
    enabled = getter("tools.collections_enabled", []) or []
    return [{"id": cid, "name": cid} for cid in enabled]


def get_default_collection(
    settings: ConfigManager | Dict[str, Any] | None = None
) -> str:
    """Return identifier of the default collection from *settings*."""

    cfg = settings or ConfigManager()
    if isinstance(cfg, dict):
        getter = lambda k, d=None: cfg.get(k, d)
    else:
        getter = cfg.get
    enabled = getter("tools.collections_enabled", []) or []
    return getter("tools.default_collection", enabled[0] if enabled else "default")


def get_tool_types(
    collection: str | None = None, force: bool = False
) -> list[dict]:
    """Wrapper for :func:`get_tool_types_list` with a simpler name."""

    return get_tool_types_list(collection=collection, force=force)


def get_statuses(
    type_id: str, collection: str | None = None, force: bool = False
) -> list[dict]:
    """Wrapper returning statuses for *type_id* in *collection*."""

    return get_statuses_for_type(type_id, collection=collection, force=force)


def get_tasks(
    type_id: str,
    status_id: str,
    collection: str | None = None,
    force: bool = False,
) -> list[str]:
    """Wrapper returning tasks for *type_id*/*status_id* pair."""

    return get_tasks_for(type_id, status_id, collection=collection, force=force)


def should_autocheck(
    status_id: str,
    collection_id: str,
    config: ConfigManager | Dict[str, Any] | None = None,
) -> bool:
    """Return ``True`` when tasks for *status_id* should be auto-checked."""

    cfg = config
    if cfg is None:
        cfg = ConfigManager().merged
    elif isinstance(cfg, ConfigManager):
        cfg = cfg.merged
    return tools_autocheck.should_autocheck(status_id, collection_id, cfg)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def register_tasks_state(tasks_state, uzytkownik: str = "system"):
    """Rejestruje bieżący stan zadań w pliku historii."""
    d = os.path.dirname(HISTORY_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    entry = {"czas": _now(), "uzytkownik": uzytkownik, "zadania": tasks_state}
    lock_path = HISTORY_PATH + ".lock"
    lock_f = open(lock_path, "w")
    try:
        LM.lock_file(lock_f)
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Nie można odczytać %s: %s", HISTORY_PATH, e, exc_info=True)
                data = []
        else:
            data = []
        data.append(entry)
        tmp = HISTORY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_PATH)
    finally:
        LM.unlock_file(lock_f)
        lock_f.close()
    return entry

def consume_for_task(tool_id: str, task: dict, uzytkownik: str = "system"):
    """
    task może zawierać:
      - task["materials"] = [{"id":"PR-30MM","ilosc":2.0}, ...]
    lub
      - task["product_code"] = "NN123" (obliczy surowce z definicji produktu)
    """
    kontekst = f"narzędzie:{tool_id}; zadanie:{task.get('id') or task.get('nazwa')}"
    surowce: dict[str, float] = {}
    materials = task.get("materials")
    if materials:
        for poz in materials:
            iid = poz["id"]
            il = float(poz["ilosc"])
            surowce[iid] = surowce.get(iid, 0) + il
    else:
        code = task.get("product_code")
        if code:
            bom_pp = bom.compute_bom_for_prd(code, 1)
            for kod_pp, info in bom_pp.items():
                for kod_sr, sr_info in bom.compute_sr_for_pp(
                    kod_pp, info["ilosc"]
                ).items():
                    surowce[kod_sr] = surowce.get(kod_sr, 0) + sr_info["ilosc"]
    if not surowce:
        return []  # brak materiałów do konsumpcji

    zuzyte = []
    for iid, il in surowce.items():
        LM.zuzyj(iid, il, uzytkownik=uzytkownik, kontekst=kontekst)
        zuzyte.append({"id": iid, "ilosc": il})
    return zuzyte
