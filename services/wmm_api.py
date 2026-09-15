# version: 1.7
"""Bezpieczny punkt wejścia WMM z blokadami zapisu i kontrolą ROOT."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

from machine_file_guard import file_write_lock, machine_file_lock, order_create_lock
from services import wmm_api_impl as _impl

_MACHINE_QR_PREFIX = "WMM:MACHINE:"


def _existing_root(candidate: str | os.PathLike[str]) -> Path | None:
    """Zwróć ROOT tylko wtedy, gdy wskazuje istniejącą strukturę WM."""

    try:
        root = Path(candidate).expanduser().resolve()
    except Exception:
        return None
    data = root if root.name.casefold() == "data" else root / "data"
    if root.is_dir() and data.is_dir():
        return root
    return None


def _strict_wmm_root_dir() -> Path:
    """Ustal ROOT bez awaryjnego zapisu do katalogu uruchomienia programu."""

    raw_root = str(os.environ.get("WM_ROOT", "") or "").strip()
    if raw_root:
        resolved = _existing_root(raw_root)
        if resolved is not None:
            return resolved

    raw_data = str(os.environ.get("WM_DATA_ROOT", "") or "").strip()
    if raw_data:
        resolved = _existing_root(raw_data)
        if resolved is not None:
            return resolved

    try:
        from core import root_paths as wm_root_paths

        pointer = wm_root_paths.root_file_path()
        if pointer.is_file():
            payload = json.loads(pointer.read_text(encoding="utf-8"))
            configured = str(payload.get("root") or "").strip() if isinstance(payload, dict) else ""
            if configured:
                resolved = _existing_root(configured)
                if resolved is not None:
                    return resolved
    except Exception:
        pass

    raise RuntimeError(
        "Brak poprawnego WM_ROOT. Uruchom Warsztat Menager ponownie i wskaż "
        "główny folder danych. WMM nie zapisze danych do katalogu programu."
    )


if not getattr(_impl, "_WM10_STRICT_WMM_ROOT", False):
    _impl._root_dir = _strict_wmm_root_dir
    _impl._WM10_STRICT_WMM_ROOT = True


if not getattr(_impl, "_WM10_MACHINE_FILE_GUARD", False):
    _original_update_machine = _impl._update_machine

    def _guarded_update_machine(machine_id: str, mutator):
        with machine_file_lock(_impl._machines_path()):
            return _original_update_machine(machine_id, mutator)

    _impl._update_machine = _guarded_update_machine
    _impl._WM10_MACHINE_FILE_GUARD = True


if not getattr(_impl, "_WM10_TOOL_FILE_GUARD", False):
    _original_update_tool = _impl._update_tool

    def _guarded_update_tool(tool_id: str, mutator):
        path = _impl._tool_path(tool_id)
        if path is None:
            return _original_update_tool(tool_id, mutator)
        with file_write_lock(path, label="Narzędzi"):
            return _original_update_tool(tool_id, mutator)

    _impl._update_tool = _guarded_update_tool
    _impl._WM10_TOOL_FILE_GUARD = True


if not getattr(_impl, "_WM10_ORDER_CREATE_GUARD", False):
    _original_create_planista_order = _impl._create_planista_order

    def _guarded_create_planista_order(payload, author):
        with order_create_lock(_impl._data_dir()):
            return _original_create_planista_order(payload, author)

    _impl._create_planista_order = _guarded_create_planista_order
    _impl._WM10_ORDER_CREATE_GUARD = True


def _machine_id_from_qr(value: object) -> str:
    raw = str(value or "").strip()
    if raw[: len(_MACHINE_QR_PREFIX)].upper() == _MACHINE_QR_PREFIX:
        return raw[len(_MACHINE_QR_PREFIX) :].strip()
    return raw


if not getattr(_impl, "_WM_MACHINE_QR_RESOLVE_V1", False):
    _original_find_machine = _impl._find_machine

    def _find_machine_with_qr(machine_id: str):
        resolved_id = _machine_id_from_qr(machine_id)
        if not resolved_id:
            return None
        return _original_find_machine(resolved_id)

    _impl._find_machine = _find_machine_with_qr
    _impl._WM_MACHINE_QR_RESOLVE_V1 = True


def _valid_media_component(value: str) -> bool:
    if not value or value in {".", ".."}:
        return False
    return Path(value).name == value


if not getattr(_impl, "_WM10_MEDIA_ROUTE_FIX", False):
    _original_do_get = _impl._WmmHandler.do_GET

    def _guarded_do_get(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/v1/media/"):
            return _original_do_get(self)

        if not self._require_pairing_key():
            return None

        parts = [unquote(part) for part in path.split("/") if part]
        if len(parts) != 6 or parts[:3] != ["api", "v1", "media"]:
            self._send(404, {"ok": False, "error": "Nie znaleziono zdjęcia."})
            return None

        kind, object_id, filename = parts[3], parts[4], parts[5]
        if (
            kind not in {"machines", "tools"}
            or not _valid_media_component(object_id)
            or not _valid_media_component(filename)
        ):
            self._send(404, {"ok": False, "error": "Nie znaleziono zdjęcia."})
            return None

        self._send_file(_impl._media_root(kind, object_id) / filename)
        return None

    _impl._WmmHandler.do_GET = _guarded_do_get
    _impl._WM10_MEDIA_ROUTE_FIX = True


if not getattr(_impl, "_WMM_WAREHOUSE_RECEIVE_V1", False):
    try:
        from services.wmm_warehouse_mobile import install as _install_wmm_warehouse_mobile

        _install_wmm_warehouse_mobile(_impl)
    except Exception:
        _impl.logger.exception("[WMM API] nie udało się uruchomić przyjęć Magazynu WMM")


if not getattr(_impl, "_WMM_MACHINE_MOBILE_V1", False):
    try:
        from services.wmm_machine_mobile import install as _install_wmm_machine_mobile

        _install_wmm_machine_mobile(_impl)
    except Exception:
        _impl.logger.exception("[WMM API] nie udało się uruchomić szybkich akcji Maszyn WMM")


if not getattr(_impl, "_WMM_MACHINE_MOBILE_V4", False):
    try:
        from services.wmm_machine_mobile_v4 import install as _install_wmm_machine_mobile_v4

        _install_wmm_machine_mobile_v4(_impl)
    except Exception:
        _impl.logger.exception("[WMM API] nie udało się uruchomić akcji zaplanowanych przeglądów WMM")


if not getattr(_impl, "_WMM_MACHINE_MOBILE_V5", False):
    try:
        from services.wmm_machine_mobile_v5 import install as _install_wmm_machine_mobile_v5

        _install_wmm_machine_mobile_v5(_impl)
    except Exception:
        _impl.logger.exception("[WMM API] nie udało się uruchomić pełnej listy przeglądów WMM")


# Zachowaj dotychczasowy publiczny moduł i wszystkie jego symbole.
sys.modules[__name__] = _impl
