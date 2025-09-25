"""Narzędzia aktualizacji backendu (kopie zapasowe danych)."""

from __future__ import annotations

import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from config.paths import get_path


def _now_stamp() -> str:
    """Zwraca bieżący znacznik czasu używany w nazwach plików."""

    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _is_relative_to(path: Path, base: Path) -> bool:
    """Bezpieczna wersja Path.is_relative_to zgodna ze starszymi Pythonami."""

    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _iter_data_files(root: Path, skip: Iterable[Path]) -> Iterable[Path]:
    """Iteruje po plikach w katalogu danych z pominięciem wskazanych ścieżek."""

    skip_resolved: List[Path] = [s.resolve(strict=False) for s in skip]
    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath).resolve(strict=False)
        # Usuń z listy podkatalogi, które należy ominąć
        dirnames[:] = [
            d
            for d in dirnames
            if not any(
                _is_relative_to((current_dir / d).resolve(strict=False), s)
                for s in skip_resolved
            )
        ]

        if any(_is_relative_to(current_dir, s) for s in skip_resolved):
            continue

        for filename in filenames:
            yield current_dir / filename


def backup_zip() -> str:
    """Tworzy archiwum ZIP katalogu danych w docelowym katalogu kopii zapasowych."""

    target_dir = Path(get_path("paths.backup_dir")).expanduser()
    os.makedirs(target_dir, exist_ok=True)

    data_root = Path(get_path("paths.data_root")).expanduser()
    if not data_root.exists() or not data_root.is_dir():
        raise FileNotFoundError("paths.data_root nie wskazuje na istniejący katalog")

    skip_dirs: List[Path] = []
    try:
        data_root_resolved = data_root.resolve()
        backup_dir_resolved = target_dir.resolve()
    except FileNotFoundError:
        data_root_resolved = data_root
        backup_dir_resolved = target_dir

    if _is_relative_to(backup_dir_resolved, data_root_resolved):
        skip_dirs.append(backup_dir_resolved)

    stamp = _now_stamp()
    zip_path = target_dir / f"backup-{stamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in _iter_data_files(data_root, skip_dirs):
            try:
                arcname = file_path.relative_to(data_root)
            except ValueError:
                # Plik spoza data_root (np. link symboliczny); pomiń go.
                continue
            archive.write(file_path, arcname.as_posix())

    return str(zip_path)

