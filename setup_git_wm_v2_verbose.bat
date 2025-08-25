@echo on
setlocal ENABLEDELAYEDEXPANSION
title WM Git setup (verbose)
echo [WM] Start: %DATE% %TIME% > wm_git_setup.log

REM === 0) Sprawdzenia srodowiska ===
where git >> wm_git_setup.log 2>&1
if errorlevel 1 (
  echo [ERROR] Git nie jest zainstalowany albo nie jest w PATH.
  echo Pobierz: https://git-scm.com/download/win
  goto end
)

git --version
if errorlevel 1 (
  echo [ERROR] Problem z uruchomieniem Git. Sprawdz instalacje.
  goto end
)

REM === 1) Konfiguracja uzytkownika (opcjonalnie) ===
if not "%~1"=="" git config --global user.name "%~1"
if not "%~2"=="" git config --global user.email "%~2"

REM === 2) Inicjalizacja repo w BIEZACYM KATALOGU ===
echo [WM] Katalog: %CD%
if not exist ".git" (
  git init || goto fail
) else (
  echo [WM] Repo juz istnieje (pomijam git init).
)

REM === 3) Git LFS ===
git lfs install >> wm_git_setup.log 2>&1
git lfs track "*.zip" "*.apk" "*.png" "*.jpg" "*.jpeg" "*.xlsm" >> wm_git_setup.log 2>&1

REM === 4) Podstawowe pliki jesli brakuje ===
if not exist ".gitignore" (
  echo # dodajemy pozniej > .gitignore
)
if not exist ".gitattributes" (
  echo * text=auto > .gitattributes
)

REM === 5) Przyklad config.sample.json ===
if exist config.json if not exist config.sample.json (
  copy /Y config.json config.sample.json >nul
)

REM === 6) Commit startowy ===
git add .gitattributes .gitignore 2>nul
git add .
git commit -m "[WM] Initial commit" || echo [WM] (brak zmian albo commit juz istnieje)

REM === 7) Ustawienie zdalnego repo ===
if "%~3"=="" (
  set /p REMOTE_URL=Podaj URL HTTPS repo (np. https://github.com/edwinkarolczyk/Warsztat-Menager.git): 
) else (
  set "REMOTE_URL=%~3"
)

if "%REMOTE_URL%"=="" (
  echo [ERROR] Nie podano adresu repo.
  goto end
)

git remote -v | findstr /I "origin" >nul
if not errorlevel 1 git remote remove origin

git remote add origin "%REMOTE_URL%"
git branch -M main
git push -u origin main || goto fail

echo [WM] Sukces. Repo wyslane: %REMOTE_URL%
goto end

:fail
echo [WM][ERROR] Cos poszlo nie tak. Zobacz wm_git_setup.log i komunikaty powyzej.

:end
pause
