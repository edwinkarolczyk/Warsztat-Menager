# -*- coding: utf-8 -*-
"""Centralna wersja aplikacji WM.

UWAGA: To jest JEDYNE źródło prawdy o wersji.
Podnosimy wyłącznie tutaj (albo przez tools/bump_version.py).
"""

__version__ = "0.1"


def get_version() -> str:
    """Zwróć aktualny numer wersji aplikacji."""

    return __version__
