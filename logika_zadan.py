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

logger = logging.getLogger(__name__)

HISTORY_PATH = os.path.join("data", "zadania_history.json")
TOOL_TASKS_PATH = os.path.join("data", "zadania_narzedzia.json")
_TOOL_TASKS_CACHE: list[dict] | None = None


class ToolTasksError(RuntimeError):
    """Wyjątek dla błędów w strukturze zadania_narzedzia.json."""


def _load_tool_tasks(force: bool = False) -> list[dict]:
    """Ładuje definicje zadań narzędzi z pliku JSON.

    Plik może zawierać maksymalnie 8 typów oraz po 8 statusów na typ.
    Przekroczenie limitu zgłasza :class:`ToolTasksError`.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    global _TOOL_TASKS_CACHE
    if _TOOL_TASKS_CACHE is not None and not force:
        return _TOOL_TASKS_CACHE
    try:
        with open(TOOL_TASKS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"types": []}
    types = data.get("types") or []
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
    _TOOL_TASKS_CACHE = types
    return types


def get_tool_types_list(force: bool = False) -> list[dict]:
    """Zwraca listę dostępnych typów narzędzi.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    return [
        {"id": t.get("id"), "name": t.get("name", t.get("id"))}
        for t in _load_tool_tasks(force=force)
    ]


def _find_type(type_id: str, force: bool = False) -> dict | None:
    for t in _load_tool_tasks(force=force):
        if t.get("id") == type_id:
            return t
    return None


def get_statuses_for_type(type_id: str, force: bool = False) -> list[dict]:
    """Zwraca listę statusów dostępnych dla danego typu.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    typ = _find_type(type_id, force=force)
    if not typ:
        return []
    return [
        {"id": s.get("id"), "name": s.get("name", s.get("id"))}
        for s in (typ.get("statuses") or [])
    ]


def get_tasks_for(type_id: str, status_id: str, force: bool = False) -> list[str]:
    """Zwraca listę zadań dla kombinacji typu i statusu.

    Args:
        force: Gdy ``True`` wymusza ponowne wczytanie pliku, ignorując cache.
    """

    typ = _find_type(type_id, force=force)
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
