# version: 1.0
# -*- coding: utf-8 -*-
"""Bezpieczny launcher WM dla restartu po aktualizacji na Windows.

start.py pozostaje źródłem logiki startowej. Ten launcher przechwytuje wyłącznie
handoff po aktualizacji, gdy ścieżka interpretera zawiera np. ``Program Files``.
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Mapping, Sequence


APP_DIR = Path(__file__).resolve().parent
START_SCRIPT = APP_DIR / "start.py"
_ORIGINAL_EXECV = os.execv


def _normalize_windows_path(value: object) -> str:
    return str(value or "").strip().strip('"').replace("/", "\\").casefold()


def _is_wm_restart_handoff(
    path: object,
    args: Sequence[object],
    *,
    env: Mapping[str, str] | None = None,
    os_name: str | None = None,
    executable: object | None = None,
) -> bool:
    """Rozpoznaj wyłącznie restart WM wykonywany po udanym Git pull."""

    current_os = os.name if os_name is None else os_name
    current_env = os.environ if env is None else env
    current_executable = sys.executable if executable is None else executable
    argv = list(args or ())

    if current_os != "nt":
        return False
    if current_env.get("WM_RESTARTED_AFTER_UPDATE") != "1":
        return False
    if len(argv) < 2:
        return False
    if _normalize_windows_path(path) != _normalize_windows_path(current_executable):
        return False

    script_name = PureWindowsPath(str(argv[1]).replace("/", "\\")).name.casefold()
    return script_name == "start.py"


def _build_restart_command(path: object, args: Sequence[object]) -> list[str]:
    """Zbuduj argv dla Popen bez sklejania ścieżek w jeden tekst polecenia."""

    argv = list(args or ())
    return [str(path), *[str(value) for value in argv[1:]]]


def _safe_execv(path: str, args: Sequence[object]):
    """Na Windows zamień problematyczny execv restartu WM na Popen(list)."""

    if _is_wm_restart_handoff(path, args):
        command = _build_restart_command(path, args)
        print(
            "[WM-DBG][GIT] Windows: restart przez subprocess.Popen "
            "(bezpieczny dla spacji w ścieżce Pythona)."
        )
        subprocess.Popen(command, cwd=str(APP_DIR), shell=False)
        raise SystemExit(0)

    return _ORIGINAL_EXECV(path, args)


def main() -> None:
    """Uruchom start.py z wąsko ograniczonym zabezpieczeniem restartu."""

    original_argv = list(sys.argv)
    os.execv = _safe_execv
    sys.argv = [str(START_SCRIPT), *original_argv[1:]]
    try:
        runpy.run_path(str(START_SCRIPT), run_name="__main__")
    finally:
        sys.argv = original_argv
        os.execv = _ORIGINAL_EXECV


if __name__ == "__main__":
    main()
