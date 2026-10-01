# version: 4.4
# 4.4: WM 1.0.29 - Planista pokazuje postęp półproduktów zamiast Wersji BOM.
# 4.3: WM 1.0.28 - czytelniejsze Dyspozycje: Typ/ID/Obiekt osobno, auto-szerokość kolumn i kolumny dodatkowe.
# 4.2: WM 1.0.27 - dodawanie punktów obrysu pomieszczeń i ortogonalne przeciąganie narożników z Shift.
# 4.1: WM 1.0.26 - poprawki ROOT/CONFIG widoku Maszyn oraz odzyskiwanie tła i pomieszczeń hali.
# 4.0: WM 1.0.25 - trwałe czyszczenie duplikatów przeglądów przy wczytaniu aktywnego pliku maszyn.
# 3.9: WM 1.0.24 - naprawa duplikatów przeglądów maszyn i QR zlecenia Planisty dla WMM.
# 3.8: WM 1.0.23 - Dyspozycje Magazynu pokazują dane live i przechodzą do pozycji w głównym module Magazyn.
# 3.7: WM 1.0.22 - jedna instancja WM, nawigacja Dyspozycji w głównym panelu i większa edycja Maszyn.
# 3.6: WM 1.0.21 - stabilizacja WM/WMM: API 0.5.31, EXE tray, idempotencja i blokady urlopów.
# 3.5: WM 1.0.20 - kontrola salda płatnego urlopu; wyjątek brygadzisty z przyczyną i historią.
# 3.4: WM 1.0.19 - API WMM uruchamiane z WM; ikona obok zegara i powiadomienia o połączeniu.
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

__version__ = "1.0.29"


def get_version() -> str:
    """Zwróć aktualny numer wersji aplikacji."""

    return __version__
