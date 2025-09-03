import subprocess
import pytest
import updater


def test_git_has_updates_logs_error(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(updater, "_now_stamp", lambda: "STAMP")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], output="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert updater._git_has_updates(tmp_path) is False

    log_file = tmp_path / "logs" / "update_STAMP.log"
    data = log_file.read_text(encoding="utf-8")
    assert "[STDERR]" in data
    assert "err" in data
    assert "[TRACEBACK]" in data


def test_run_git_pull_logs_error(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "LOGS_DIR", tmp_path / "logs")

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], output="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        updater._run_git_pull(tmp_path, "STAMP2")

    log_file = tmp_path / "logs" / "update_STAMP2.log"
    data = log_file.read_text(encoding="utf-8")
    assert "[STDERR]" in data
    assert "err" in data
    assert "[TRACEBACK]" in data


def test_git_has_updates_missing_branch(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
    subprocess.run(["git", "push", "-u", "origin", "master"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-b", "missing"], cwd=repo, check=True)

    monkeypatch.setattr(updater, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(updater, "_now_stamp", lambda: "STAMP3")

    assert updater._git_has_updates(repo) is False

    log_file = tmp_path / "logs" / "update_STAMP3.log"
    data = log_file.read_text(encoding="utf-8")
    assert "remote branch origin/missing not found" in data

