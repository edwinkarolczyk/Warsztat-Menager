from __future__ import annotations
import os
import sys
import time
import traceback
from typing import Any, Callable, Optional

# Konfiguracja z Ustawień (opcjonalna)
_SETTINGS_GETTER: Optional[Callable[[str], Any]] = None

def bind_settings_getter(getter: Callable[[str], Any]) -> None:
    """Podłącz funkcję pobierającą ustawienia (np. lambda k: settings_state.get(k))."""
    global _SETTINGS_GETTER
    _SETTINGS_GETTER = getter


def _get_setting(key: str, default: Any = None) -> Any:
    if _SETTINGS_GETTER is None:
        return default
    try:
        val = _SETTINGS_GETTER(key)
        return default if val is None else val
    except Exception:
        return default


# Poziomy logowania
_LEVELS = {"debug": 10, "info": 20, "error": 30}
_COLOR = {
    "DBG": "\033[90m",   # szary
    "INFO": "\033[37m",  # biały
    "ERR": "\033[91m",   # czerwony
    "RESET": "\033[0m",
}


def _term_supports_color() -> bool:
    if os.name == "nt":
        # Windows 10+ zwykle wspiera ANSI w nowym terminalu
        return True
    return sys.stdout.isatty()


def _enabled(level_name: str) -> bool:
    # Flaga debug
    debug_enabled = bool(_get_setting("system.debug_enabled", True))
    # Globalny poziom
    lvl = str(_get_setting("system.log_level", "debug")).lower()
    min_level = _LEVELS.get(lvl, 10)
    cur_level = {"DBG": 10, "INFO": 20, "ERR": 30}[level_name]
    if cur_level < min_level:
        # filtr progu
        if level_name == "DBG" and not debug_enabled:
            return False
        return False
    # Dla DBG dodatkowo sprawdź flagę
    if level_name == "DBG" and not debug_enabled:
        return False
    return True


def _kv_pairs(kv: dict[str, Any]) -> str:
    out = []
    for k, v in kv.items():
        try:
            s = repr(v)
            if len(s) > 240:
                s = s[:240] + "...(truncated)"
        except Exception:
            s = "<unrepr>"
        out.append(f"{k}={s}")
    return " ".join(out)


def _emit(level_tag: str, where: str, msg: str, **kv: Any) -> None:
    if not _enabled(level_tag):
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    pairs = _kv_pairs(kv) if kv else ""
    base = f"WM|{level_tag}|{ts}|{where}|{msg}"
    line = f"{base}|{pairs}" if pairs else base
    if _term_supports_color():
        color = _COLOR[level_tag]
        reset = _COLOR["RESET"]
        print(f"{color}{line}{reset}")
    else:
        print(line)


def dbg(where: str, msg: str, **kv: Any) -> None:
    _emit("DBG", where, msg, **kv)


def info(where: str, msg: str, **kv: Any) -> None:
    _emit("INFO", where, msg, **kv)


def err(where: str, msg: str, exc: Optional[BaseException] = None, **kv: Any) -> None:
    if exc is not None:
        kv = {**kv, "exc": repr(exc), "tb": traceback.format_exc(limit=5)}
    _emit("ERR", where, msg, **kv)
