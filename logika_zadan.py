# Wersja pliku: 1.0.0
# Plik: logika_zadan.py
# Zmiany 1.0.0:
# - Pomost między zadaniami a magazynem: zużycie materiałów zdefiniowanych w zadaniu albo z definicji produktu
# - API: consume_for_task(tool_id, task_dict, uzytkownik)
# ⏹ KONIEC KODU

import json
import os
from datetime import datetime

import logika_magazyn as LM
import bom
HISTORY_PATH = os.path.join("data", "zadania_history.json")


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
            except Exception:
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
                for kod_sr, qty in bom.compute_sr_for_pp(kod_pp, info["ilosc"]).items():
                    surowce[kod_sr] = surowce.get(kod_sr, 0) + qty
    if not surowce:
        return []  # brak materiałów do konsumpcji

    zuzyte = []
    for iid, il in surowce.items():
        LM.zuzyj(iid, il, uzytkownik=uzytkownik, kontekst=kontekst)
        zuzyte.append({"id": iid, "ilosc": il})
    return zuzyte
