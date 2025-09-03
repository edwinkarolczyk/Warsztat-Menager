import updater
import pytest

def test_run_git_pull_logs_stderr_and_traceback(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(updater, "LOGS_DIR", logs_dir)
    stamp = "0001"
    with pytest.raises(RuntimeError):
        updater._run_git_pull(tmp_path, stamp)
    log_file = logs_dir / f"update_{stamp}.log"
    content = log_file.read_text(encoding="utf-8")
    assert "[STDERR]" in content
    assert "not a git repository" in content.lower()
    assert "[TRACEBACK]" in content


def test_git_has_updates_logs_traceback(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(updater, "LOGS_DIR", logs_dir)
    stamp = "0002"
    monkeypatch.setattr(updater, "_now_stamp", lambda: stamp)
    result = updater._git_has_updates(tmp_path / "missing")
    assert result is False
    log_file = logs_dir / f"update_{stamp}.log"
    content = log_file.read_text(encoding="utf-8")
    assert "git update check failed" in content
    assert "[TRACEBACK]" in content
