@echo off
setlocal
cd /d "%~dp0\.."
py -3.13 -c "import base64,gzip,pathlib; p=pathlib.Path(r'WMT\WMT.py.gz.b64'); pathlib.Path(r'WMT\WMT.py').write_bytes(gzip.decompress(base64.b64decode(p.read_text(encoding='ascii'))))"
if errorlevel 1 exit /b 1
py -3.13 -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name WMT --icon 11.ico WMT\WMT.py --distpath WMT\dist --workpath WMT\build
if errorlevel 1 exit /b 1
echo.
echo GOTOWE: %CD%\WMT\dist\WMT.exe
endlocal
