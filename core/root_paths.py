# version: 1.0
"""Centralny resolver ROOT dla Warsztat Menager.

APP_ROOT = folder programu / repozytorium / Git
WM_ROOT  = folder danych wybrany przez użytkownika
DATA_ROOT = WM_ROOT / "data"

Ten moduł nie dotyka mechanizmu aktualizacji Git.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT_FILE_NAME = "wm_root.json"

_LAST_CREATED_ITEMS: list[str] = []


def _write_json_if_missing(path: Path, payload: Any) -> bool:
    """Tworzy plik JSON tylko wtedy, gdy go nie ma."""

    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return True


def _default_profiles_payload() -> dict[str, Any]:
    return {
        "users": [
            {
                "login": "admin",
                "haslo": "nimda",
                "pin": "nimda",
                "rola": "administrator",
                "active": True,
                "disabled_modules": [],
            }
        ]
    }


def _norm(path: Path | str) -> Path:
    p = path if isinstance(path, Path) else Path(str(path))
    try:
        return p.expanduser().resolve()
    except Exception:
        return p.expanduser()


def get_app_root() -> Path:
    """Zwraca folder programu/repozytorium, a nie folder danych."""

    if getattr(sys, "frozen", False):
        return _norm(Path(sys.executable).parent)
    return _norm(Path(__file__).resolve().parents[1])


def root_file_path(app_root: Path | None = None) -> Path:
    return _norm((app_root or get_app_root()) / ROOT_FILE_NAME)


def _read_root_file(path: Path) -> Path | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            raw = str(payload.get("root") or "").strip()
        else:
            raw = ""
        if not raw:
            return None
        return _norm(Path(raw))
    except Exception as exc:
        print(f"[WM-ROOT][WARN] Nie można odczytać {path}: {exc}")
        return None


def _write_root_file(path: Path, wm_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"root": str(wm_root)}, handle, ensure_ascii=False, indent=2)


def _default_wm_root() -> Path:
    """Tylko katalog startowy dla okna wyboru; nie jest automatycznie zapisywany."""
    try:
        return _norm(Path.home())
    except Exception:
        return _norm(get_app_root())


def _ask_root_folder(initial: Path) -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo(
                "Wybór głównego folderu danych WM",
                "Wskaż folder, w którym Warsztat Menager ma trzymać dane.\n\n"
                "Może to być dowolny folder na dysku lub pendrive, np.:\n"
                "D:\\Dane_WM\n"
                "E:\\Warsztat_Root\n"
                "C:\\Moje_Dane_Warsztatu\n\n"
                "Program utworzy w nim katalogi: data, logs, backup, assets.\n\n"
                "Nie wybieraj folderu programu.\n"
                "Nie wybieraj samego folderu data.",
                parent=root,
            )
        except Exception:
            pass
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=str(initial),
            title="Wybierz główny folder danych WM",
        )
        root.destroy()
    except Exception as exc:
        print(f"[WM-ROOT][WARN] Nie udało się pokazać wyboru ROOT: {exc}")
        return None

    if not selected:
        return None
    return _norm(Path(selected))


def resolve_wm_root(*, prompt: bool = False) -> Path:
    """Ustal WM_ROOT z ENV, wm_root.json albo wyboru użytkownika."""

    app_root = get_app_root()

    env_root = os.environ.get("WM_ROOT") or os.environ.get("WM_APP_ROOT")
    if env_root:
        wm_root = _norm(Path(env_root))
        return wm_root

    pointer = root_file_path(app_root)
    from_file = _read_root_file(pointer)
    if from_file is not None:
        return from_file

    initial = _default_wm_root()
    selected = _ask_root_folder(initial) if prompt else None
    if selected is None and prompt:
        raise RuntimeError(
            "Nie wybrano głównego folderu danych WM. "
            "Wybierz folder ROOT, aby program wiedział gdzie zapisywać dane."
        )
    wm_root = selected or initial
    try:
        _write_root_file(pointer, wm_root)
        print(f"[WM-ROOT][BOOT] Zapisano ROOT_FILE: {pointer}")
    except Exception as exc:
        print(f"[WM-ROOT][WARN] Nie można zapisać ROOT_FILE {pointer}: {exc}")
    return wm_root


def get_root_anchor() -> Path:
    return resolve_wm_root(prompt=False)


def get_data_root() -> Path:
    return get_root_anchor() / "data"


def path_config() -> Path:
    return get_root_anchor() / "config.json"


def path_logs() -> Path:
    return get_root_anchor() / "logs"


def path_backup() -> Path:
    return get_root_anchor() / "backup"


def path_assets() -> Path:
    return get_root_anchor() / "assets"


def path_profiles() -> Path:
    return get_data_root() / "profiles.json"


def path_tools_dir() -> Path:
    return get_data_root() / "narzedzia"


def path_machines() -> Path:
    return get_data_root() / "maszyny" / "maszyny.json"


def path_warehouse() -> Path:
    return get_data_root() / "magazyn" / "magazyn.json"


def path_bom() -> Path:
    return get_data_root() / "produkty" / "bom.json"


def path_orders_dir() -> Path:
    return get_data_root() / "zlecenia"


def path_dyspozycje() -> Path:
    return get_data_root() / "dyspozycje" / "dyspozycje.json"


def ensure_root_tree() -> list[str]:
    """Tworzy strukturę katalogów i pliki startowe wyłącznie pod WM_ROOT."""

    global _LAST_CREATED_ITEMS
    dirs = [
        get_root_anchor(),
        get_data_root(),
        path_logs(),
        path_backup(),
        path_assets(),
        get_data_root() / "user",
        path_tools_dir(),
        get_data_root() / "maszyny",
        get_data_root() / "magazyn",
        get_data_root() / "produkty",
        get_data_root() / "polprodukty",
        path_orders_dir(),
        get_data_root() / "dyspozycje",
        get_data_root() / "layout",
    ]
    created: list[str] = []
    for directory in dirs:
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(f"DIR  {directory}")
            print(f"[WM-ROOT][CREATE] dir={directory}")

    starter_files: list[tuple[Path, Any]] = [
        (
            path_config(),
            {
                "paths": {
                    "anchor_root": str(get_root_anchor()),
                    "data_root": str(get_data_root()),
                    "logs_dir": str(path_logs()),
                    "backup_dir": str(path_backup()),
                    "assets_dir": str(path_assets()),
                    "layout_dir": str(get_data_root() / "layout"),
                }
            },
        ),
        (path_profiles(), _default_profiles_payload()),
        (path_machines(), {"maszyny": []}),
        (path_warehouse(), {"items": {}, "meta": {}}),
        (path_bom(), {"items": []}),
        (path_dyspozycje(), {"version": 1, "items": []}),
        (get_data_root() / "magazyn" / "katalog.json", {}),
        (get_data_root() / "magazyn" / "stany.json", {}),
        (get_data_root() / "magazyn" / "przyjecia.json", []),
        (get_data_root() / "magazyn" / "_seq_pz.json", {}),
        (get_data_root() / "magazyn" / "magazyn_history.json", []),
    ]

    for file_path, payload in starter_files:
        try:
            if _write_json_if_missing(file_path, payload):
                created.append(f"FILE {file_path}")
                print(f"[WM-ROOT][CREATE] file={file_path}")
        except Exception as exc:
            print(
                f"[WM-ROOT][WARN] Nie można utworzyć pliku startowego "
                f"{file_path}: {exc}"
            )

    _LAST_CREATED_ITEMS = created
    return created


def get_last_created_items() -> list[str]:
    return list(_LAST_CREATED_ITEMS)


def show_created_root_info(created: list[str] | None = None) -> None:
    """Pokazuje użytkownikowi, co zostało utworzone w ROOT."""

    items = created if created is not None else get_last_created_items()
    if not items:
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        preview = "\n".join(items[:18])
        suffix = "" if len(items) <= 18 else f"\n... oraz {len(items) - 18} więcej"
        messagebox.showinfo(
            "Utworzono strukturę danych WM",
            "Program utworzył brakujące foldery/pliki w wybranym ROOT.\n\n"
            f"ROOT:\n{get_root_anchor()}\n\n"
            f"DATA:\n{get_data_root()}\n\n"
            f"Utworzono:\n{preview}{suffix}",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass


def install_environment(*, prompt: bool = False) -> dict[str, str]:
    """Ustawia ENV dla reszty aplikacji i zwraca snapshot ścieżek."""

    wm_root = resolve_wm_root(prompt=prompt)
    data_root = wm_root / "data"

    os.environ["WM_ROOT"] = str(wm_root)
    os.environ["WM_APP_ROOT"] = str(wm_root)
    os.environ["WM_DATA_ROOT"] = str(data_root)
    os.environ["WM_CONFIG_FILE"] = str(wm_root / "config.json")

    created = ensure_root_tree()
    show_created_root_info(created)

    return {
        "app_root": str(get_app_root()),
        "root_file": str(root_file_path()),
        "wm_root": str(wm_root),
        "config": str(path_config()),
        "data_root": str(data_root),
        "profiles": str(path_profiles()),
        "tools_dir": str(path_tools_dir()),
        "machines": str(path_machines()),
        "warehouse": str(path_warehouse()),
        "bom": str(path_bom()),
        "orders_dir": str(path_orders_dir()),
        "dyspozycje": str(path_dyspozycje()),
        "logs_dir": str(path_logs()),
        "backup_dir": str(path_backup()),
    }


def print_root_diagnostics(snapshot: dict[str, Any] | None = None) -> None:
    snap = snapshot or install_environment(prompt=False)
    print("[WM-ROOT][BOOT] =====================================")
    print(f"[WM-ROOT][BOOT] APP_ROOT    = {snap.get('app_root')}")
    print(f"[WM-ROOT][BOOT] ROOT_FILE   = {snap.get('root_file')}")
    print(f"[WM-ROOT][BOOT] WM_ROOT     = {snap.get('wm_root')}")
    print(f"[WM-ROOT][BOOT] CONFIG      = {snap.get('config')}")
    print(f"[WM-ROOT][BOOT] DATA_ROOT   = {snap.get('data_root')}")
    print(f"[WM-ROOT][BOOT] PROFILES    = {snap.get('profiles')}")
    print(f"[WM-ROOT][BOOT] TOOLS_DIR   = {snap.get('tools_dir')}")
    print(f"[WM-ROOT][BOOT] MACHINES    = {snap.get('machines')}")
    print(f"[WM-ROOT][BOOT] WAREHOUSE   = {snap.get('warehouse')}")
    print(f"[WM-ROOT][BOOT] BOM         = {snap.get('bom')}")
    print(f"[WM-ROOT][BOOT] ORDERS_DIR  = {snap.get('orders_dir')}")
    print(f"[WM-ROOT][BOOT] DYSP_FILE   = {snap.get('dyspozycje')}")
    print(f"[WM-ROOT][BOOT] LOGS_DIR    = {snap.get('logs_dir')}")
    print(f"[WM-ROOT][BOOT] BACKUP_DIR  = {snap.get('backup_dir')}")
    print("[WM-ROOT][BOOT] =====================================")

    app_data = get_app_root() / "data"
    try:
        if app_data.exists() and _norm(app_data) != _norm(get_data_root()):
            print(f"[WM-ROOT][WARN] Wykryto lokalny folder data przy programie: {app_data}")
            print(f"[WM-ROOT][WARN] Aktywny DATA_ROOT: {get_data_root()}")
            print("[WM-ROOT][WARN] Lokalny folder data nie powinien być używany.")
    except Exception:
        pass
