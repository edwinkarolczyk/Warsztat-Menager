# version: 1.0
# -*- coding: utf-8 -*-
"""Wspólny store dla modułu Dyspozycje.

Cel:
- jedno źródło danych dla dyspozycji z modułów:
  narzędzia / maszyny / magazyn / zamówienia
- brak GUI w tym etapie
- bez ingerencji w stare moduły; tylko fundament pod dalsze spięcie
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore

try:
    from core import root_paths as wm_root_paths
except Exception:  # pragma: no cover
    wm_root_paths = None  # type: ignore


DISP_FILE_NAME = "dyspozycje.json"
DISP_DIR_NAME = "dyspozycje"
DISP_ALLOWED_TYPES = {
    "narzedzie",
    "maszyna",
    "magazyn",
    "zamowienie",
    "zlecenie_wykonania",
}
DISP_TYPE_ALIASES = {
    "zamowienie": "zlecenie_wykonania",
}
DISP_ALLOWED_STATUSES = {"nowa", "w_toku", "wstrzymana", "zamknieta"}
DISP_ALLOWED_PRIORITIES = {"niski", "normalny", "wysoki", "krytyczny"}


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _runtime_cfg_manager():
    try:
        start_mod = sys.modules.get("start")
        if start_mod is not None:
            mgr = getattr(start_mod, "CONFIG_MANAGER", None)
            if mgr is not None:
                try:
                    print(
                        "[WM-DBG][DYSP][STORE] runtime manager=start.CONFIG_MANAGER "
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
                    "[WM-DBG][DYSP][STORE] runtime manager=ConfigManager() "
                    f"{type(mgr).__name__}"
                )
            except Exception:
                pass
            return mgr
        except Exception:
            pass
    return None


def _data_root() -> Path:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        try:
            path = Path(mgr.path_data())
            try:
                print(f"[WM-DBG][DYSP][STORE] data_root={path}")
            except Exception:
                pass
            return path
        except Exception:
            pass
    return Path("data")


def _anchor_root() -> Path:
    mgr = _runtime_cfg_manager()
    if mgr is not None:
        for method_name in ("path_anchor", "path_root"):
            method = getattr(mgr, method_name, None)
            if not callable(method):
                continue
            try:
                path = Path(method())
                try:
                    print(f"[WM-DBG][DYSP][STORE] anchor_root={path}")
                except Exception:
                    pass
                return path
            except Exception:
                continue
    return Path.cwd()


def _legacy_dyspozycje_path() -> Path:
    return _data_root() / DISP_FILE_NAME


def _legacy_root_dyspozycje_path() -> Path:
    return _anchor_root() / DISP_DIR_NAME / DISP_FILE_NAME


def _active_dyspozycje_path() -> Path:
    if wm_root_paths is not None:
        try:
            return wm_root_paths.path_dyspozycje()
        except Exception:
            pass
    return _data_root() / DISP_DIR_NAME / DISP_FILE_NAME


def _migrate_legacy_if_needed(target: Path) -> None:
    legacy_candidates = [
        _legacy_root_dyspozycje_path(),
        _legacy_dyspozycje_path(),
    ]
    try:
        target_norm = target.resolve()
    except Exception:
        target_norm = target

    for legacy in legacy_candidates:
        try:
            if legacy.resolve() == target_norm:
                continue
        except Exception:
            pass
        if not legacy.exists():
            continue
        if target.exists():
            try:
                print(
                    "[WM-DBG][DYSP][STORE][WARN] legacy dyspozycje exists "
                    f"but active is data dyspozycje: {legacy}"
                )
            except Exception:
                pass
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
            print(
                "[WM-DBG][DYSP][STORE] migrated legacy dyspozycje: "
                f"{legacy} -> {target}"
            )
            return
        except Exception as exc:
            try:
                print(f"[WM-DBG][DYSP][STORE] migration failed: {exc}")
            except Exception:
                pass


def get_dyspozycje_path() -> Path:
    path = _active_dyspozycje_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_if_needed(path)
    try:
        print(f"[WM-DBG][DYSP][STORE] dyspozycje_path={path}")
    except Exception:
        pass
    return path


def _default_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "items": [],
    }


def _normalize_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = DISP_TYPE_ALIASES.get(raw, raw)
    return raw if raw in DISP_ALLOWED_TYPES else "narzedzie"


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in DISP_ALLOWED_STATUSES else "nowa"


def _normalize_priority(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in DISP_ALLOWED_PRIORITIES else "normalny"


def _normalize_login(value: Any) -> str:
    return str(value or "").strip()


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "tak", "yes"}


def make_dyspozycja(
    *,
    typ_dyspozycji: str,
    tytul: str,
    opis: str = "",
    autor: str = "",
    przypisane_do: str = "",
    dla_wszystkich: bool = False,
    termin: str = "",
    priorytet: str = "normalny",
    modul_zrodlowy: str = "",
    obiekt_id: str = "",
    status: str = "nowa",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tworzy nowy rekord dyspozycji w jednym wspólnym modelu danych."""

    record = {
        "id": f"DYSP-{uuid.uuid4().hex[:10].upper()}",
        "typ_dyspozycji": _normalize_type(typ_dyspozycji),
        "tytul": str(tytul or "").strip(),
        "opis": str(opis or "").strip(),
        "status": _normalize_status(status),
        "priorytet": _normalize_priority(priorytet),
        "termin": str(termin or "").strip(),
        "autor": _normalize_login(autor),
        "przypisane_do": _normalize_login(przypisane_do),
        "dla_wszystkich": _normalize_bool(dla_wszystkich),
        "modul_zrodlowy": str(modul_zrodlowy or "").strip().lower(),
        "obiekt_id": str(obiekt_id or "").strip(),
        "utworzono": _now_iso(),
        "wykonano": "",
        "zamknieto_at": "",
        "zamkniete_przez": "",
        "uwagi": "",
        "meta": dict(meta or {}),
    }
    return normalize_dyspozycja(record)


