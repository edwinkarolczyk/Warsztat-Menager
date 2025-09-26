"""Minimal logging helpers used by backend utilities during tests.

The real application defines richer logging facilities under the same
module name.  For test purposes we emulate the API that the updater module
expects so that imports succeed without pulling the full logging stack.
"""

from __future__ import annotations

from typing import Any


def _log(level: str, area: str, event: str, extra: Any | None = None, **kwargs: Any) -> None:
    parts = [f"[{level}]", f"[{area}]", event]
    if extra is not None:
        parts.append(repr(extra))
    if kwargs:
        details = " ".join(f"{key}={value!r}" for key, value in kwargs.items())
        parts.append(details)
    print(" ".join(parts))


def dbg(area: str, event: str, extra: Any | None = None, **kwargs: Any) -> None:
    _log("DBG", area, event, extra, **kwargs)


def info(area: str, event: str, extra: Any | None = None, **kwargs: Any) -> None:
    _log("INFO", area, event, extra, **kwargs)


def err(area: str, event: str, extra: Any | None = None, **kwargs: Any) -> None:
    _log("ERR", area, event, extra, **kwargs)
