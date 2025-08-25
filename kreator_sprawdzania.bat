@echo off
REM ============================================
REM Kreator sprawdzania plikow i wersji – WM
REM ============================================

set ROOT=%~dp0
set PY=python

echo.
echo [INFO] Uruchamianie kreatora sprawdzania w katalogu:
echo %ROOT%
echo.

%PY% "%ROOT%kreator_sprawdzenia.py" --root "%ROOT%" --report "%ROOT%raport_sprawdzenia.txt" --pause

echo.
echo [INFO] Raport zostal zapisany do: raport_sprawdzenia.txt
echo.
pause
