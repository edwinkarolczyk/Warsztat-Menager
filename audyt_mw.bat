@echo off
REM Start bat dla audyt_mw.py
REM Użycie: audyt_mw_start.bat "C:\sciezka\do\MW"

setlocal ENABLEDELAYEDEXPANSION

if "%~1"=="" (
    set ROOT=%cd%
) else (
    set ROOT=%~1
)

REM Sprawdź czy python jest dostępny
python --version >nul 2>&1
if errorlevel 1 (
    echo [BŁĄD] Python nie jest zainstalowany lub nie jest w PATH.
    pause
    exit /b 1
)

echo [MW] Uruchamianie audytu dla katalogu: %ROOT%
python "%~dp0audyt_mw.py" "%ROOT%"

echo.
echo [OK] Audyt zakończony. Sprawdź pliki audit_mw_report.json oraz audit_mw_report.md w katalogu %ROOT%.
pause
