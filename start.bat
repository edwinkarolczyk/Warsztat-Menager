@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

set "PY_EMB=%~dp0Files\Python313\python.exe"
set "PYTHON_EXE="

if exist "%PY_EMB%" (
  set "PYTHON_EXE=%PY_EMB%"
) else (
  for %%P in ("py -3.13" "py -3.12" "py -3.11" "python" "python3") do (
    call %%~P -c "import sys;print(sys.version)" >nul 2>nul
    if !errorlevel! EQU 0 (
      set "PYTHON_EXE=%%~P"
      goto :found
    )
  )
)

:found
if not defined PYTHON_EXE (
  echo [ERROR] Nie znaleziono Pythona.
  pause
  exit /b 1
)

echo [INFO] Uzywam Pythona: %PYTHON_EXE%
echo [INFO] Katalog roboczy: "%cd%"

%PYTHON_EXE% -u "%~dp0start.py"
set ERR=%ERRORLEVEL%

if %ERR% NEQ 0 (
  echo [ERROR] Program zakonczyl sie kodem %ERR%.
) else (
  echo [INFO] Zakonczono pomyslnie.
)
pause
exit /b %ERR%
