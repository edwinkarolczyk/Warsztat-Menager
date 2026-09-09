# version: 1.1
# presence.py (enhanced)
import os, json, time, tempfile, platform, atexit, traceback, threading
import logging
from datetime import datetime, timezone

from config_manager import ConfigManager

logger = logging.getLogger(__name__)

config = {}
config_path = None


def set_config(cfg=None, cfg_path=None):
    """Configure presence module with plain dict and optional path."""
    global config, config_path
    if isinstance(cfg, dict):
        config = cfg
    if cfg_path:
        config_path = cfg_path

try:
    from tkinter import TclError
except ImportError:  # pragma: no cover
    class TclError(Exception):
        pass

try:
    from logger import log_akcja
except ImportError:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)

    def log_akcja(msg: str) -> None:
        logger.info(msg)

_atexit_handler = None
_session_lock = threading.RLock()
_session_stop: threading.Event | None = None
_session_thread: threading.Thread | None = None
_session_login = ""
_session_role = ""


def _now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_cfg():
    return config if isinstance(config, dict) else {}


def _cfg_dir():
    try:
        cfg = ConfigManager()
        data_root = cfg.path_data()
        if not os.path.isdir(data_root) and os.path.isdir("data"):
            raise FileNotFoundError("Configured data root missing.")
        return data_root
    except Exception:
        if config_path:
            return os.path.dirname(config_path)
        return os.getcwd()


def _presence_path():
    base = _cfg_dir()
    return os.path.join(base, "presence.json")


