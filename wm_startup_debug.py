"""Diagnostyka startu WM.

Zapisuje checkpointy do stderr i logs/wm_startup_debug.log. Nie wykonuje żadnej
ciężkiej pracy i nie używa sieci/Git.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

_ENABLED = os.environ.get("WM_STARTUP_DEBUG", "1").strip().lower() not in {"0", "false", "off", "no"}
_START = time.perf_counter()


def _log_path() -> Path:
    base = os.environ.get("WM_DATA_ROOT") or os.environ.get("WM_ROOT") or os.getcwd()
    p = Path(base) / "logs" / "wm_startup_debug.log"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        p = Path(os.getcwd()) / "wm_startup_debug.log"
    return p


def checkpoint(name: str, **details) -> None:
    if not _ENABLED:
        return
    elapsed = time.perf_counter() - _START
    msg = f"[WM-STARTUP {elapsed:8.3f}s] {name}"
    if details:
        msg += " | " + " ".join(f"{k}={v}" for k, v in details.items())
    line = f"{datetime.now().isoformat(timespec='milliseconds')} {msg}"
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass
