"""Usługi Warsztat Menager.

WMM API startuje dopiero po ustawieniu WM_ROOT, żeby zawsze używać właściwych
danych instalacji. Serwer jest lekki, idempotentny i nie blokuje GUI.
Można go wyłączyć przez WM_DISABLE_WMM_API=1.
"""

from __future__ import annotations

import os
import sys
import threading
import time


def _wmm_api_enabled() -> bool:
    value = str(os.environ.get("WM_DISABLE_WMM_API", "") or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return False
    if "pytest" in sys.modules:
        return False
    return True


def _start_wmm_after_root() -> None:
    """Poczekaj na aktywny WM_ROOT i dopiero wtedy uruchom API oraz panel QR."""
    for _ in range(240):  # maks. około 2 minuty na wybór ROOT przy starcie
        if str(os.environ.get("WM_ROOT", "") or "").strip():
            try:
                from .wmm_api import start_wmm_api
                from .wmm_login_panel import start_login_panel_watcher

                start_wmm_api()
                start_login_panel_watcher()
            except Exception:
                pass
            return
        time.sleep(0.5)


if _wmm_api_enabled():
    threading.Thread(
        target=_start_wmm_after_root,
        name="wm-wmm-bootstrap",
        daemon=True,
    ).start()
