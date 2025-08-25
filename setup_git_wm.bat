@echo off
setlocal ENABLEDELAYEDEXPANSION
echo [WM][GIT] === Warsztat Menager: inicjalizacja repo ===

:: Usage: setup_git_wm.bat "Edwin Karolczyk" "Edwinkarolczyk@gmail.com"
if "%~1"=="" (
  echo.
  echo Uzycie: setup_git_wm.bat "Imie Nazwisko" "email@domena"
  echo (opcjonalnie) Skopiuj ten plik do katalogu projektu i uruchom z parametrami.
  echo.
)

where git >nul 2>&1 || (
  echo [ERROR] Nie znaleziono GIT. Zainstaluj Git for Windows: https://git-scm.com/download/win
  pause
  exit /b 1
)

:: Konfiguracja uzytkownika (globalnie, tylko jesli podano parametry)
if NOT "%~1"=="" git config --global user.name "%~1"
if NOT "%~2"=="" git config --global user.email "%~2"

:: Utworz podstawowe pliki jesli nie istnieja
if not exist ".gitignore" (
  echo Tworze .gitignore...
  (
    echo # patrz wersja dostarczona w paczce
  ) > .gitignore
)
if not exist ".gitattributes" (
  echo Tworze .gitattributes...
  (
    echo * text=auto
  ) > .gitattributes
)

:: Inicjalizacja repo
if not exist ".git" (
  git init || goto :fail
)

:: Ustaw branch main jesli nie ustawiony
git rev-parse --abbrev-ref HEAD >nul 2>&1
if errorlevel 1 (
  git symbolic-ref HEAD refs/heads/main 2>nul
)

:: Git LFS (opcjonalnie, ale zalecane)
git lfs version >nul 2>&1
if errorlevel 1 (
  echo [INFO] Instalacja/wlaczenie Git LFS...
  git lfs install || echo [WARN] Nie udalo sie wlaczyc LFS (kontynuujemy).
) else (
  git lfs install
  git lfs track "*.zip" "*.apk" "*.png" "*.jpg" "*.jpeg" "*.xlsm"
)

:: Przygotuj plik config.sample.json jesli jest config.json
if exist config.json if not exist config.sample.json (
  echo [INFO] Tworze config.sample.json (skopiuj i wyczysc dane wrazliwe).
  copy /Y config.json config.sample.json >nul
)

git add .gitattributes .gitignore 2>nul
git add .
git commit -m "[WM] Initial commit" || echo [INFO] Commit juz istnieje lub brak zmian.

echo.
echo [WM] Utworz teraz PUSTE repo na GitHub (np. warsztat-menager) i skopiuj jego adres HTTPS.
set /p REMOTE_URL=Podaj URL (HTTPS) nowego repo: 
if "%REMOTE_URL%"=="" (
  echo [ERROR] Nie podano URL. Przerywam.
  goto :end
)

git remote remove origin >nul 2>&1
git remote add origin "%REMOTE_URL%"
git branch -M main
git push -u origin main || goto :fail

echo.
echo [WM] Gotowe. Repo wyslane na GitHub.
goto :end

:fail
echo [WM][ERROR] Operacja nie powiodla sie. Sprawdz komunikaty powyzej.
:end
pause
