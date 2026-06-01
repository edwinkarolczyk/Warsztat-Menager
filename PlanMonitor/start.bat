@echo off
title Plan Monitor
cd /d "%~dp0"

echo ========================================
echo  PLAN MONITOR - START
echo ========================================
echo.

py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo Nie znaleziono Python 3.13 przez launcher py.
    echo Sprobuj zainstalowac Python 3.13 albo uruchom recznie:
    echo python main.py
    echo.
    pause
    exit /b 1
)

echo Sprawdzam biblioteki...
py -3.13 -m pip install pandas openpyxl xlrd

echo.
echo Uruchamiam Plan Monitor...
py -3.13 main.py

echo.
echo Program zostal zamkniety.
pause
