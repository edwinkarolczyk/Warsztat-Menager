from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


def _get_audit_file() -> Path:
    return Path(
        os.environ.get(
            "WM_AUDIT_FILE",
            Path(__file__).resolve().parents[1] / "audit" / "config_changes.jsonl",
        )
    )


def _append_audit(entry: dict) -> None:
    audit_file = _get_audit_file()
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with audit_file.open("a", encoding="utf-8") as fh:
        json.dump(entry, fh, ensure_ascii=False)
        fh.write("\n")


def apply_patch(path: str, dry_run: bool = False) -> None:
    """Apply a git patch from ``path``.

    Parameters
    ----------
    path:
        Path to the patch file.
    dry_run:
        When ``True``, run ``git apply --check`` to verify patch without
        applying it.
    """
    cmd = ["git", "apply"]
    if dry_run:
        cmd.append("--check")
    cmd.append(path)
    print(f"[WM-DBG] Running {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    _append_audit(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": "apply_patch",
            "path": path,
            "dry_run": dry_run,
        }
    )
    print("[WM-DBG] apply_patch complete")


def get_commits(limit: int = 20, branch: str = "Rozwiniecie") -> List[Tuple[str, str]]:
    """Return last commits from ``branch``.

    Parameters
    ----------
    limit:
        Maximum number of commits to return.
    branch:
        Branch name to inspect.
    """
    cmd = ["git", "log", f"-n{limit}", "--format=%H%x09%s", branch]
    print(f"[WM-DBG] Running {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    commits: List[Tuple[str, str]] = []
    for line in result.stdout.strip().splitlines():
        commit_hash, message = line.split("\t", 1)
        commits.append((commit_hash, message))
    _append_audit(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": "get_commits",
            "limit": limit,
            "branch": branch,
        }
    )
    print("[WM-DBG] get_commits complete")
    return commits


def rollback_to(commit_hash: str, hard: bool = True) -> None:
    """Reset repository to ``commit_hash``.

    Parameters
    ----------
    commit_hash:
        Commit to reset to.
    hard:
        When ``True`` perform ``--hard`` reset, otherwise ``--soft``.
    """
    cmd = ["git", "reset", "--hard" if hard else "--soft", commit_hash]
    print(f"[WM-DBG] Running {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    _append_audit(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": "rollback_to",
            "commit": commit_hash,
            "hard": hard,
        }
    )
    print("[WM-DBG] rollback_to complete")
