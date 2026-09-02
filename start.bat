@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM → Zminimalizuj okno CMD, aby schowało się na pasek zadań
powershell -NoProfile -Command ^
  "$signature = '[DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd,int nCmdShow);'; " ^
  "Add-Type -MemberDefinition $signature -Name 'Win32ShowWindow' -Namespace 'Native' | Out-Null; " ^
  "$hwnd = (Get-Process -Id $PID).MainWindowHandle; " ^
  "[Native.Win32ShowWindow]::ShowWindowAsync($hwnd, 6) | Out-Null"

REM → Uruchom program Warsztat Menager
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

set "PYTHON_EXE="
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3.10" "py -3.9" "py -3" "python" "python3") do (
  if not defined PYTHON_EXE (
    call :_detect_python %%~C
  )
)

if not defined PYTHON_EXE (
  echo [ERROR] Nie znaleziono interpretera Python 3.x.
  echo        Zainstaluj Pythona lub dodaj go do zmiennej PATH.
  pause
  exit /b 1
)

echo [INFO] Używam Pythona: %PYTHON_EXE%
echo [INFO] Katalog roboczy: "%cd%"

%PYTHON_EXE% -u wm_launch.py
set ERR=%ERRORLEVEL%

endlocal & set ERR=%ERR%

if %ERR% NEQ 0 (
  echo [ERROR] Program zakończył się kodem %ERR%.
) else (
  echo [INFO] Zakończono pomyślnie.
)
pause
exit /b %ERR%

:_detect_python
set "_CANDIDATE=%*"
if "%_CANDIDATE%"=="" exit /b
echo [INFO] Szukam interpretera: %_CANDIDATE%
%_CANDIDATE% -c "import sys" >nul 2>&1
if errorlevel 1 exit /b
set "PYTHON_EXE=%_CANDIDATE%"
exit /b
