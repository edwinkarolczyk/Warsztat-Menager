from __future__ import annotations

import shutil
from pathlib import Path

BACKUP_ROOT = Path("backups")


def restore_backup(path: str | Path) -> Path:
    """Restore a file from the backups directory to its original location.

    The ``path`` should point to a file inside ``backups/<stamp>/``. The file
    is copied to the repository root keeping the relative path stored in the
    backup. The directory structure inside the stamp is preserved.

    Parameters
    ----------
    path:
        Path to a file inside the ``backups`` directory.

    Returns
    -------
    pathlib.Path
        Destination path of the restored file.

    Raises
    ------
    FileNotFoundError
        If the provided path does not exist.
    ValueError
        If the path is outside of the ``backups`` directory or malformed.
    """

    src = Path(path).resolve()
    root = BACKUP_ROOT.resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Backup file not found: {src}")

    try:
        rel = src.relative_to(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Backup file must reside inside 'backups/'") from exc

    parts = rel.parts
    if len(parts) < 2:
        raise ValueError("Invalid backup file path.")

    dest = Path(*parts[1:])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest
