# Warsztat Menager – GitHub + Codespaces (pełny start)

Ten pakiet przygotowuje repozytorium **Warsztat Menager** do pracy na GitHubie i w **Codespaces**.
**Nie zmieniamy Twojego kodu** – tylko dodajemy pliki konfiguracyjne.

---

## 1) Utwórz repozytorium na GitHubie

1. Zaloguj się → **New** repo → nazwa np. `warsztat-menager` (private).
2. Na razie puste repo (bez plików). Skopiuj adres **HTTPS** (np. `https://github.com/user/warsztat-menager.git`).

---

## 2) Przygotuj lokalny katalog WM

1. Skopiuj do folderu projektu pliki z tej paczki:
   - `.gitignore`
   - `.gitattributes`
   - `requirements.txt`
   - `.devcontainer/devcontainer.json`
   - `setup_git_wm.bat`
2. (Opcjonalnie) Utwórz `config.sample.json` (bez haseł), jeśli masz `config.json` lokalnie.

---

## 3) Inicjalizacja GIT (Windows)

W katalogu projektu uruchom:
```
setup_git_wm.bat "Imię Nazwisko" "email@domena"
```

Skrypt zrobi:
- `git init`, doda pliki, pierwszy commit,
- włączy **Git LFS** i doda wzorce (`*.zip, *.apk, *.png, *.jpg, *.jpeg, *.xlsm`),
- poprosi o adres **HTTPS** repo i wykona `git push -u origin main`.

---

## 4) Praca w GitHub Codespaces

1. Wejdź na repo → zielony przycisk **Code** → zakładka **Codespaces** → **Create codespace on main**.
2. Po starcie kontenera: automatycznie wykona się `pip install -r requirements.txt`.
3. Edytuj kod w przeglądarce, rób commity i push.

> Uwaga: **Tkinter GUI** nie wyświetli okienek w Codespaces (to serwer Linux). Testuj GUI lokalnie (`py -3 start.py`). Jeśli chcesz podgląd GUI w przeglądarce (noVNC/X11), napisz – dorzucimy rozszerzenie devcontainer.

---

## 5) Dobre praktyki dla WM

- **`config.json` nie trafia do repo** (patrz `.gitignore`). W repo trzymaj **`config.sample.json`** z bezpiecznymi wartościami.
- **Logi, backupy, buildy** są ignorowane (patrz `.gitignore`).
- **Duże pliki** i binaria (zip, obrazy, xlsm, apk) → **Git LFS**.
- Każdy plik Pythona: nagłówek z wersją + `[INFO]/[DEBUG]` printy + stopka `# ⏹ KONIEC KODU` – bez zmian w Twoim kodzie, jeśli już to masz.

---

## 6) Skróty GIT

```bash
git status
git add .
git commit -m "[WM] opis zmiany"
git push

# Branch roboczy
git checkout -b dev
git push -u origin dev

# Tag wydania
git tag -a v1.5 -m "Release 1.5"
git push origin v1.5
```

Powodzenia! 🚀
