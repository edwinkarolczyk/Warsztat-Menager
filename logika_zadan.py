# Wersja pliku: 1.0.0
# Plik: logika_zadan.py
# Zmiany 1.0.0:
# - Pomost między zadaniami a magazynem: zużycie materiałów zdefiniowanych w zadaniu albo z definicji produktu
# - API: consume_for_task(tool_id, task_dict, uzytkownik)
import json
import os
from datetime import datetime
import logging

import logika_magazyn as LM
import bom
import tools

logger = logging.getLogger(__name__)

HISTORY_PATH = os.path.join("data", "zadania_history.json")
TOOL_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOLS_TEMPLATES_CACHE: dict[str, dict] | None = None
DEFAULT_COLLECTION_ID = "default"


class ToolTasksError(RuntimeError):
    """Wyjątek dla błędów w strukturze definicji zadań narzędzi."""


def _read_json_atomic(path: str) -> dict:
    """Odczytaj plik JSON z prostą blokadą."""

    lock_path = path + ".lock"
    lock_f = None
    try:
        lock_f = open(lock_path, "w")
        LM.lock_file(lock_f)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.debug("[WM-DBG] read %s", path)
            return data
    except FileNotFoundError:
        logger.debug("[WM-DBG] missing %s", path)
        return {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("[WM-DBG] cannot read %s: %s", path, e, exc_info=True)
        return {}
    finally:
        if lock_f:
            LM.unlock_file(lock_f)
            lock_f.close()


def _validate_types(types: list[dict], collection_id: str) -> list[dict]:
    if len(types) > 8:
        raise ToolTasksError(
            f"Przekroczono maksymalną liczbę typów (8) w kolekcji {collection_id}"
        )
    seen_types: set[str] = set()
    for typ in types:
        tid = typ.get("id")
        if tid in seen_types:
            raise ToolTasksError(
                f"Duplikat ID typu {tid} w kolekcji {collection_id}"
            )
        seen_types.add(tid)
        statuses = typ.get("statuses") or []
        if len(statuses) > 8:
            raise ToolTasksError(
                f"Przekroczono maksymalną liczbę statusów dla typu {tid}"
            )
        seen_st: set[str] = set()
        for st in statuses:
            sid = st.get("id")
            if sid in seen_st:
                raise ToolTasksError(
                    f"Duplikat ID statusu {sid} w typie {tid}"
                )
            seen_st.add(sid)
    return types


def load_tools_templates(force: bool = False) -> dict[str, dict]:
    """Wczytaj szablony zadań narzędzi."""

    global _TOOLS_TEMPLATES_CACHE
    if _TOOLS_TEMPLATES_CACHE is not None and not force:
        return _TOOLS_TEMPLATES_CACHE

    logger.debug("[WM-DBG] load_tools_templates(force=%s)", force)
    collections: dict[str, dict] = {}
    paths = getattr(tools, "collections_paths", None) or {}
    if paths:
        logger.debug("[WM-DBG] using collections_paths: %s", paths)
        for cid, path in paths.items():
            data = _read_json_atomic(path)
            types = _validate_types(data.get("types") or [], cid)
            collections[cid] = {
                "id": cid,
                "name": data.get("name", cid),
                "types": types,
            }
    else:
        data = _read_json_atomic(TOOL_TASKS_PATH)
        types = _validate_types(data.get("types") or [], DEFAULT_COLLECTION_ID)
        collections[DEFAULT_COLLECTION_ID] = {
            "id": DEFAULT_COLLECTION_ID,
            "name": data.get("name", DEFAULT_COLLECTION_ID),
            "types": types,
        }
    _TOOLS_TEMPLATES_CACHE = collections
    return collections


def get_collections() -> list[dict]:
    templates = load_tools_templates()
    return [
        {"id": c["id"], "name": c.get("name", c["id"])}
        for c in templates.values()
    ]


def get_tool_types(collection_id: str | None = None) -> list[dict]:
    cid = collection_id or DEFAULT_COLLECTION_ID
    coll = load_tools_templates().get(cid)
    if not coll:
        return []
    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in (coll.get("types") or [])
    ]


def get_statuses(collection_id: str | None, type_id: str) -> list[dict]:
    cid = collection_id or DEFAULT_COLLECTION_ID
    coll = load_tools_templates().get(cid)
    if not coll:
        return []
    for t in coll.get("types") or []:
        if t.get("id") == type_id:
            return [
                {"id": s.get("id"), "name": s.get("name", s.get("id"))}
                for s in (t.get("statuses") or [])
            ]
    return []


def get_tasks(collection_id: str | None, type_id: str, status_id: str) -> list[str]:
    cid = collection_id or DEFAULT_COLLECTION_ID
    coll = load_tools_templates().get(cid)
    if not coll:
        return []
    for t in coll.get("types") or []:
        if t.get("id") == type_id:
            for st in t.get("statuses") or []:
                if st.get("id") == status_id:
                    return list(st.get("tasks") or [])
    return []


def should_autocheck(collection_id: str | None, type_id: str, status_id: str) -> bool:
    cid = collection_id or DEFAULT_COLLECTION_ID
    coll = load_tools_templates().get(cid)
    if not coll:
        return False
    for t in coll.get("types") or []:
        if t.get("id") == type_id:
            t_auto = bool(t.get("autocheck"))
            for st in t.get("statuses") or []:
                if st.get("id") == status_id:
                    return bool(st.get("autocheck", t_auto))
    return False


# Zachowanie kompatybilności ze starym API
def get_tool_types_list() -> list[dict]:
    return get_tool_types()


def get_statuses_for_type(type_id: str) -> list[dict]:
    return get_statuses(None, type_id)


def get_tasks_for(type_id: str, status_id: str) -> list[str]:
    return get_tasks(None, type_id, status_id)


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

# ⏹ KONIEC KODU
