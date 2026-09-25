# version: 1.11
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
    def _guarded_create_planista_order(payload, author):
        """WMM and desktop must create identical BOM/reservation/disposition data."""
        from math import isfinite
        import zlecenia_logika as ZL

        data_root = _impl._data_dir().resolve()
        if ZL._data_dir().resolve() != data_root:
            raise RuntimeError(
                "WM i WMM wskazują różne katalogi danych. Nie utworzono zlecenia."
            )
        product_code = str(payload.get("product_code") or "").strip()
        products = {
            str(item.get("kod") or ""): item
            for item in _impl._planista_products()
        }
        if product_code not in products:
            raise RuntimeError(f"Brak produktu WM: {product_code}")
        try:
            quantity = float(payload.get("quantity"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Ilość musi być liczbą.") from exc
        if not isfinite(quantity) or quantity <= 0:
            raise RuntimeError("Ilość musi być dodatnią, skończoną liczbą.")
        external_no = str(payload.get("external_no") or "").strip()

        def create():
            if external_no:
                for row in ZL.list_zlecenia():
                    if (str(row.get("zlec_wew") or "").strip().casefold() == external_no.casefold()
                        and str(row.get("produkt") or "").strip().casefold() == product_code.casefold()):
                        raise RuntimeError(
                            "Istnieje już zlecenie z tym samym Zleceniem wew i Produktem."
                        )
            order, _shortages = ZL.create_zlecenie(
                product_code, quantity,
                uwagi=str(payload.get("notes") or ""),
                autor=str(author or "system"),
                zlec_wew=external_no or None,
                reserve=True,
                version=products[product_code].get("version"),
                termin=str(payload.get("due_date") or "").strip(),
                auto_dyspozycje=True,
            )
            return order

        # The desktop runtime already holds order_create_lock inside the
        # canonical transaction. Never acquire the same non-reentrant lock twice.
        if getattr(ZL.create_zlecenie, "_wm_full_transaction", False):
            return create()
        # Headless WMM can run without the desktop Planista runtime.
        # Keep the same warehouse/disposition rollback in that case.
        import planista_audit_runtime as PAR

        with order_create_lock(data_root):
            with PAR.warehouse_full_operation():
                warehouse = PAR._canonical_warehouse_snapshot()
                disp_path, disp_snapshot = PAR._disposition_snapshot()
                orders_dir = data_root / "zlecenia"
                before = {path.name for path in orders_dir.glob("*.json")}
                try:
                    return create()
                except Exception:
                    PAR._restore_canonical_warehouse(warehouse)
                    PAR._restore_disposition_snapshot(disp_path, disp_snapshot)
                    for path in orders_dir.glob("*.json"):
                        if path.name not in before:
                            path.unlink()
                    raise

    _impl._create_planista_order = _guarded_create_planista_order
    _impl._WM10_ORDER_CREATE_GUARD = True



if not getattr(_impl, "_WM10_PLANISTA_DISPOSITION_GUARD", False):
    _original_set_disposition_status = _impl._set_disposition_status

    def _guarded_set_disposition_status(item_id, status, author):
        from dyspozycje_store import get_dyspozycja

        row = get_dyspozycja(str(item_id))
        if not row:
            raise RuntimeError("Nie znaleziono Dyspozycji.")
        typ = str(row.get("typ_dyspozycji") or "").strip().lower()
        if typ != "zlecenie_wykonania" or str(status) != "zamknieta":
            return _original_set_disposition_status(item_id, status, author)

        if str(row.get("status") or "") == "zamknieta":
            return row
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        order_id = str(
            meta.get("order_id") or meta.get("nr_zlecenia")
            or meta.get("zlecenie_id") or ""
        ).strip()
        object_id = str(row.get("obiekt_id") or "").strip()
        if object_id.startswith("zlecenie:") and ":" not in object_id[len("zlecenie:"):]:
            order_id = object_id[len("zlecenie:"):]
        if not order_id:
            raise RuntimeError(
                "Dyspozycja produkcyjna bez powiązanego zlecenia wymaga rozliczenia w WM."
            )
        from dyspozycje_access import resolve_role_for_login
        from planista_dispatch_runtime import close_completed_planista_dispatch

        role = resolve_role_for_login(str(author))
        try:
            return close_completed_planista_dispatch(
                order_id, who=str(author), role=role,
            )
        except (PermissionError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    _impl._set_disposition_status = _guarded_set_disposition_status
    _impl._WM10_PLANISTA_DISPOSITION_GUARD = True


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


if not getattr(_impl, "_WMM_PLANISTA_MOBILE_V1", False):
    try:
        from services.wmm_planista_mobile import install as _install_wmm_planista_mobile

        _install_wmm_planista_mobile(_impl)
    except Exception:
        _impl.logger.exception("[WMM API] nie udało się uruchomić mobilnego postępu Planisty")


# Zachowaj dotychczasowy publiczny moduł i wszystkie jego symbole.
sys.modules[__name__] = _impl
