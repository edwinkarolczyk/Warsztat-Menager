"""Minimal logging helpers used by backend utilities during tests.

The real application defines richer logging facilities under the same
module name. For test purposes we emulate the ``wm_log`` API that the
updater module expects so that imports succeed without pulling the full
logging stack. The helpers mirror the ``wm_log`` contract of accepting a
single ``extra`` payload (typically a dict with structured data).
"""

from __future__ import annotations

from typing import Any


def _log(level: str, area: str, event: str, extra: Any | None = None) -> None:
    parts = [f"[{level}]", f"[{area}]", event]
    if extra is not None:
        if isinstance(extra, dict):
            details = " ".join(f"{key}={value!r}" for key, value in extra.items())
            parts.append(details)
        else:
            parts.append(repr(extra))
    print(" ".join(parts))


def dbg(area: str, event: str, extra: Any | None = None) -> None:
    _log("DBG", area, event, extra)


def info(area: str, event: str, extra: Any | None = None) -> None:
    _log("INFO", area, event, extra)


def err(area: str, event: str, extra: Any | None = None) -> None:
    _log("ERR", area, event, extra)
