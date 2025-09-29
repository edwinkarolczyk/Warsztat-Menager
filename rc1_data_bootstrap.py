# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json
ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "config.json")
PAYLOADS = {
    "warehouse.stock_source": [], "bom.file": [],
    "tools.types_file": [], "tools.statuses_file": [], "tools.task_templates_file": []
}
def _load(): 
    try: return json.load(open(CONFIG_PATH,"r",encoding="utf-8"))
    except: return {}
def _save(cfg): 
    try: json.dump(cfg, open(CONFIG_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e: print(f"[RC1][bootstrap] config save error: {e}")
def _n(p): 
    return os.path.normpath(str(p).strip().strip('"').strip("'")) if p else None
def _mkdirs(path): os.makedirs(os.path.dirname(path), exist_ok=True)
def _write_if_missing(path, payload):
    if not os.path.exists(path):
        _mkdirs(path); json.dump(payload, open(path,"w",encoding="utf-8"), ensure_ascii=False, indent=2); return True
    return False
def _ask(title,msg):
    try:
        import tkinter as tk; from tkinter import messagebox
        r=tk.Tk(); r.withdraw(); a=messagebox.askyesno(title,msg); r.destroy(); return bool(a)
    except: return True
def _get(d, dotted):
    cur=d
    for part in dotted.split("."):
        if not isinstance(cur,dict) or part not in cur: return None
        cur=cur[part]
    return cur
def _set(d, dotted, val):
    cur=d
    parts=dotted.split(".")
    for p in parts[:-1]: cur=cur.setdefault(p,{})
    cur[parts[-1]]=val
def _set_bom_aliases(cfg, path):
    _set(cfg,"bom.file",path); cfg.setdefault("bom",{})["file"]=path; cfg["bom.file"]=path
def _paths_base(cfg):
    paths = cfg.get("paths") if isinstance(cfg.get("paths"),dict) else {}
    data_root = _n(paths.get("data_root")) or _n(cfg.get("data_root"))
    wh = _n(paths.get("warehouse_dir")) or (os.path.join(data_root,"magazyn") if data_root else None)
    pr = _n(paths.get("products_dir"))  or (os.path.join(data_root,"produkty") if data_root else None)
    tl = _n(paths.get("tools_dir"))     or (os.path.join(data_root,"narzedzia") if data_root else None)
    return {
        "warehouse_dir": wh or os.path.join(ROOT,"data","magazyn"),
        "products_dir":  pr or os.path.join(ROOT,"data","produkty"),
        "tools_dir":     tl or os.path.join(ROOT,"data","narzedzia"),
    }
def ensure_data_files():
    cfg=_load(); base=_paths_base(cfg); changed=False; created=[]
    want={
        "warehouse.stock_source": os.path.join(base["warehouse_dir"],"magazyn.json"),
        "bom.file":               os.path.join(base["products_dir"],"bom.json"),
        "tools.types_file":       os.path.join(base["tools_dir"],"typy_narzedzi.json"),
        "tools.statuses_file":    os.path.join(base["tools_dir"],"statusy_narzedzi.json"),
        "tools.task_templates_file": os.path.join(base["tools_dir"],"szablony_zadan.json"),
    }
    for key, fb in want.items():
        cur=_n(_get(cfg,key))
        if key=="bom.file" and not cur:
            cur=_n(cfg.get("bom.file")) or _n(cfg.get("bom",{}).get("file"))
        if cur:
            if not os.path.exists(cur):
                if _ask("Brak pliku danych", f"Nie znaleziono pliku:\n{cur}\n\nUtworzyć pusty plik w tej lokalizacji?"):
                    if _write_if_missing(cur, PAYLOADS[key]): created.append(cur)
            if key=="bom.file": _set_bom_aliases(cfg,cur); changed=True
        else:
            tgt=fb
            if _write_if_missing(tgt, PAYLOADS[key]): created.append(tgt)
            if key=="bom.file": _set_bom_aliases(cfg,tgt)
            else: _set(cfg,key,tgt)
            changed=True
    if changed: _save(cfg)
    print("[RC1][bootstrap] Utworzono pliki:" if created else "[RC1][bootstrap] Wszystkie wymagane pliki istnieją.")
    for p in created: print("  -", p)
try: ensure_data_files()
except Exception as e: print(f"[RC1][bootstrap] ERROR: {e}")
if __name__=="__main__": ensure_data_files()
