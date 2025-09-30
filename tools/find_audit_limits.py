"""Narzędzie do wyszukiwania potencjalnych limitów audytu w kodzie."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SUFFIXES = (".py", ".json", ".md")
DEFAULT_PATTERNS = (
    r"\[:10\]",  # slicing do 10
    r"\bmax_items\s*=\s*10\b",  # domyślny parametr 10
    r"\bAUDIT_LIMIT\s*=\s*10\b",  # stała limitu
    r"\bAUDIT_CASES\s*=\s*\[",  # tablica rejestru testów
    r"\baudit\s*\.\s*run\b",  # miejsca wywołania audytu
    r"\brun_audit\b",  # popularna nazwa wrappera
)
SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache"}


@dataclass(slots=True)
class Hit:
    """Opis pojedynczego dopasowania."""

    path: Path
    line: int
    pattern: str
    snippet: str


def iter_source_files(root: Path, suffixes: Sequence[str]) -> Iterator[Path]:
    """Iteruje po plikach źródłowych z repozytorium."""

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(tuple(suffixes)):
                yield Path(dirpath) / filename


def compile_patterns(patterns: Sequence[str]) -> List[re.Pattern[str]]:
    """Kompiluje wzorce regex, aby przyspieszyć wyszukiwanie."""

    return [re.compile(pattern) for pattern in patterns]


def find_hits(path: Path, patterns: Sequence[re.Pattern[str]]) -> Iterable[Hit]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    hits: List[Hit] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            snippet = text[match.start() : match.start() + 80].replace("\n", "\\n")
            hits.append(Hit(path=path, line=line, pattern=pattern.pattern, snippet=snippet))
    return hits


def scan(root: Path, suffixes: Sequence[str], patterns: Sequence[str]) -> List[Hit]:
    compiled = compile_patterns(patterns)
    results: List[Hit] = []
    for file_path in iter_source_files(root, suffixes):
        results.extend(find_hits(file_path, compiled))
    return results


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wyszukuje potencjalne limity audytu w kodzie.")
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=ROOT,
        help="Katalog startowy (domyślnie katalog repozytorium).",
    )
    parser.add_argument(
        "--suffix",
        dest="suffixes",
        action="append",
        default=list(DEFAULT_SUFFIXES),
        help="Rozszerzenie pliku do uwzględnienia (można podać wielokrotnie).",
    )
    parser.add_argument(
        "--pattern",
        dest="patterns",
        action="append",
        default=list(DEFAULT_PATTERNS),
        help="Dodatkowy wzorzec regex do wyszukania (można podać wielokrotnie).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    hits = scan(args.root, args.suffixes, args.patterns)

    if not hits:
        print(
            "[AUDIT-SCAN] Brak ewidentnych limitów/registry w kodzie (sprawdź ręcznie gui_settings*.py i audit*.py)"
        )
        return 0

    print("[AUDIT-SCAN] Kandydaci (plik:linia :: dopasowanie → snippet):")
    for hit in hits:
        print(f" - {hit.path}:{hit.line} :: {hit.pattern} → {hit.snippet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
