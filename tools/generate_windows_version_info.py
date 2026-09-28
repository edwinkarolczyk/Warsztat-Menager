# -*- coding: utf-8 -*-
"""Generuje ikonę oraz metadane wersji Windows dla builda Warsztat Menager."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
VERSION_SOURCE = ROOT / "__version__.py"
ICON_SOURCE = ROOT / "assets" / "wm_icon_source.jpg"
ICON_PATH = ROOT / "11.ico"
OUTPUT = ROOT / "build" / "windows_version_info.txt"

_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def read_version() -> str:
    text = VERSION_SOURCE.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise RuntimeError(f"Nie znaleziono __version__ w {VERSION_SOURCE}")
    return match.group(1).strip()


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or any(not part.isdigit() for part in parts):
        raise RuntimeError(f"Nieprawidłowa wersja Windows/SemVer: {version}")
    numbers = [int(part) for part in parts]
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers[:4])


def build_icon() -> None:
    if not ICON_SOURCE.exists():
        raise RuntimeError(f"Brak źródła ikony: {ICON_SOURCE}")

    with Image.open(ICON_SOURCE) as source:
        image = source.convert("RGBA")
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        image = image.resize((256, 256), Image.Resampling.LANCZOS)
        image.save(
            ICON_PATH,
            format="ICO",
            sizes=[
                (16, 16),
                (24, 24),
                (32, 32),
                (48, 48),
                (64, 64),
                (128, 128),
                (256, 256),
            ],
        )


def verify_icon() -> None:
    with Image.open(ICON_PATH) as icon:
        if icon.format != "ICO":
            raise RuntimeError(f"{ICON_PATH.name} nie jest prawdziwym plikiem ICO")
        sizes = set(icon.ico.sizes())
    required = {(16, 16), (32, 32), (48, 48), (256, 256)}
    missing = required - sizes
    if missing:
        raise RuntimeError(f"Brak wymaganych rozmiarów ikony: {sorted(missing)}")


def render(version: str) -> str:
    a, b, c, d = version_tuple(version)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, {d}),
    prodvers=({a}, {b}, {c}, {d}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041504B0',
        [
          StringStruct('CompanyName', 'Warsztat Menager'),
          StringStruct('FileDescription', 'Warsztat Menager'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'WarsztatMenager'),
          StringStruct('OriginalFilename', 'WarsztatMenager.exe'),
          StringStruct('ProductName', 'Warsztat Menager'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1045, 1200])])
  ]
)
"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    build_icon()
    verify_icon()
    version = read_version()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(version), encoding="utf-8")
    print(f"[WM-EXE] wersja: {version}")
    print(f"[WM-EXE] źródło ikony: {ICON_SOURCE}")
    print(f"[WM-EXE] ikona: {ICON_PATH} (ICO OK)")
    print(f"[WM-EXE] metadane Windows: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
