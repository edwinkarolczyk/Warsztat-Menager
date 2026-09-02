# version: 1.1
# -*- coding: utf-8 -*-
"""Centralna wersja aplikacji WM.

UWAGA: To jest JEDYNE źródło prawdy o wersji.
Podnosimy wyłącznie tutaj (albo przez tools/bump_version.py).

Zasada SemVer dla WM:
- PATCH (x.y.Z): poprawki błędów i kosmetyka bez zmiany zachowania,
- MINOR (x.Y.0): nowe funkcje i istotne usprawnienia zgodne wstecznie,
- MAJOR (X.0.0): zmiany niekompatybilne lub duża przebudowa aplikacji.
"""

__version__ = "0.4.1"


def get_version() -> str:
    """Zwróć aktualny numer wersji aplikacji."""

    return __version__
