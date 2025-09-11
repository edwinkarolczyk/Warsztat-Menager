# presence.py (enhanced)
import os, json, time, tempfile, platform, atexit, traceback
import logging
from datetime import datetime, timezone

# Initialize module logger
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
except ImportError:  # pragma: no cover - fallback when tkinter is unavailable
    class TclError(Exception):
        pass

try:
    from logger import log_akcja
except ImportError:  # pragma: no cover - logger module might be absent in tests
    logging.basicConfig(level=logging.INFO)

    def log_akcja(msg: str) -> None:
        logger.info(msg)

# Track the currently registered atexit handler to avoid duplicates
_atexit_handler = None

def _now_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def _get_cfg():
    return config if isinstance(config, dict) else {}

def _cfg_dir():
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
                except OSError as e:
                    logger.exception("rename fallback failed for %s: %s", path, e)
        finally:
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                logger.exception("cleanup failed for %s: %s", tmp_path, e)

def _read_all():
    path = _presence_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
            if isinstance(d, dict):
                return d
        except (OSError, json.JSONDecodeError) as e:
            logger.exception("reading presence file failed: %s", e)
    return {}

def heartbeat(login, role=None, machine=None, logout=False):
    """Jednorazowy zapis bicia serca. logout=True oznacza świadome wylogowanie."""
    if not login: return False
    path = _presence_path()
    data = _read_all()

    if not machine:
        try:
            machine = platform.node()
        except OSError as e:
            logger.exception("platform.node failed: %s", e)
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

def end_session(login, role=None, machine=None):
    """Oznacz użytkownika jako wylogowanego (natychmiast offline)."""
    try:
        heartbeat(login, role, machine, logout=True)
    except Exception:
        logger.exception("end_session heartbeat failed")

def start_heartbeat(root, login, role=None, interval_ms=None):
    """Uruchom cykliczne bicie serca.

    interval_ms z configu: presence.heartbeat_sec (domyślnie 30s).
    Kolejne wywołania zastępują poprzedni hook ``atexit`` aby nie
    gromadzić wielu rejestracji zakończenia programu.
    """
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
        except Exception as e:  # unexpected
            log_akcja(
                f"[USERS-DBG] unexpected heartbeat error: {e}\n{traceback.format_exc()}"
            )
        finally:
            try:
                root.after(interval_ms, _tick)
            except TclError:
                log_akcja("[USERS-DBG] heartbeat scheduling stopped")
            except Exception as e:
                log_akcja(
                    f"[USERS-DBG] unexpected scheduling error: {e}\n{traceback.format_exc()}"
                )

    # Rejestruj zakończenie procesu (program zamykany) => natychmiast offline
    def _on_exit():
        try:
            end_session(login, role)
        except (OSError, ValueError) as e:
            log_akcja(f"[USERS-DBG] end_session error: {e}")
        except Exception as e:
            log_akcja(
                f"[USERS-DBG] unexpected end_session error: {e}\n{traceback.format_exc()}"
            )

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
    except (RuntimeError, ValueError) as e:
        log_akcja(f"[USERS-DBG] atexit register error: {e}")
    except Exception as e:
        log_akcja(
            f"[USERS-DBG] unexpected atexit register error: {e}\n{traceback.format_exc()}"
        )

    _tick()

def read_presence(max_age_sec=None):
    """Zwróć listę rekordów z presence.json + online/offline.
       Jeśli logout=True => zawsze offline niezależnie od wieku wpisu.
       max_age_sec z configu: presence.online_window_sec (domyślnie 120s)."""
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
        for key, rec in data.items():
            ts_iso = rec.get("ts")
            try:
                ts = datetime.fromisoformat(ts_iso).timestamp() if ts_iso else 0
            except ValueError:
                ts = 0
            age = now - ts if ts else 999999
            online = (age <= max_age_sec) and (not rec.get("logout"))
            out.append({
                "login": rec.get("login",""),
                "role": rec.get("role",""),
                "machine": rec.get("machine",""),
                "last_ts": ts_iso or "",
                "seconds_ago": int(age) if ts else None,
                "online": online,
                "logout": bool(rec.get("logout")),
            })
    return out, _presence_path()
