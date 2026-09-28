# version: 1.0
"""Blokada jednej instancji Warsztat Menager na stanowisku.

Windows używa nazwanego mutexu systemowego, więc awaria procesu nie pozostawia
trwałej blokady. Na pozostałych systemach używany jest flock na pliku w TEMP,
co pozwala uruchamiać testy regresyjne bez zmiany zachowania Windows.
"""
from __future__ import annotations

import atexit
import os
import tempfile
import time
from pathlib import Path
from typing import Any

_MUTEX_NAME = r"Local\WarsztatMenager.SingleInstance.v1"
_lock_handle: Any = None
_lock_file: Any = None
_registered_atexit = False


def _acquire_windows() -> bool:
    global _lock_handle
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.GetLastError.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if not handle:
        return False
    if int(kernel32.GetLastError()) == 183:
        kernel32.CloseHandle(handle)
        return False
    _lock_handle = handle
    return True


def _acquire_posix() -> bool:
    global _lock_file
    import fcntl

    path = Path(tempfile.gettempdir()) / "warsztat-menager-single-instance.lock"
    handle = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        handle.close()
        return False

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _lock_file = handle
    return True


def acquire_single_instance(*, wait_seconds: float = 0.0) -> bool:
    """Zajmij globalną blokadę WM.

    wait_seconds jest używane tylko przy kontrolowanym restarcie po aktualizacji.
    Zwykłe drugie uruchomienie nie czeka i kończy się od razu.
    """
    global _registered_atexit
    if _lock_handle is not None or _lock_file is not None:
        return True

    deadline = time.monotonic() + max(0.0, float(wait_seconds or 0.0))
    while True:
        acquired = _acquire_windows() if os.name == "nt" else _acquire_posix()
        if acquired:
            if not _registered_atexit:
                atexit.register(release_single_instance)
                _registered_atexit = True
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def release_single_instance() -> None:
    """Zwolnij blokadę, jeśli ten proces ją posiada."""
    global _lock_handle, _lock_file

    if os.name == "nt" and _lock_handle is not None:
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            try:
                kernel32.ReleaseMutex(_lock_handle)
            except Exception:
                pass
            kernel32.CloseHandle(_lock_handle)
        finally:
            _lock_handle = None

    if _lock_file is not None:
        handle = _lock_file
        _lock_file = None
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


def show_already_running_notice() -> None:
    message = (
        "Warsztat Menager jest już uruchomiony.\n\n"
        "Sprawdź główne okno albo ikonę WM obok zegara."
    )
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                message,
                "Warsztat Menager",
                0x00000040,
            )
            return
        except Exception:
            pass
    print(message)


__all__ = [
    "acquire_single_instance",
    "release_single_instance",
    "show_already_running_notice",
]