def normalize_dyspozycja(item: dict[str, Any] | None) -> dict[str, Any]:
    src = dict(item or {})
    normalized = {
        "id": str(src.get("id") or f"DYSP-{uuid.uuid4().hex[:10].upper()}").strip(),
        "typ_dyspozycji": _normalize_type(src.get("typ_dyspozycji")),
        "tytul": str(src.get("tytul") or "").strip(),
        "opis": str(src.get("opis") or "").strip(),
        "status": _normalize_status(src.get("status")),
        "priorytet": _normalize_priority(src.get("priorytet")),
        "termin": str(src.get("termin") or "").strip(),
        "autor": _normalize_login(src.get("autor")),
        "przypisane_do": _normalize_login(src.get("przypisane_do")),
        "dla_wszystkich": _normalize_bool(src.get("dla_wszystkich")),
        "modul_zrodlowy": str(src.get("modul_zrodlowy") or "").strip().lower(),
        "obiekt_id": str(src.get("obiekt_id") or "").strip(),
        "utworzono": str(src.get("utworzono") or _now_iso()).strip(),
        "wykonano": str(src.get("wykonano") or "").strip(),
        "zamknieto_at": str(src.get("zamknieto_at") or "").strip(),
        "zamkniete_przez": _normalize_login(src.get("zamkniete_przez")),
        "uwagi": str(src.get("uwagi") or "").strip(),
        "meta": dict(src.get("meta") or {}),
    }
    return normalized


def load_dyspozycje() -> list[dict[str, Any]]:
    path = get_dyspozycje_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        return []

    if isinstance(raw, dict):
        items = raw.get("items") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(normalize_dyspozycja(item))
    return out


def save_dyspozycje(items: list[dict[str, Any]]) -> Path:
    path = get_dyspozycje_path()
    payload = _default_payload()
    payload["items"] = [
        normalize_dyspozycja(item) for item in items if isinstance(item, dict)
    ]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def add_dyspozycja(item: dict[str, Any]) -> dict[str, Any]:
    items = load_dyspozycje()
    record = normalize_dyspozycja(item)
    items.append(record)
    save_dyspozycje(items)
    return deepcopy(record)


