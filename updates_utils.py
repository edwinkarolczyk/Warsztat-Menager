"""Utilities for retrieving last update information.

This module provides a single function ``load_last_update_info`` which
tries to determine the timestamp of the latest application update.  The
information is retrieved from local JSON or text logs and finally falls
back to the date of the last Git commit.
"""

from __future__ import annotations

import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


def remote_branch_exists(remote: str, branch: str, cwd: Path | None = None) -> bool:
    """Check if ``branch`` exists on ``remote``.

    Parameters
    ----------
    remote:
        Nazwa zdalnego repozytorium, np. ``origin``.
    branch:
        Nazwa gałęzi do sprawdzenia.
    cwd:
        Katalog roboczy dla polecenia ``git``.

    Returns
    -------
    bool
        ``True`` jeśli gałąź istnieje na zdalnym repozytorium,
        ``False`` w przeciwnym razie.
    """

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

    1. Read the last entry from ``logi_wersji.json``.
    2. Parse the ``Data:`` line from ``CHANGES_PROFILES_UPDATE.txt``.
    3. Use ``git log -1 --format=%ci`` (or ``git show -s --format=%ci HEAD``)
       to obtain the date of the most recent commit.

    Returns a tuple ``("Ostatnia aktualizacja: <date>", version)``.  If
    the version could not be determined ``None`` is returned instead.  If
    no method succeeds ``("brak danych o aktualizacjach", None)`` is
    returned.
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
