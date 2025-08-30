# Wersja pliku: 1.0.0
# Plik: logika_zadan.py
# Zmiany 1.0.0:
# - Pomost między zadaniami a magazynem: zużycie materiałów zdefiniowanych w zadaniu albo BOM
# - API: consume_for_task(tool_id, task_dict, uzytkownik)
# ⏹ KONIEC KODU

import os

import logika_magazyn as LM
from io_utils import read_json

BOM_DIR = os.path.join("data", "produkty")  # zgodnie z ustaleniami

def _load_bom(product_code):
    path = os.path.join(BOM_DIR, f"{product_code}.json")
    return read_json(path)

def consume_for_task(tool_id: str, task: dict, uzytkownik: str = "system"):
    """
    task może zawierać:
      - task["materials"] = [{"id":"PR-30MM","ilosc":2.0}, ...]
    lub
      - task["product_code"] = "NN123" (pobierze BOM z data/produkty/NN123.json)
    """
    kontekst = f"narzędzie:{tool_id}; zadanie:{task.get('id') or task.get('nazwa')}"
    materials = task.get("materials")
    if not materials:
        code = task.get("product_code")
        if code:
            bom = _load_bom(code)
            if bom and isinstance(bom.get("skladniki"), list):
                materials = [{"id":x["id"], "ilosc":float(x["ilosc"])} for x in bom["skladniki"]]
    if not materials:
        return []  # brak materiałów do konsumpcji

    zuzyte = []
    for poz in materials:
        iid = poz["id"]
        il = float(poz["ilosc"])
        item = LM.get_item(iid)
        wsp = float(item.get("wsp_konwersji", 1.0)) if item else 1.0
        LM.zuzyj(iid, il, uzytkownik=uzytkownik, kontekst=kontekst)
        zuzyte.append({"id": iid, "ilosc": il * wsp})
    return zuzyte
