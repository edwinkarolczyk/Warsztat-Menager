# version: 1.0.1
"""Utilities for retrieving last update information.

This module provides helpers for update metadata and remote-branch checks.
During WM bootstrap, Git subprocesses are intentionally short-circuited so
network/repository operations cannot block the main application startup.
Once ``start.py`` switches ``BOOTSTRAP_ACTIVE`` to ``False``, normal Git
commands work unchanged.
"""

from __future__ import annotations

import json
import subprocess
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


logger = logging.getLogger(__name__)

# Preserve the real subprocess implementation. During startup, start.py sets
# BOOTSTRAP_ACTIVE=True; Git commands are then replaced with instant successful
# no-ops. This is deliberately scoped to Git commands only.
_REAL_SUBPROCESS_RUN = subprocess.run


def _wm_subprocess_run(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    is_git = isinstance(cmd, (list, tuple)) and bool(cmd) and str(cmd[0]).lower().split("\\")[-1] in {"git", "git.exe"}
    bootstrap = False
    try:
        bootstrap = bool(getattr(sys.modules.get("__main__"), "BOOTSTRAP_ACTIVE", False))
    except Exception:
        bootstrap = False

    if is_git and bootstrap:
        stdout = kwargs.get("stdout")
        stderr = kwargs.get("stderr")
        out_value = "" if stdout is not None else None
        err_value = "" if stderr is not None else None
        return subprocess.CompletedProcess(cmd, 0, stdout=out_value, stderr=err_value)

    return _REAL_SUBPROCESS_RUN(*args, **kwargs)


# Shared subprocess module object: start.py imports the same module, therefore
# its direct Git calls are protected during bootstrap as well.
subprocess.run = _wm_subprocess_run


def remote_branch_exists(remote: str, branch: str, cwd: Path | None = None) -> bool:
    """Check if ``branch`` exists on ``remote``."""

    result = subprocess.run(
        ["git", "ls-remote", "--heads", remote, branch],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def load_last_update_info() -> Tuple[str, Optional[str]]:
    """Return information about the latest update.

    The function attempts three methods in order:
    1. ``logi_wersji.json``
    2. ``CHANGES_PROFILES_UPDATE.txt``
    3. ``git log`` / ``git show`` as a fallback.
    """

    try:
        with open("logi_wersji.json", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list) and data:
            last = data[-1]
            data_str = last.get("data")
            wersje = last.get("wersje", {})
            version = None
            if isinstance(wersje, dict):
                version = next(iter(wersje.values()), None)
            if data_str:
                return f"Ostatnia aktualizacja: {data_str}", version
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.debug("Unable to read logi_wersji.json: %s", e, exc_info=True)

    try:
        with open("CHANGES_PROFILES_UPDATE.txt", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().lower().startswith("data:"):
                    date_str = line.split(":", 1)[1].strip()
                    if date_str:
                        return f"Ostatnia aktualizacja: {date_str}", None
    except OSError as e:
        logger.debug("Unable to read CHANGES_PROFILES_UPDATE.txt: %s", e, exc_info=True)

    for cmd in (["git", "log", "-1", "--format=%ci"],
                ["git", "show", "-s", "--format=%ci", "HEAD"]):
        try:
            ts = subprocess.check_output(
                cmd,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S %z")
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            return f"Ostatnia aktualizacja: {formatted}", None
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            logger.debug("Git command %s failed: %s", cmd, e, exc_info=True)
            continue

    return "brak danych o aktualizacjach", None
