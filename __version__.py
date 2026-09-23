# version: 3.3
# 3.3: WM 1.0.18 - wymagaj rewizji przy zmianie statusu i uwag WMM.
# 3.2: WM 1.0.17 - migawka materiału przed zmianą ilości zlecenia.
# 3.1: WM 1.0.16 - zachowanie nierozliczonego materiału przy zmianie ilości zlecenia.
# 3.0: WM 1.0.15 - rozliczenie materiału we wspólnym edytorze i poprawny zakres planu.
# 2.9: WM 1.0.14 - wykonanie zlecenia oddzielone od świadomego rozliczenia materiału.
# 2.8: WM 1.0.13 - wspólny edytor zlecenia Planisty, usuwanie i uporządkowanie paska akcji.
# 2.7: WM 1.0.12 - naprawa widoku i wydruków w module Maszyny.
# -*- coding: utf-8 -*-
"""Centralna wersja aplikacji WM.

UWAGA: To jest JEDYNE źródło prawdy o wersji.
Podnosimy wyłącznie tutaj (albo przez tools/bump_version.py).

Zasada SemVer dla WM:
- PATCH (x.y.Z): poprawki błędów i kosmetyka bez zmiany zachowania,
- MINOR (x.Y.0): nowe funkcje i istotne usprawnienia zgodne wstecznie,
- MAJOR (X.0.0): zmiany niekompatybilne lub duża przebudowa aplikacji.
"""

__version__ = "1.0.18"


def get_version() -> str:
    """Zwróć aktualny numer wersji aplikacji."""

    return __version__
