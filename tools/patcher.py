import json
import os
import subprocess
from datetime import datetime
from typing import List

AUDIT_PATH = os.path.join("audit", "config_changes.jsonl")


def _audit(action: str, details: dict | None = None) -> None:
    rec = {"time": datetime.now().isoformat(timespec="seconds"), "action": action}
    if details:
        rec.update(details)
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def apply_patch(path: str, dry_run: bool) -> subprocess.CompletedProcess:
    cmd = ["git", "apply"]
    if dry_run:
        cmd.append("--check")
    cmd.append(path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    _audit("apply_patch", {"path": path, "dry_run": dry_run, "returncode": res.returncode})
    return res


def get_commits(limit: int = 20, branch: str = "Rozwiniecie") -> List[str]:
    res = subprocess.run(
        ["git", "rev-list", "--max-count", str(limit), branch],
        capture_output=True,
        text=True,
    )
    commits = res.stdout.strip().splitlines() if res.returncode == 0 else []
    _audit("get_commits", {"count": len(commits)})
    return commits


def rollback_to(commit_hash: str, hard: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "reset", "--hard" if hard else "--soft", commit_hash]
    res = subprocess.run(cmd, capture_output=True, text=True)
    _audit(
        "rollback_to",
        {"commit": commit_hash, "hard": hard, "returncode": res.returncode},
    )
    return res
