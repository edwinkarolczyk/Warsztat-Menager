from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional

from config.paths import get_path

# USTAWIENIA DOMYŚLNE:
# - repo_dir: katalog repozytorium z Git (domyślnie: bieżący katalog aplikacji)
# - data_root: katalog danych do backupu/restore (z Ustawień → System → Ścieżki danych)
# - backup_dir: katalog docelowy backupów ZIP

def _run(cmd: list[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Uruchom komendę, zwróć (rc, stdout, stderr)."""
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False
        # UWAGA: shell=False ze względów bezpieczeństwa
    )
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()

def _timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def repo_git_dir() -> str:
    # Możesz zmienić na odczyt z ustawień, np. "updates.repo_dir" jeśli wprowadzisz taki klucz.
    return os.getcwd()

def git_pull() -> dict:
    """
    Pull na bieżącej gałęzi repozytorium.
    Zwraca dict: {ok: bool, msg: str}
    """
    cwd = repo_git_dir()
    if not os.path.isdir(os.path.join(cwd, ".git")):
        return {"ok": False, "msg": f"Nie znaleziono repozytorium .git w: {cwd}"}

    rc, out, err = _run(["git", "pull"], cwd=cwd)
    if rc == 0:
        return {"ok": True, "msg": f"git pull OK\n{out}"}
    return {"ok": False, "msg": f"git pull ERROR\n{err or out}"}

def pull_branch(branch: str) -> dict:
    """
    Pobierz wskazaną gałąź (fetch + checkout + pull).
    """
    if not branch:
        return {"ok": False, "msg": "Brak nazwy gałęzi."}

    cwd = repo_git_dir()
    if not os.path.isdir(os.path.join(cwd, ".git")):
        return {"ok": False, "msg": f"Nie znaleziono repozytorium .git w: {cwd}"}

    steps = []

    rc, out, err = _run(["git", "fetch", "origin", branch], cwd=cwd)
    steps.append(("fetch", rc, out, err))
    if rc != 0:
        return {"ok": False, "msg": f"git fetch ERROR\n{err or out}"}

    rc, out, err = _run(["git", "checkout", branch], cwd=cwd)
    steps.append(("checkout", rc, out, err))
    if rc != 0:
        return {"ok": False, "msg": f"git checkout '{branch}' ERROR\n{err or out}"}

    rc, out, err = _run(["git", "pull", "origin", branch], cwd=cwd)
    steps.append(("pull", rc, out, err))
    if rc != 0:
        return {"ok": False, "msg": f"git pull origin '{branch}' ERROR\n{err or out}"}

    return {"ok": True, "msg": "OK: " + " → ".join([s for s, r, _, _ in steps])}

def backup_zip() -> dict:
    """
    Tworzy ZIP całego data_root do katalogu backup_dir.
    Plik: backup-{timestamp}.zip
    """
    data_root = get_path("paths.data_root")
    backup_dir = get_path("paths.backup_dir")
    if not data_root or not os.path.isdir(data_root):
        return {"ok": False, "msg": f"Brak katalogu danych: {data_root!r}"}

    os.makedirs(backup_dir, exist_ok=True)
    out_zip = os.path.join(backup_dir, f"backup-{_timestamp()}.zip")

    # Kompilujemy listę plików do ZIP (bez samego katalogu backup)
    def _should_include(path: str) -> bool:
        # Nie pakuj katalogu backup do samego siebie
        try:
            return not os.path.commonpath([path, backup_dir]) == backup_dir
        except Exception:
            return True

    with tempfile.TemporaryDirectory() as _tmp:
        # Standardowe shutil.make_archive (wygodne), ale ono pakuje cały folder.
        # Upewniamy się, że backup_dir nie jest pod data_root, a jeśli jest — filtrujemy ręcznie.
        if os.path.commonpath([data_root]) == os.path.commonpath([data_root, backup_dir]):
            # backup_dir jest w data_root — tworzymy filtr
            import zipfile
            with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(data_root):
                    # pomijamy backup_dir
                    dirs[:] = [d for d in dirs if _should_include(os.path.join(root, d))]
                    for name in files:
                        full = os.path.join(root, name)
                        if _should_include(full):
                            arc = os.path.relpath(full, data_root)
                            zf.write(full, arc)
        else:
            shutil.make_archive(out_zip[:-4], "zip", root_dir=data_root)

    return {"ok": True, "msg": f"Utworzono backup: {out_zip}", "path": out_zip}

def _extract_zip_to_dir(zip_path: str, target_dir: str) -> None:
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

def restore_from_zip(zip_path: str) -> dict:
    """
    Przywraca zawartość ZIP do data_root (nadpisuje istniejące pliki).
    """
    data_root = get_path("paths.data_root")
    if not os.path.isfile(zip_path):
        return {"ok": False, "msg": f"Nie znaleziono pliku: {zip_path}"}
    if not data_root:
        return {"ok": False, "msg": "Brak skonfigurowanego katalogu data_root."}

    # Ostrożność: wypakuj do katalogu tymczasowego i skopiuj, aby zminimalizować ryzyko
    with tempfile.TemporaryDirectory() as tmp:
        _extract_zip_to_dir(zip_path, tmp)

        # Kopiuj pliki z tmp do data_root (nadpisuj)
        for root, dirs, files in os.walk(tmp):
            rel = os.path.relpath(root, tmp)
            dst_root = os.path.join(data_root, rel) if rel != "." else data_root
            os.makedirs(dst_root, exist_ok=True)
            for f in files:
                src = os.path.join(root, f)
                dst = os.path.join(dst_root, f)
                shutil.copy2(src, dst)

    return {"ok": True, "msg": f"Przywrócono z: {zip_path}"}

# restore_dialog wywołujemy z UI przez settings_action_handlers (otwiera filedialog)
# i przekazuje wybrany ZIP tutaj (albo tu też można dodać dialog, ale trzymamy UI w jednym miejscu).
