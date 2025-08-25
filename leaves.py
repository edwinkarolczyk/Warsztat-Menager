# leaves.py
# Prosty dziennik urlopów/L4/spóźnień/NN i agregaty do bilansu
import os, json
from datetime import datetime

def _cfg():
    try:
        cm = globals().get("CONFIG_MANAGER")
        if cm and getattr(cm, "config", None):
            return cm.config or {}
    except Exception:
        pass
    cfg = globals().get("config", {})
    return cfg if isinstance(cfg, dict) else {}

def _path(fname):
    base = None
    try:
        cm = globals().get("CONFIG_MANAGER")
        if cm and getattr(cm, "config_path", None):
            base = os.path.dirname(cm.config_path)
    except Exception:
        pass
    base = base or os.getcwd()
    return os.path.join(base, fname)

def _read(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(path): os.remove(path)
            os.rename(tmp, path)
        except Exception:
            pass

def add_entry(login, type_, date, shift=None, quantity_days=1.0, minutes=0, approved_by=None, note=""):
    """Dodaj wpis do leaves.json"""
    path = _path("leaves.json")
    data = _read(path, [])
    rid = f"leave_{date}_{login}_{type_}"
    data.append({
        "id": rid,
        "login": login,
        "type": type_,  # urlop | l4 | spoznienie | nn | inny
        "date": date,
        "shift": shift,
        "quantity_days": float(quantity_days or 0),
        "minutes": int(minutes or 0),
        "approved_by": approved_by,
        "created_at": datetime.utcnow().isoformat()+"Z",
        "note": (note or "")
    })
    _write(path, data)
    return rid

def read_all():
    return _read(_path("leaves.json"), [])

def totals_for(login, year=None):
    items = read_all()
    out = {"urlop":0.0, "l4":0.0, "spoznienie_min":0, "nn":0.0, "inny":0.0}
    for it in items:
        if login and it.get("login")!=login: 
            continue
        if year:
            y = str(it.get("date",""))[:4]
            if y != str(year): 
                continue
        t = it.get("type")
        if t=="urlop":
            out["urlop"] += float(it.get("quantity_days") or 0.0)
        elif t=="l4":
            out["l4"] += float(it.get("quantity_days") or 0.0)
        elif t=="spoznienie":
            out["spoznienie_min"] += int(it.get("minutes") or 0)
        elif t=="nn":
            out["nn"] += float(it.get("quantity_days") or 0.0)
        else:
            out["inny"] += float(it.get("quantity_days") or 0.0)
    return out

def entitlements_for(login):
    # z uzytkownicy.json + config.leaves.entitlements
    import json, os
    def _read_users():
        p = _path("uzytkownicy.json")
        try:
            if os.path.exists(p):
                with open(p,"r",encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    cfg = _cfg()
    base = {"urlop_rocznie": 26, "l4_limit_rocznie": 33}
    base.update(cfg.get("leaves", {}).get("entitlements", {}))
    for rec in _read_users():
        if isinstance(rec, dict) and rec.get("login")==login:
            ent = rec.get("entitlements")
            if isinstance(ent, dict):
                base.update(ent)
            break
    return base
