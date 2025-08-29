import importlib
import sys
from pathlib import Path


def test_restore_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    backup = importlib.import_module("backup")

    stamp = Path("backups") / "stamp"
    stamp.mkdir(parents=True)
    backup_file = stamp / "data.txt"
    backup_file.write_text("hello", encoding="utf-8")

    restored = backup.restore_backup(backup_file)
    assert restored == Path("data.txt")
    assert restored.read_text(encoding="utf-8") == "hello"
