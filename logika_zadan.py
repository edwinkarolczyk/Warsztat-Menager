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

logger = logging.getLogger(__name__)

HISTORY_PATH = os.path.join("data", "zadania_history.json")
TOOL_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOLS_TEMPLATES_CACHE: dict[str, dict] | None = None


class ToolTasksError(RuntimeError):
    """Wyjątek dla błędów w strukturze zadania_narzedzia.json."""


def load_tools_templates(force: bool = False) -> dict[str, dict]:
    """Wczytaj definicje zadań narzędzi z pliku JSON.

    Dane są zorganizowane w strukturze ``kolekcja → typ → status``. Funkcja
    weryfikuje limity: maksymalnie 8 kolekcji, 8 typów na kolekcję oraz 8
    statusów na typ. Identyfikatory muszą być unikalne w swoich zakresach.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    global _TOOLS_TEMPLATES_CACHE
    if _TOOLS_TEMPLATES_CACHE is not None and not force:
        logger.debug("[WM-DBG][TASKS] użyto cache szablonów")
        return _TOOLS_TEMPLATES_CACHE

    try:
        with open(TOOL_TASKS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.debug(
            "[WM-DBG][TASKS] wczytano szablony z %s", TOOL_TASKS_PATH
        )
    except FileNotFoundError:
        logger.debug(
            "[WM-DBG][TASKS] brak pliku %s, zwracam pustą strukturę",
            TOOL_TASKS_PATH,
        )
        data = {"collections": {}}

    collections: dict[str, dict] = data.get("collections") or {}
    if len(collections) > 8:
        raise ToolTasksError("Przekroczono maksymalną liczbę kolekcji (8)")

    out: dict[str, dict] = {}
    for cid, coll in collections.items():
        if cid in out:
            raise ToolTasksError(f"Powtarzające się id kolekcji: {cid}")
        types = coll.get("types") or []
        if len(types) > 8:
            raise ToolTasksError(
                f"Przekroczono maksymalną liczbę typów w kolekcji {cid}"
            )
        type_ids: set[str] = set()
        for typ in types:
            tid = typ.get("id")
            if tid in type_ids:
                raise ToolTasksError(
                    f"Powtarzające się id typu {tid} w kolekcji {cid}"
                )
            type_ids.add(tid)
            statuses = typ.get("statuses") or []
            if len(statuses) > 8:
                raise ToolTasksError(
                    f"Przekroczono maksymalną liczbę statusów dla typu {tid}"
                )
            status_ids: set[str] = set()
            for st in statuses:
                sid = st.get("id")
                if sid in status_ids:
                    raise ToolTasksError(
                        f"Powtarzające się id statusu {sid} w typie {tid}"
                    )
                status_ids.add(sid)
        out[cid] = coll

    _TOOLS_TEMPLATES_CACHE = out
    return out


def invalidate_cache() -> None:
    """Resetuje wewnętrzny cache szablonów."""

    global _TOOLS_TEMPLATES_CACHE
    _TOOLS_TEMPLATES_CACHE = None
    logger.debug("[WM-DBG][TASKS] cache unieważniony")


def _coerce_settings(
    settings: ConfigManager | Dict[str, Any] | None,
) -> Dict[str, Any]:
    if settings is None:
        return ConfigManager().merged
    if isinstance(settings, ConfigManager):
        return settings.merged
    return settings


def get_collections(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    """Zwróć listę dostępnych kolekcji zgodnie z konfiguracją."""

    cfg = _coerce_settings(settings)
    enabled = cfg.get("tools", {}).get("collections_enabled", []) or []
    templates = load_tools_templates()
    result = []
    for cid in enabled:
        coll = templates.get(cid, {})
        name = coll.get("name", cid)
        result.append({"id": cid, "name": name})
    logger.debug("[WM-DBG][TASKS] kolekcje: %s", result)
    return result


def get_default_collection(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> str:
    cfg = _coerce_settings(settings)
    enabled = cfg.get("tools", {}).get("collections_enabled", []) or []
    default = cfg.get("tools", {}).get(
        "default_collection", enabled[0] if enabled else "default"
    )
    logger.debug("[WM-DBG][TASKS] domyślna kolekcja: %s", default)
    return default


def get_tool_types(
    collection_id: str,
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types", [])
    result = [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in types
    ]
    logger.debug(
        "[WM-DBG][TASKS] typy dla %s: %s", collection_id, result
    )
    return result


def get_statuses(
    collection_id: str,
    type_id: str,
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types", [])
    for typ in types:
        if typ.get("id") == type_id:
            statuses = [
                {
                    "id": s.get("id"),
                    "name": s.get("name", s.get("id")),
                    "auto_check_on_entry": bool(s.get("auto_check_on_entry")),
                }
                for s in (typ.get("statuses") or [])
            ]
            logger.debug(
                "[WM-DBG][TASKS] statusy dla %s/%s: %s",
                collection_id,
                type_id,
                statuses,
            )
            return statuses
    logger.debug(
        "[WM-DBG][TASKS] brak statusów dla %s/%s", collection_id, type_id
    )
    return []


def get_tasks(
    collection_id: str,
    type_id: str,
    status_id: str,
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[str]:
    templates = load_tools_templates()
    types = templates.get(collection_id, {}).get("types", [])
    for typ in types:
        if typ.get("id") == type_id:
            for st in typ.get("statuses") or []:
                if st.get("id") == status_id:
                    tasks = list(st.get("tasks") or [])
                    logger.debug(
                        "[WM-DBG][TASKS] zadania dla %s/%s/%s: %s",
                        collection_id,
                        type_id,
                        status_id,
                        tasks,
                    )
                    return tasks
    logger.debug(
        "[WM-DBG][TASKS] brak zadań dla %s/%s/%s",
        collection_id,
        type_id,
        status_id,
    )
    return []


def should_autocheck(
    collection_id: str,
    status_id: str,
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> bool:
    cfg = _coerce_settings(settings)
    templates = load_tools_templates()
    coll = templates.get(collection_id, {})
    for typ in coll.get("types", []):
        for st in typ.get("statuses") or []:
            if st.get("id") == status_id:
                flag = st.get("auto_check_on_entry")
                if flag is not None:
                    res = bool(flag)
                    logger.debug(
                        "[WM-DBG][TASKS] autocheck %s/%s -> %s (entry)",
                        collection_id,
                        status_id,
                        res,
                    )
                    return res
    statuses = cfg.get("tools", {}).get("auto_check_on_status_global", [])
    res = status_id in statuses
    logger.debug(
        "[WM-DBG][TASKS] autocheck %s/%s -> %s (global)",
        collection_id,
        status_id,
        res,
    )
    return res


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
