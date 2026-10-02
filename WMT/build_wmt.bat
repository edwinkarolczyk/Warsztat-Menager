@echo off
setlocal
cd /d "%~dp0\.."
py -3.13 -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name WMT --add-data "WMT\bridge_sitecustomize.py;WMT" WMT\WMT.py --distpath WMT\dist --workpath WMT\build
if errorlevel 1 exit /b 1
echo.
echo GOTOWE: %CD%\WMT\dist\WMT.exe
endlocal