def get_dyspozycja(dyspozycja_id: str) -> dict[str, Any] | None:
    needle = str(dyspozycja_id or "").strip()
    if not needle:
        return None
    for item in load_dyspozycje():
        if str(item.get("id") or "").strip() == needle:
            return deepcopy(item)
    return None


def update_dyspozycja(
    dyspozycja_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    needle = str(dyspozycja_id or "").strip()
    if not needle:
        return None

    items = load_dyspozycje()
    changed: dict[str, Any] | None = None
    for idx, item in enumerate(items):
        if str(item.get("id") or "").strip() != needle:
            continue
        merged = dict(item)
        merged.update(dict(updates or {}))
        normalized = normalize_dyspozycja(merged)
        items[idx] = normalized
        changed = normalized
        break

    if changed is None:
        return None
    save_dyspozycje(items)
    return deepcopy(changed)


def close_dyspozycja(
    dyspozycja_id: str,
    *,
    uwagi: str = "",
    closed_by: str = "",
) -> dict[str, Any] | None:
    updates = {
        "status": "zamknieta",
        "wykonano": _now_iso(),
        "zamknieto_at": _now_iso(),
        "zamkniete_przez": _normalize_login(closed_by),
    }
    if str(uwagi or "").strip():
        updates["uwagi"] = str(uwagi).strip()
    return update_dyspozycja(dyspozycja_id, updates)


def delete_dyspozycja(dyspozycja_id: str) -> bool:
    needle = str(dyspozycja_id or "").strip()
    if not needle:
        return False
    items = load_dyspozycje()
    filtered = [item for item in items if str(item.get("id") or "").strip() != needle]
    if len(filtered) == len(items):
        return False
    save_dyspozycje(filtered)
    return True


def visible_for_login(login: str) -> list[dict[str, Any]]:
    login_norm = _normalize_login(login).lower()
    out: list[dict[str, Any]] = []
    for item in load_dyspozycje():
        assigned = _normalize_login(item.get("przypisane_do")).lower()
        if item.get("dla_wszystkich") is True:
            out.append(item)
            continue
        if login_norm and assigned == login_norm:
            out.append(item)
    return out


def assigned_to_login(login: str) -> list[dict[str, Any]]:
    login_norm = _normalize_login(login).lower()
    if not login_norm:
        return []
    out: list[dict[str, Any]] = []
    for item in load_dyspozycje():
        assigned = _normalize_login(item.get("przypisane_do")).lower()
        if assigned == login_norm:
            out.append(item)
    return out


def filter_dyspozycje(
    *,
    typ_dyspozycji: str | None = None,
    modul_zrodlowy: str | None = None,
    obiekt_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    items = load_dyspozycje()
    out: list[dict[str, Any]] = []
    for item in items:
        if typ_dyspozycji and str(item.get("typ_dyspozycji") or "") != str(typ_dyspozycji):
            continue
        if modul_zrodlowy and str(item.get("modul_zrodlowy") or "") != str(modul_zrodlowy):
            continue
        if obiekt_id and str(item.get("obiekt_id") or "") != str(obiekt_id):
            continue
        if status and str(item.get("status") or "") != str(status):
            continue
        out.append(item)
    return out


__all__ = [
    "DISP_ALLOWED_PRIORITIES",
    "DISP_ALLOWED_STATUSES",
    "DISP_ALLOWED_TYPES",
    "add_dyspozycja",
    "assigned_to_login",
    "close_dyspozycja",
    "delete_dyspozycja",
    "filter_dyspozycje",
    "get_dyspozycja",
    "get_dyspozycje_path",
    "load_dyspozycje",
    "make_dyspozycja",
    "normalize_dyspozycja",
    "save_dyspozycje",
    "update_dyspozycja",
    "visible_for_login",
]