def _atomic_write(path, data_dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="presence_", suffix=".tmp", dir=os.path.dirname(path) or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        LOCK_PATH = path + ".lock"
        with open(LOCK_PATH, "w", encoding="utf-8") as f_lock:
            f_lock.write(str(time.time()))
        try:
            try:
                os.replace(tmp_path, path)
            except OSError as e:
                logger.exception("os.replace failed for %s: %s", path, e)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                    os.rename(tmp_path, path)
                except OSError:
                    logger.exception("rename fallback failed for %s", path)
        finally:
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.exception("cleanup failed for %s", tmp_path)


def _read_all():
    path = _presence_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
            if isinstance(d, dict):
                return d
        except (OSError, json.JSONDecodeError):
            logger.exception("reading presence file failed")
    return {}


def _stop_background_session(*, mark_logout: bool = False, login: str = "", role: str = "") -> None:
    global _session_stop, _session_thread, _session_login, _session_role
    with _session_lock:
        stop = _session_stop
        active_login = _session_login
        active_role = _session_role
        _session_stop = None
        _session_thread = None
        _session_login = ""
        _session_role = ""
        if stop is not None:
            stop.set()
    if mark_logout and (login or active_login):
        try:
            _heartbeat_write(login or active_login, role or active_role, logout=True)
        except Exception:
            logger.exception("background session logout failed")


def _heartbeat_write(login, role=None, machine=None, logout=False):
    if not login:
        return False
    path = _presence_path()
    data = _read_all()
    if not machine:
        try:
            machine = platform.node()
        except OSError:
            logger.exception("platform.node failed")
            machine = "unknown"
    key = f"{login}@{machine}"
    data[key] = {
        "login": login,
        "role": role or "",
        "machine": machine,
        "ts": _now_utc_iso(),
        "logout": bool(logout),
    }
    _atomic_write(path, data)
    return True


def heartbeat(login, role=None, machine=None, logout=False):
    """Jednorazowy zapis bicia serca. logout=True kończy aktywną sesję."""
    if logout:
        with _session_lock:
            if _session_login and str(_session_login).casefold() == str(login or "").casefold():
                stop = _session_stop
                if stop is not None:
                    stop.set()
    return _heartbeat_write(login, role, machine, logout)


def start_session(login, role=None, interval_sec=None):
    """Uruchom niezależny od widoku GUI heartbeat aktywnej sesji WM."""
    global _session_stop, _session_thread, _session_login, _session_role
    login_text = str(login or "").strip()
    if not login_text:
        return
    if interval_sec is None:
        try:
            interval_sec = int(_get_cfg().get("presence", {}).get("heartbeat_sec", 30))
        except Exception:
            interval_sec = 30
    interval_sec = max(5, int(interval_sec))

    _stop_background_session(mark_logout=False)
    stop = threading.Event()
    with _session_lock:
        _session_stop = stop
        _session_login = login_text
        _session_role = str(role or "")

    try:
        _heartbeat_write(login_text, role, logout=False)
    except Exception:
        logger.exception("initial session heartbeat failed")

    def _worker():
        while not stop.wait(interval_sec):
            try:
                _heartbeat_write(login_text, role, logout=False)
            except Exception:
                logger.exception("background heartbeat failed")

    thread = threading.Thread(target=_worker, name="wm-presence-heartbeat", daemon=True)
    with _session_lock:
        _session_thread = thread
    thread.start()


def end_session(login, role=None, machine=None):
    """Oznacz użytkownika jako wylogowanego i zatrzymaj heartbeat."""
    try:
        with _session_lock:
            stop = _session_stop
            if stop is not None:
                stop.set()
        _heartbeat_write(login, role, machine, logout=True)
    except Exception:
        logger.exception("end_session heartbeat failed")


def start_heartbeat(root, login, role=None, interval_ms=None):
    """Uruchom Tk heartbeat dla zgodności ze starszym kodem."""
    if not root or not login:
        return
    cfg = _get_cfg()
    if interval_ms is None:
        try:
            hb_sec = int(cfg.get("presence", {}).get("heartbeat_sec", 30))
        except (TypeError, ValueError):
            hb_sec = 30
        interval_ms = max(5000, hb_sec * 1000)

    def _tick():
        try:
            heartbeat(login, role, logout=False)
        except (OSError, ValueError) as e:
            log_akcja(f"[USERS-DBG] heartbeat error: {e}")
        except Exception as e:
            log_akcja(f"[USERS-DBG] unexpected heartbeat error: {e}\n{traceback.format_exc()}")
        finally:
            try:
                root.after(interval_ms, _tick)
            except TclError:
                log_akcja("[USERS-DBG] heartbeat scheduling stopped")
            except Exception as e:
                log_akcja(f"[USERS-DBG] unexpected scheduling error: {e}\n{traceback.format_exc()}")

    def _on_exit():
        try:
            end_session(login, role)
        except Exception as e:
            log_akcja(f"[USERS-DBG] end_session error: {e}")

    global _atexit_handler
    try:
        unreg = getattr(atexit, "unregister", None)
        if _atexit_handler and unreg:
            try:
                unreg(_atexit_handler)
            except Exception:
                logger.exception("atexit unregister failed")
        if _atexit_handler is None or unreg:
            atexit.register(_on_exit)
            _atexit_handler = _on_exit
    except Exception as e:
        log_akcja(f"[USERS-DBG] atexit register error: {e}")

    _tick()


def read_presence(max_age_sec=None):
    """Zwróć listę rekordów z presence.json + online/offline."""
    cfg = _get_cfg()
    if max_age_sec is None:
        try:
            max_age_sec = int(cfg.get("presence", {}).get("online_window_sec", 120))
        except (TypeError, ValueError):
            max_age_sec = 120

    data = _read_all()
    out = []
    now = datetime.now(timezone.utc).timestamp()
    if isinstance(data, dict):
        for _key, rec in data.items():
            ts_iso = rec.get("ts")
            try:
                ts = datetime.fromisoformat(ts_iso).timestamp() if ts_iso else 0
            except ValueError:
                ts = 0
            age = now - ts if ts else 999999
            online = (age <= max_age_sec) and (not rec.get("logout"))
            out.append({
                "login": rec.get("login", ""),
                "role": rec.get("role", ""),
                "machine": rec.get("machine", ""),
                "last_ts": ts_iso or "",
                "seconds_ago": int(age) if ts else None,
                "online": online,
                "logout": bool(rec.get("logout")),
            })
    return out, _presence_path()
