# presence_watcher.py
# Prosty watcher nieobecności: po starcie zmiany + grace, jeśli brak online -> tworzy alert.
import os, json, time, traceback
import logging
from datetime import datetime, timezone, timedelta

# Initialize module logger
logger = logging.getLogger(__name__)

try:
    from tkinter import TclError
except ImportError:  # pragma: no cover - tkinter may be absent
    class TclError(Exception):
        pass

try:
    from logger import log_akcja
except ImportError:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)

    def log_akcja(msg: str) -> None:
        logger.info(msg)

def _now():
    return datetime.now(timezone.utc)

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

def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log_akcja(f"[JSON] read error for {path}: {e}")
    except Exception as e:
        log_akcja(f"[JSON] unexpected read error for {path}: {e}")
    return default

def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
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

def _shifts_from_cfg(c):
    p = c.get("presence", {})
    shifts = p.get("shifts", {
        "I": {"start":"06:00", "end":"14:00"},
        "II":{"start":"14:00", "end":"22:00"},
        "III":{"start":"22:00", "end":"06:00"}
    })
    grace = int(p.get("grace_min", 15))
    return shifts, grace

def _active_shift(now_local=None):
    # Prosta determinacja zmiany wg godzin lokalnych; nocna przecina dobę
    if now_local is None:
        now_local = datetime.now()
    h = now_local.hour
    if 6 <= h < 14: return "I"
    if 14 <= h < 22: return "II"
    return "III"

def _today_str(dtobj=None):
    if dtobj is None:
        dtobj = datetime.now()
    return dtobj.strftime("%Y-%m-%d")

def _is_online(login, max_age_sec=None):
    try:
        import presence
        recs, _ = presence.read_presence(max_age_sec=max_age_sec)
        for r in recs:
            if r.get("login")==login:
                return bool(r.get("online"))
    except Exception:
        pass
    return False

def _users_meta():
    meta = _read_json(_path("uzytkownicy.json"), [])
    out = {}
    if isinstance(meta, list):
        for r in meta:
            if isinstance(r, dict) and r.get("login"):
                out[r["login"]] = r
    return out

def _ensure_alert(date_str, shift, login):
    alerts = _read_json(_path("alerts.json"), [])
    key = f"{date_str}_{login}_{shift}"
    for a in alerts:
        if a.get("id")==key:
            return False  # already exists
    now_iso = _now().isoformat()
    alerts.append({
        "id": key,
        "login": login,
        "data": date_str,
        "zmiana": shift,
        "created_at": now_iso,
        "status": "pending",
        "resolution": None,
        "minutes": 0,
        "resolved_by": None,
        "resolved_at": None,
        "note": ""
    })
    _write_json(_path("alerts.json"), alerts)
    return True

def run_check():
    """Sprawdź brak obecności po starcie zmiany + grace i twórz alerty."""
    c = _cfg()
    shifts, grace = _shifts_from_cfg(c)
    now_local = datetime.now()
    active = _active_shift(now_local)
    # start godziny danej zmiany wg configu
    def _parse_hhmm(s):
        try:
            hh,mm = s.split(":")
            return int(hh), int(mm)
        except Exception:
            return 0,0
    start_str = shifts.get(active, {}).get("start", "06:00")
    hh,mm = _parse_hhmm(start_str)
    start_dt = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    # jeśli nocna i minęła północ, dopasuj start do wczoraj
    if active=="III" and now_local.hour < 6:
        start_dt = start_dt - timedelta(days=1)

    # Czekamy aż minie grace
    if now_local < (start_dt + timedelta(minutes=grace)):
        return 0

    users = _users_meta()
    created = 0
    for lg, meta in users.items():
        # tylko użytkownicy przypisani do tej zmiany (meta["zmiana"])
        mshift = str(meta.get("zmiana","")).upper().replace("3","III").replace("2","II").replace("1","I")
        if mshift != active: 
            continue
        if _is_online(lg, max_age_sec=None):
            continue
        if _ensure_alert(_today_str(now_local), active, lg):
            created += 1
    return created

def schedule_watcher(root):
    """Uruchom cykliczny watcher (co 60 s)."""
    if not root:
        return
    def _tick():
        try:
            n = run_check()
            if n:
                log_akcja(f"[ALERTS] utworzono {n} alert(ów) nieobecności")
        except (OSError, ValueError) as e:
            log_akcja(f"[ALERTS] watcher error: {e}")
        except Exception as e:
            log_akcja(
                f"[ALERTS] unexpected watcher error: {e}\n{traceback.format_exc()}"
            )
        finally:
            try:
                root.after(60000, _tick)
            except TclError:
                log_akcja("[ALERTS] watcher scheduling stopped")
            except Exception as e:
                log_akcja(
                    f"[ALERTS] unexpected watcher scheduling error: {e}\n{traceback.format_exc()}"
                )
    _tick()
