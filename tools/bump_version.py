# version: 1.0
"""Podnosi centralną wersję Warsztat Menager zgodnie z SemVer."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[1] / "__version__.py"
RX = re.compile(r'__version__\s*=\s*["\'](\d+)(?:\.(\d+))?(?:\.(\d+))?["\']')

def bump(kind: str) -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = RX.search(text)
    if not match:
        raise RuntimeError("Nie znaleziono __version__ w __version__.py")
    major, minor, patch = (int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0))
    if kind == "patch":
        patch += 1
    elif kind == "minor":
        minor += 1; patch = 0
    elif kind == "major":
        major += 1; minor = 0; patch = 0
    else:
        raise ValueError(kind)
    new = f"{major}.{minor}.{patch}"
    start, end = match.span()
    text = text[:start] + f'__version__ = "{new}"' + text[end:]
    VERSION_FILE.write_text(text, encoding="utf-8")
    return new

def main() -> int:
    parser = argparse.ArgumentParser(description="Podnieś wersję WM zgodnie z SemVer")
    parser.add_argument("kind", choices=("patch", "minor", "major"))
    args = parser.parse_args()
    print(bump(args.kind))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
