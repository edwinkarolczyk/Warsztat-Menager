# version: 1.0
"""Źródła danych dla Dyspozycji (bez GUI)."""

from __future__ import annotations

import json
import os
import sys
from typing import List, Tuple

try:
    print(f"[WM-DBG][DYSP][SRC] module_file={__file__}")
except Exception:
    pass

try:
    from config_manager import ConfigManager, get_config, get_machines_path, resolve_rel
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore
    get_config = None  # type: ignore
    get_machines_path = None  # type: ignore
    resolve_rel = None  # type: ignore

try:
    from core import root_paths as wm_root_paths
except Exception:  # pragma: no cover
    wm_root_paths = None  # type: ignore


def _runtime_cfg_manager():
    try:
        start_mod = sys.modules.get("start")
        if start_mod is not None:
            mgr = getattr(start_mod, "CONFIG_MANAGER", None)
            if mgr is not None:
                try:
                    print(
                        "[WM-DBG][DYSP][SRC] runtime manager=start.CONFIG_MANAGER "
                        f"{type(mgr).__name__}"
                    )
                except Exception:
                    pass
                return mgr
    except Exception:
        pass
    if ConfigManager is not None:
        try:
            mgr = ConfigManager()
            try:
                print(
                    "[WM-DBG][DYSP][SRC] runtime manager=ConfigManager() "
                    f"{type(mgr).__name__}"
                )
            except Exception:
                pass
            return mgr
        except Exception:
            pass
    return None


def _cfg() -> dict:
    mgr = _runtime_cfg_manager()
    if mgr is not None and hasattr(mgr, "load"):
        try:
            cfg = mgr.load() or {}
            try:
                paths = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
                print(
                    "[WM-DBG][DYSP][SRC] cfg paths:"
                    f" anchor_root={paths.get('anchor_root')}"
                    f" data_root={paths.get('data_root')}"
                    f" logs_dir={paths.get('logs_dir')}"
                )
            except Exception:
                pass
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    if callable(get_config):
        try:
            cfg = get_config() or {}
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    if ConfigManager is not None:
        try:
            cfg = ConfigManager().load() or {}
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    return {}


def _root_path(*parts: str) -> str:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        try:
            path_anchor = getattr(mgr, "path_anchor", None)
            if callable(path_anchor):
                result = os.path.join(str(path_anchor()), *parts)
                try:
                    print(f"[WM-DBG][DYSP][SRC] path_anchor{parts} -> {result}")
                except Exception:
                    pass
                return result
        except Exception:
            pass
    try:
        cfg = _cfg()
        paths = cfg.get("paths") or {}
        anchor = str(paths.get("anchor_root") or "").strip()
        if anchor:
            result = os.path.join(anchor, *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] cfg_anchor{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    return os.path.join(os.getcwd(), *parts)


def _data_path(*parts: str) -> str:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        try:
            path_data = getattr(mgr, "path_data", None)
            if callable(path_data):
                result = path_data(*parts)
                try:
                    print(f"[WM-DBG][DYSP][SRC] path_data{parts} -> {result}")
                except Exception:
                    pass
                return result
        except Exception:
            pass
    try:
        if wm_root_paths is not None:
            result = os.path.join(str(wm_root_paths.get_data_root()), *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] root_paths_data{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    try:
        cfg = _cfg()
        paths = cfg.get("paths") or {}
        data_root = str(paths.get("data_root") or "").strip()
        if data_root:
            result = os.path.join(data_root, *parts)
            try:
                print(f"[WM-DBG][DYSP][SRC] cfg_data{parts} -> {result}")
            except Exception:
                pass
            return result
    except Exception:
        pass
    return os.path.join("data", *parts)


def _tools_dir_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_tools_dir())
        except Exception:
            pass
    return _data_path("narzedzia")


def _machines_file_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_machines())
        except Exception:
            pass
    return _data_path("maszyny", "maszyny.json")


def _warehouse_file_path() -> str:
    if wm_root_paths is not None:
        try:
            return str(wm_root_paths.path_warehouse())
        except Exception:
            pass
    return _data_path("magazyn", "magazyn.json")


