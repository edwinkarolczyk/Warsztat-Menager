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

import logika_magazyn as LM
import bom
from config_manager import ConfigManager

logger = logging.getLogger(__name__)
DBG_PREFIX = "[WM-DBG][TASKS]"

HISTORY_PATH = os.path.join("data", "zadania_history.json")
TOOL_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOL_TASKS_CACHE: dict[str, dict] | None = None


class ToolTasksError(RuntimeError):
    """Wyjątek dla błędów w strukturze ``zadania_narzedzia.json``."""


def load_tools_templates(force: bool = False) -> dict[str, dict]:
    """Wczytuje definicje zadań narzędzi z pliku JSON.

    Sprawdza ograniczenia: maksymalnie 8 kolekcji, 8 typów na kolekcję oraz
    8 statusów na typ. Identyfikatory muszą być unikalne w swoich zakresach.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.

    Returns:
        dict: Słownik kolekcji.

    Raises:
        ToolTasksError: Gdy struktura danych jest nieprawidłowa.
    """

    global _TOOL_TASKS_CACHE
    if _TOOL_TASKS_CACHE is not None and not force:
        logger.debug("%s użycie cache", DBG_PREFIX)
        return _TOOL_TASKS_CACHE

    try:
        with open(TOOL_TASKS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raw = {"collections": {}}

    collections = raw.get("collections") or {}
    if not isinstance(collections, dict):
        raise ToolTasksError("Brak sekcji 'collections' w zadania_narzedzia.json")
    if len(collections) > 8:
        raise ToolTasksError("Przekroczono maksymalną liczbę kolekcji (8)")

    coll_ids: set[str] = set()
    out: dict[str, dict] = {}
    for cid, coll in collections.items():
        if cid in coll_ids:
            raise ToolTasksError(f"Powtarzające się id kolekcji: {cid}")
        coll_ids.add(cid)

        types = coll.get("types") or []
        if len(types) > 8:
            raise ToolTasksError(
                f"Przekroczono maksymalną liczbę typów w kolekcji {cid}"
            )

        type_ids: set[str] = set()
        norm_types: list[dict] = []
        for typ in types:
            type_id = typ.get("id")
            if type_id in type_ids:
                raise ToolTasksError(
                    f"Powtarzające się id typu {type_id} w kolekcji {cid}"
                )
            type_ids.add(type_id)

            statuses = typ.get("statuses") or []
            if len(statuses) > 8:
                raise ToolTasksError(
                    f"Przekroczono maksymalną liczbę statusów dla typu {type_id}"
                )

            status_ids: set[str] = set()
            norm_statuses: list[dict] = []
            for status in statuses:
                status_id = status.get("id")
                if status_id in status_ids:
                    raise ToolTasksError(
                        f"Powtarzające się id statusu {status_id} w typie {type_id}"
                    )
                status_ids.add(status_id)
                norm_statuses.append(status)
            norm_types.append({**typ, "statuses": norm_statuses})

        out[cid] = {"name": coll.get("name", cid), "types": norm_types}

    _TOOL_TASKS_CACHE = out
    logger.debug("%s wczytano kolekcje: %s", DBG_PREFIX, list(out))
    return out


def invalidate_cache() -> None:
    """Czyści pamięć podręczną szablonów zadań."""

    global _TOOL_TASKS_CACHE
    _TOOL_TASKS_CACHE = None
    logger.debug("%s cache unieważniony", DBG_PREFIX)


def get_collections(settings: dict) -> list[dict]:
    """Zwraca listę dostępnych kolekcji."""

    enabled = settings.get("tools", {}).get("collections_enabled", []) or []
    templates = load_tools_templates()
    out = []
    for cid, info in templates.items():
        if enabled and cid not in enabled:
            continue
        out.append({"id": cid, "name": info.get("name", cid)})
    logger.debug("%s get_collections -> %s", DBG_PREFIX, [c["id"] for c in out])
    return out


def get_tool_types(collection_id: str, settings: dict) -> list[dict]:
    """Zwraca listę typów narzędzi dla kolekcji."""

    enabled = settings.get("tools", {}).get("collections_enabled", []) or []
    if enabled and collection_id not in enabled:
        logger.debug(
            "%s get_tool_types(%s) -> kolekcja wyłączona",
            DBG_PREFIX,
            collection_id,
        )
        return []
    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types") or []
    out = [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in types
    ]
    logger.debug(
        "%s get_tool_types(%s) -> %s",
        DBG_PREFIX,
        collection_id,
        [t["id"] for t in out],
    )
    return out


def get_statuses(collection_id: str, type_id: str, settings: dict) -> list[dict]:
    """Zwraca listę statusów dla danego typu."""

    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types") or []
    for typ in types:
        if typ.get("id") == type_id:
            statuses = typ.get("statuses") or []
            out = [
                {
                    "id": s.get("id"),
                    "name": s.get("name", s.get("id")),
                    "auto_check_on_entry": bool(s.get("auto_check_on_entry")),
                }
                for s in statuses
            ]
            logger.debug(
                "%s get_statuses(%s,%s) -> %s",
                DBG_PREFIX,
                collection_id,
                type_id,
                [s["id"] for s in out],
            )
            return out
    logger.debug(
        "%s get_statuses(%s,%s) -> []",
        DBG_PREFIX,
        collection_id,
        type_id,
    )
    return []


def get_tasks(
    collection_id: str, type_id: str, status_id: str, settings: dict
) -> list[str]:
    """Zwraca listę zadań dla wskazanego statusu."""

    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types") or []
    for typ in types:
        if typ.get("id") == type_id:
            for status in typ.get("statuses") or []:
                if status.get("id") == status_id:
                    tasks = list(status.get("tasks") or [])
                    logger.debug(
                        "%s get_tasks(%s,%s,%s) -> %s",
                        DBG_PREFIX,
                        collection_id,
                        type_id,
                        status_id,
                        tasks,
                    )
                    return tasks
    logger.debug(
        "%s get_tasks(%s,%s,%s) -> []",
        DBG_PREFIX,
        collection_id,
        type_id,
        status_id,
    )
    return []


def should_autocheck(collection_id: str, status_id: str, settings: dict) -> bool:
    """Określa, czy status wymaga automatycznego sprawdzenia."""

    templates = load_tools_templates()
    coll = templates.get(collection_id, {})
    for typ in coll.get("types") or []:
        for status in typ.get("statuses") or []:
            if status.get("id") == status_id:
                if status.get("auto_check_on_entry"):
                    logger.debug(
                        "%s should_autocheck(%s,%s) -> True (entry)",
                        DBG_PREFIX,
                        collection_id,
                        status_id,
                    )
                    return True
    global_statuses = (
        settings.get("tools", {}).get("auto_check_on_status_global", []) or []
    )
    result = status_id in global_statuses
    logger.debug(
        "%s should_autocheck(%s,%s) -> %s",
        DBG_PREFIX,
        collection_id,
        status_id,
        result,
    )
    return result


def _default_collection() -> str:
    cfg = ConfigManager()
    enabled = cfg.get("tools.collections_enabled", []) or []
    return cfg.get("tools.default_collection", enabled[0] if enabled else "default")


def get_tool_types_list(
    collection: str | None = None, force: bool = False
) -> list[dict]:
    """Zwraca listę typów narzędzi dla danej kolekcji."""

    coll = collection or _default_collection()
    types = load_tools_templates(force=force).get(coll, {}).get("types", [])
    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in types
    ]


def _find_type(
    type_id: str, collection: str | None = None, force: bool = False
) -> dict | None:
    coll = collection or _default_collection()
    for t in load_tools_templates(force=force).get(coll, {}).get("types", []):
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
