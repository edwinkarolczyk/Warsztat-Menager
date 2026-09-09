"""Usługi Warsztat Menager.

WMM API startuje w tle razem z importem pakietu usług. Serwer jest lekki,
idempotentny i nie blokuje GUI. Można go wyłączyć przez WM_DISABLE_WMM_API=1.
"""

from __future__ import annotations

import os


def _wmm_api_enabled() -> bool:
    value = str(os.environ.get("WM_DISABLE_WMM_API", "") or "").strip().lower()
    return value not in {"1", "true", "yes", "on"}


if _wmm_api_enabled():
    try:
        from .wmm_api import start_wmm_api

        start_wmm_api()
    except Exception:
        # API mobilne nie może zablokować startu głównego programu WM.
        pass
