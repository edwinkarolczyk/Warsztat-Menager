#!/usr/bin/env python3
"""Scan repository for direct tkinter dialog calls.

The script helps maintainers replace raw ``filedialog`` and ``messagebox``
invocations with the safe wrappers provided in :mod:`ui_dialogs_safe`.
"""

from __future__ import annotations

import os
import re
import sys


def _iter_python_files(root: str):
    for base, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def main() -> int:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(repo_root)
    pattern = re.compile(
        r"\bfiledialog\.(askopenfilename|asksaveasfilename|askdirectory)\b"
        r"|\bmessagebox\.(showinfo|showerror|showwarning)\b"
    )

    for path in _iter_python_files(repo_root):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for lineno, line in enumerate(handle, 1):
                    if pattern.search(line):
                        rel = os.path.relpath(path, repo_root).replace("\\", "/")
                        print(f"{rel}:{lineno}: {line.rstrip()}")
        except OSError:
            continue

    return 0


if __name__ == "__main__":  # pragma: no cover - helper script
    sys.exit(main())

