@echo off
REM === Generowanie RAW linków do WSZYSTKICH plików w gałęzi Rozwiniecie (CMD) ===
setlocal enabledelayedexpansion

REM --- KONFIG ---
set "OWNER=edwinkarolczyk"
set "REPO=Warsztat-Menager"
set "BRANCH=Rozwiniecie"
set "REPO_DIR=C:\Warsztat\WM\Warsztat-Menager"

REM --- WSTĘPNE SPRAWDZENIA ---
where git >nul 2>nul || (echo [ERROR] Git nie jest w PATH & exit /b 1)
if not exist "%REPO_DIR%\.git" (
  echo [ERROR] Nie znaleziono repozytorium w "%REPO_DIR%"
  exit /b 1
)

cd /d "%REPO_DIR%" || (echo [ERROR] Nie moge przejsc do "%REPO_DIR%" & exit /b 1)
del /q raw_links.txt 2>nul

echo [WM-DBG] Generuje linki z: %CD%
for /f "delims=" %%F in ('git ls-files') do (
  for /f "usebackq delims=" %%U in (`
    powershell -NoLogo -NoProfile -Command "$p='%%F'; $u=[System.Uri]::EscapeDataString($p) -replace '%%2F','/'; 'https://raw.githubusercontent.com/%OWNER%/%REPO%/%BRANCH%/'+$u"
  `) do (
    echo %%U>>raw_links.txt
  )
)

echo.
echo [WM-DBG] Gotowe: raw_links.txt
echo [WM-DBG] Przykladowy pierwszy link:
for /f "usebackq delims=" %%L in (`more +0 raw_links.txt ^| cmd /v:on /c "set/p=&& echo:"`) do (
  echo %%L
  goto :afterpreview
)
:afterpreview
echo.
pause
