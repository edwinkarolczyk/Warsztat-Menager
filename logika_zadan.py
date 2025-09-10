# Wersja pliku: 1.0.0
# Plik: logika_zadan.py
# Zmiany 1.0.0:
# - Pomost między zadaniami a magazynem: zużycie materiałów zdefiniowanych w zadaniu albo z definicji produktu
# - API: consume_for_task(tool_id, task_dict, uzytkownik)
# ⏹ KONIEC KODU

import os, json, threading

_CACHE_LOCK = threading.RLock()
_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOL_TASKS_CACHE = None
_TOOL_TASKS_MTIME = None

import logging
from datetime import datetime
from typing import Any, Dict

import logika_magazyn as LM
import bom
from config_manager import ConfigManager
import tools_autocheck

logger = logging.getLogger(__name__)

# Backward compatibility for external modules
TOOL_TASKS_PATH = _TASKS_PATH
HISTORY_PATH = os.path.join("data", "zadania_history.json")


def _safe_load() -> dict:
    try:
        with open(_TASKS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WM-DBG][NARZ][WARN] Nie można odczytać {_TASKS_PATH}: {exc}")
        return {}


def _ensure_cache() -> None:
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    with _CACHE_LOCK:
        try:
            mtime = os.path.getmtime(_TASKS_PATH)
        except OSError:
            mtime = None
        if _TOOL_TASKS_CACHE is not None and _TOOL_TASKS_MTIME == mtime:
            return
        data = _safe_load() or {}
        collections = data.get("collections") or {}
        _TOOL_TASKS_CACHE = {
            cid: coll.get("types") or [] for cid, coll in collections.items()
        }
        _TOOL_TASKS_MTIME = mtime
        print(f"[WM-DBG][NARZ] Przeładowano definicje zadań (mtime={mtime})")


def _default_collection() -> str:
    cfg = ConfigManager()
    enabled = cfg.get("tools.collections_enabled", []) or []
    return cfg.get("tools.default_collection", enabled[0] if enabled else "default")


def invalidate_cache():
    global _TOOL_TASKS_CACHE, _TOOL_TASKS_MTIME
    with _CACHE_LOCK:
        _TOOL_TASKS_CACHE = None
        _TOOL_TASKS_MTIME = None
        print("[WM-DBG][NARZ] Cache zadań wyczyszczony.")


def get_collections(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> list[dict]:
    _ensure_cache()
    return [{"id": cid, "name": cid} for cid in (_TOOL_TASKS_CACHE or {}).keys()]


def get_default_collection(
    settings: ConfigManager | Dict[str, Any] | None = None,
) -> str:
    cfg = settings or ConfigManager()
    getter = cfg.get
    enabled = getter("tools.collections_enabled", []) or []
    return getter("tools.default_collection", enabled[0] if enabled else "default")


def get_tool_types(collection: str | None = None) -> list[dict]:
    _ensure_cache()
    coll = collection or _default_collection()
    tasks = _TOOL_TASKS_CACHE or {}
    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in tasks.get(coll, [])
    ]


def get_statuses(type_id: str, collection: str | None = None) -> list[dict]:
    _ensure_cache()
    coll = collection or _default_collection()
    tasks = _TOOL_TASKS_CACHE or {}
    for t in tasks.get(coll, []):
        if t.get("id") == type_id:
            return [
                {"id": s.get("id"), "name": s.get("name", s.get("id"))}
                for s in (t.get("statuses") or [])
            ]
    return []


def get_tasks(type_id: str, status_id: str, collection: str | None = None) -> list[str]:
    _ensure_cache()
    coll = collection or _default_collection()
    tasks = _TOOL_TASKS_CACHE or {}
    for t in tasks.get(coll, []):
        if t.get("id") == type_id:
            for st in t.get("statuses") or []:
                if st.get("id") == status_id:
                    return list(st.get("tasks") or [])
    return []


def should_autocheck(
    status_id: str,
    collection_id: str,
    config: ConfigManager | Dict[str, Any] | None = None,
) -> bool:
    _ensure_cache()
    cfg = config
    if cfg is None:
        cfg = ConfigManager().merged
    elif isinstance(cfg, ConfigManager):
        cfg = cfg.merged
    return tools_autocheck.should_autocheck(status_id, collection_id, cfg)


get_tool_types_list = get_tool_types
get_statuses_for_type = get_statuses


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
                logger.warning(
                    "Nie można odczytać %s: %s", HISTORY_PATH, e, exc_info=True
                )
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
