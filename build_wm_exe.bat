@echo off
REM Build Warsztat-Menager into a standalone Windows onedir package using PyInstaller.
setlocal enabledelayedexpansion

pushd %~dp0

set "WM_BUILD_DIR=%CD%\build"
set "WM_DIST_DIR=%CD%\dist"

if not exist "%WM_BUILD_DIR%" mkdir "%WM_BUILD_DIR%"
if not exist "%WM_DIST_DIR%" mkdir "%WM_DIST_DIR%"

echo [WM-EXE] Preparing Windows icon and version metadata...
py -3.13 "%CD%\tools\generate_windows_version_info.py"
if errorlevel 1 goto :fail

echo [WM-EXE] Building WarsztatMenager.exe...
py -3.13 -m PyInstaller --noconfirm --clean ^
    --workpath "%WM_BUILD_DIR%\pyinstaller" ^
    --distpath "%WM_DIST_DIR%" ^
    "%CD%\wm.spec"
if errorlevel 1 goto :fail

if not exist "%WM_DIST_DIR%\WarsztatMenager\WarsztatMenager.exe" (
    echo [WM-EXE][ERROR] Missing dist\WarsztatMenager\WarsztatMenager.exe
    goto :fail
)

for %%I in ("%WM_DIST_DIR%\WarsztatMenager\WarsztatMenager.exe") do (
    echo [WM-EXE] OK: %%~fI
    echo [WM-EXE] EXE size: %%~zI bytes
)

popd
endlocal
exit /b 0

:fail
echo [WM-EXE][ERROR] Build failed.
popd
endlocal
exit /b 1