def _magazyn_dir_path() -> str:
    return _data_path("magazyn")


def _produkty_dir_path() -> str:
    return _data_path("produkty")


def _polprodukty_dir_path() -> str:
    return _data_path("polprodukty")


def _first_existing_path(*candidates: str | None) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        try:
            if os.path.exists(candidate):
                return candidate
        except Exception:
            continue
    return None


def _root_json_path(folder: str, filename: str) -> str:
    # Legacy helper zostawiony dla kompatybilności.
    # Nowe źródła kreatora Dyspozycji mają używać <ROOT>/data przez _data_path().
    return _root_path(folder, filename)


# =========================================================
# NARZĘDZIA
# =========================================================
def load_tool_choices() -> List[Tuple[str, str]]:
    tools_dir = _tools_dir_path()
    try:
        print(f"[WM-DBG][DYSP][SRC] tools_dir_selected={tools_dir}")
    except Exception:
        pass
    out = []

    try:
        for filename in sorted(os.listdir(tools_dir)):
            if not filename.endswith(".json"):
                continue

            file_stem = os.path.splitext(filename)[0].strip()
            if not file_stem.isdigit():
                continue

            path = os.path.join(tools_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            except Exception:
                continue

            if isinstance(doc, dict) and isinstance(doc.get("narzedzie"), dict):
                doc = doc.get("narzedzie") or {}
            elif isinstance(doc, dict) and isinstance(doc.get("tool"), dict):
                doc = doc.get("tool") or {}

            tool_id = str(
                doc.get("id")
                or doc.get("nr")
                or doc.get("numer")
                or file_stem
            ).strip()
            name = str(
                doc.get("nazwa")
                or doc.get("name")
                or doc.get("opis")
                or ""
            ).strip()

            if not tool_id:
                continue

            label = f"{tool_id} - {name}" if name else tool_id
            out.append((tool_id, label))

    except Exception:
        return []

    return out


# =========================================================
# MASZYNY
# =========================================================
def load_machine_choices() -> List[Tuple[str, str]]:
    cfg = _cfg()
    machine_path = None
    root_data_machine_path = _machines_file_path()

    if callable(get_machines_path):
        try:
            machine_path = get_machines_path(cfg)
        except Exception:
            machine_path = None

    path = _first_existing_path(
        root_data_machine_path,
        machine_path,
        _data_path("maszyny", "maszyny.json"),
    )
    try:
        print(
            "[WM-DBG][DYSP][SRC] machine_candidates="
            f"root_data:{root_data_machine_path} | "
            f"get_machines_path:{machine_path} | "
            f"data:{_data_path('maszyny', 'maszyny.json')}"
        )
        print(f"[WM-DBG][DYSP][SRC] machine_path_selected={path}")
    except Exception:
        pass
    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    rows = []
    if isinstance(data, dict):
        if isinstance(data.get("maszyny"), list):
            rows = data.get("maszyny") or []
        elif isinstance(data.get("items"), list):
            rows = data.get("items") or []
        elif isinstance(data.get("machines"), list):
            rows = data.get("machines") or []
        elif isinstance(data.get("lista"), list):
            rows = data.get("lista") or []
    elif isinstance(data, list):
        rows = data

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        if isinstance(row.get("maszyna"), dict):
            row = row.get("maszyna") or row

        mid = str(
            row.get("id")
            or row.get("nr_ewid")
            or row.get("nr")
            or row.get("numer")
            or row.get("kod")
            or ""
        ).strip()
        name = str(
            row.get("nazwa")
            or row.get("name")
            or row.get("opis")
            or row.get("typ")
            or ""
        ).strip()

        if not mid:
            continue

        label = f"{mid} - {name}" if name else mid
        out.append((mid, label))

    return out


# =========================================================
# MAGAZYN
# =========================================================
def load_magazyn_choices() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    candidates = [
        _warehouse_file_path(),
        os.path.join(_magazyn_dir_path(), "katalog.json"),
        os.path.join(_magazyn_dir_path(), "stany.json"),
    ]
    try:
        print(f"[WM-DBG][DYSP][SRC] magazyn_candidates={candidates}")
    except Exception:
        pass

    for path in [p for p in candidates if p]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        rows = []
        if isinstance(data, dict):
            if isinstance(data.get("items"), list):
                rows = data.get("items") or []
            elif isinstance(data.get("pozycje"), list):
                rows = data.get("pozycje") or []
            elif isinstance(data.get("magazyn"), list):
                rows = data.get("magazyn") or []
            elif isinstance(data.get("produkty"), list):
                rows = data.get("produkty") or []
            elif isinstance(data.get("stany"), list):
                rows = data.get("stany") or []
            elif isinstance(data.get("lista"), list):
                rows = data.get("lista") or []
            elif isinstance(data.get("rows"), list):
                rows = data.get("rows") or []
            elif isinstance(data.get("data"), list):
                rows = data.get("data") or []
            else:
                for key, row in data.items():
                    if isinstance(row, dict):
                        code = str(
                            row.get("id")
                            or row.get("kod")
                            or row.get("nr")
                            or row.get("symbol")
                            or row.get("index")
                            or row.get("numer")
                            or key
                        ).strip()
                        if not code or code.lower() in seen:
                            continue
                        seen.add(code.lower())
                        name = str(
                            row.get("nazwa")
                            or row.get("name")
                            or row.get("opis")
                            or row.get("typ")
                            or row.get("material")
                            or ""
                        ).strip()
                        label = f"{code} - {name}" if name else code
                        out.append((code, label))
                if out:
                    return out
                continue
        elif isinstance(data, list):
            rows = data

        for row in rows:
            if not isinstance(row, dict):
                continue

            if isinstance(row.get("pozycja"), dict):
                row = row.get("pozycja") or row
            elif isinstance(row.get("item"), dict):
                row = row.get("item") or row

            code = str(
                row.get("id")
                or row.get("kod")
                or row.get("nr")
                or row.get("symbol")
                or row.get("index")
                or row.get("numer")
                or ""
            ).strip()
            if not code or code.lower() in seen:
                continue
            seen.add(code.lower())
            name = str(
                row.get("nazwa")
                or row.get("name")
                or row.get("opis")
                or row.get("typ")
                or row.get("material")
                or ""
            ).strip()
            label = f"{code} - {name}" if name else code
            out.append((code, label))

        if out:
            return out

    return out


# =========================================================
# ZLECENIE WYKONANIA
# =========================================================
def load_zlecenie_wykonania_choices() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()

    candidates = [
        ("produkt", _produkty_dir_path()),
        ("polprodukt", _polprodukty_dir_path()),
    ]

    for prefix, folder in candidates:
        try:
            names = sorted(os.listdir(folder))
        except Exception:
            names = []
        for filename in names:
            if not filename.endswith(".json"):
                continue
            code = os.path.splitext(filename)[0].strip()
            if not code:
                continue
            key = f"{prefix}:{code}".lower()
            if key in seen:
                continue
            seen.add(key)
            label = f"{prefix.upper()} - {code}"
            out.append((f"{prefix}:{code}", label))

    # katalog magazynowy jako "elementy / pozycje magazynowe"
    katalog_candidates = [
        os.path.join(_magazyn_dir_path(), "katalog.json"),
    ]
    katalog = {}
    try:
        for katalog_path in katalog_candidates:
            try:
                with open(katalog_path, "r", encoding="utf-8") as f:
                    katalog = json.load(f)
                if katalog:
                    break
            except Exception:
                continue
    except Exception:
        katalog = {}

    if isinstance(katalog, dict):
        for key, row in katalog.items():
            code = str(key or "").strip()
            if not code:
                continue
            uniq = f"element:{code}".lower()
            if uniq in seen:
                continue
            seen.add(uniq)
            name = ""
            if isinstance(row, dict):
                name = str(row.get("nazwa") or "").strip()
            label = f"ELEMENT - {code}" + (f" - {name}" if name else "")
            out.append((f"element:{code}", label))

    return out
