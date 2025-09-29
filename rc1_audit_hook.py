# -*- coding: utf-8 -*-
"""Hook zamieniający ``audit.run`` na wersję z Audit+ (>=100 checków).

Moduł próbuje bezpiecznie przejąć wywołanie ``audit.run``. Jeśli wymagane
moduły są dostępne, podmieniamy funkcję na wrapper, który wywołuje
``rc1_audit_plus.run``. W przypadku niepowodzenia wracamy do oryginalnego
``audit.run`` lub zwracamy defensywną odpowiedź błędu.
"""

from __future__ import annotations


def _install() -> None:
    try:
        import audit
    except Exception:
        return  # brak modułu audit — nic nie robimy

    try:
        import rc1_audit_plus as audit_plus
    except Exception:
        return  # nie ma Audit+ — zostaw oryginał

    orig_run = getattr(audit, "run", None)

    def run_wrapper(*args, **kwargs):
        """Uruchom Audit+ lub fallback do oryginalnego ``audit.run``."""

        try:
            out = audit_plus.run()
            if isinstance(out, dict) and "ok" in out and "msg" in out:
                return out
        except Exception:
            pass
        if callable(orig_run):
            return orig_run(*args, **kwargs)
        return {"ok": False, "msg": "audit.run missing", "path": None}

    try:
        setattr(audit, "run", run_wrapper)
    except Exception:
        pass


try:
    _install()
except Exception:
    pass
