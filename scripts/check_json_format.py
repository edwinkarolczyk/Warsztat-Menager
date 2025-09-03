#!/usr/bin/env python3
"""Validate JSON files for UTF-8 encoding and two-space indentation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def check_json_file(path: Path) -> bool:
    """Return True if file is valid UTF-8 JSON with two-space indentation."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"{path}: not UTF-8 encoded")
        return False

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"{path}: invalid JSON - {exc}")
        return False

    formatted = json.dumps(data, ensure_ascii=False, indent=2)
    if text.rstrip() != formatted.rstrip():
        print(f"{path}: not formatted with two-space indentation")
        return False

    return True


def main() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.json"], capture_output=True, check=True
    )
    output = result.stdout.decode()
    files = [Path(p) for p in output.split("\0") if p]

    ok = True
    for file in files:
        if not check_json_file(file):
            ok = False

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
