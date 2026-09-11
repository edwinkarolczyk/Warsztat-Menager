# version: 1.3
"""Wspólne blokady plików danych dla WM desktop i WMM."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import threading
import time
from typing import Iterator


_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _process_lock_for(lock_path: Path) -> threading.Lock:
    key = str(lock_path.resolve())
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_LOCKS[key] = lock
        return lock


def _try_os_lock(handle) -> bool:
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _release_os_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def file_write_lock(
    target_path: str | os.PathLike[str],
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
    label: str = "danych",
) -> Iterator[None]:
    """Zablokuj zapis wskazanego zasobu między wątkami i procesami."""

    target = Path(target_path)
    lock_path = target.with_name(target.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    process_lock = _process_lock_for(lock_path)
    wait_seconds = max(0.0, float(timeout))
    if not process_lock.acquire(timeout=wait_seconds):
        raise TimeoutError(
            f"Przekroczono czas oczekiwania na zapis {label}: {target}"
        )

    handle = None
    os_locked = False
    deadline = time.monotonic() + wait_seconds
    try:
        handle = lock_path.open("a+b")
        while True:
            if _try_os_lock(handle):
                os_locked = True
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Przekroczono czas oczekiwania na blokadę {label}: {target}"
                )
            time.sleep(max(0.01, float(poll_interval)))
        yield
    finally:
        if handle is not None:
            try:
                if os_locked:
                    _release_os_lock(handle)
            finally:
                handle.close()
        process_lock.release()


@contextmanager
def order_create_lock(
    data_dir: str | os.PathLike[str],
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Serializuj tworzenie numerowanego zlecenia między WM i WMM."""

    sequence_guard = Path(data_dir) / "zlecenia" / "_order_sequence"
    with file_write_lock(
        sequence_guard,
        timeout=timeout,
        poll_interval=poll_interval,
        label="Zleceń",
    ):
        yield


@contextmanager
def warehouse_transaction_lock(
    warehouse_json_path: str | os.PathLike[str],
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Serializuj pełny odczyt -> zmianę -> zapis kanonicznego Magazynu."""

    transaction_guard = Path(warehouse_json_path).with_name(
        "_warehouse_transaction"
    )
    with file_write_lock(
        transaction_guard,
        timeout=timeout,
        poll_interval=poll_interval,
        label="Magazynu",
    ):
        yield


@contextmanager
def machine_file_lock(
    machine_json_path: str | os.PathLike[str],
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Zablokuj zapis jednego ``maszyny.json`` między procesami WM/WMM."""

    with file_write_lock(
        machine_json_path,
        timeout=timeout,
        poll_interval=poll_interval,
        label="Maszyn",
    ):
        yield
