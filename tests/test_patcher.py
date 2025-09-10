import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from tools import patcher


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "WM"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "wm@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "Rozwiniecie"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "audit").mkdir()
    (path / "audit" / "config_changes.jsonl").write_text("", encoding="utf-8")


def test_get_commits() -> None:
    with TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_repo(repo)
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run([
            "git",
            "add",
            "a.txt",
        ], cwd=repo, check=True, capture_output=True)
        subprocess.run([
            "git",
            "commit",
            "-m",
            "msg1",
        ], cwd=repo, check=True, capture_output=True)
        (repo / "a.txt").write_text("b\n", encoding="utf-8")
        subprocess.run(
            ["git", "commit", "-am", "msg2"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        os.environ["WM_AUDIT_FILE"] = str(
            repo / "audit" / "config_changes.jsonl"
        )
        prev_cwd = os.getcwd()
        try:
            os.chdir(repo)
            commits = patcher.get_commits(limit=5, branch="Rozwiniecie")
        finally:
            os.chdir(prev_cwd)
        assert [msg for _, msg in commits] == ["msg2", "msg1"]
        audit_lines = (
            repo / "audit" / "config_changes.jsonl"
        ).read_text(encoding="utf-8").strip().splitlines()
        last_entry = json.loads(audit_lines[-1])
        assert last_entry["action"] == "get_commits"


def test_apply_patch_and_rollback() -> None:
    with TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_repo(repo)
        file_path = repo / "file.txt"
        file_path.write_text("Hello\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "file.txt"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        base = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        patch = (
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1 +1 @@\n"
            "-Hello\n"
            "+Hello world\n"
        )
        patch_file = repo / "change.patch"
        patch_file.write_text(patch, encoding="utf-8")
        os.environ["WM_AUDIT_FILE"] = str(
            repo / "audit" / "config_changes.jsonl"
        )
        prev_cwd = os.getcwd()
        try:
            os.chdir(repo)
            patcher.apply_patch(str(patch_file), dry_run=True)
            assert file_path.read_text(encoding="utf-8") == "Hello\n"
            patcher.apply_patch(str(patch_file))
            assert file_path.read_text(encoding="utf-8") == "Hello world\n"
            subprocess.run(
                ["git", "commit", "-am", "update"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            patcher.rollback_to(base, hard=True)
        finally:
            os.chdir(prev_cwd)
        assert file_path.read_text(encoding="utf-8") == "Hello\n"
        audit_lines = (
            repo / "audit" / "config_changes.jsonl"
        ).read_text(encoding="utf-8").strip().splitlines()
        actions = [json.loads(line)["action"] for line in audit_lines]
        assert actions.count("apply_patch") == 2
        assert "rollback_to" in actions
