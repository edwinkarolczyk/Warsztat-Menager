# -*- coding: utf-8 -*-
"""Mobilne szczegóły Planisty i bezpieczne odhaczanie operacji w WMM."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import unquote, urlparse

from machine_file_guard import file_write_lock


_EPS = 1e-9


def _f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _order_path(order_id: str):
    import zlecenia_logika as ZL

    return ZL._order_path(str(order_id))


def _read_order(order_id: str) -> dict[str, Any]:
    import zlecenia_logika as ZL

    path = _order_path(order_id)
    if not path.is_file():
        raise RuntimeError("Nie znaleziono zlecenia.")
    row = ZL._read_json(path)
    if not isinstance(row, dict):
        raise RuntimeError("Nieprawidłowe dane zlecenia.")
    row.setdefault("id", str(order_id))
    return row


def _mobile_order(impl: Any, order: dict[str, Any]) -> dict[str, Any]:
    """Rozszerz zlecenie o czytelny postęp półproduktów i operacji."""
    import planista_semi_progress_runtime as PS

    result = dict(order)
    targets = PS._full_semi_targets(order)
    semi_rows = {str(row.get("kod") or ""): row for row in PS.semi_progress_rows(order)}
    tracking = order.get("postep_operacji_polproduktow")
    tracking = tracking if isinstance(tracking, dict) else {}
    made_map = order.get("wykonano_polprodukty")
    made_map = made_map if isinstance(made_map, dict) else {}

    mobile_semis: list[dict[str, Any]] = []
    ordered_codes = list(targets)
    for code in semi_rows:
        if code not in targets:
            ordered_codes.append(code)

    for code in ordered_codes:
        if not code:
            continue
        target = targets.get(code) if isinstance(targets.get(code), dict) else {}
        progress = semi_rows.get(code, {})
        to_make = max(0.0, _f(progress.get("do_wykonania")))
        semi_made = max(0.0, _f(made_map.get(code)))
        op_state = tracking.get(code)
        op_state = op_state if isinstance(op_state, dict) else {}
        operation_names = [str(item).strip() for item in target.get("czynnosci") or [] if str(item).strip()]

        operations: list[dict[str, Any]] = []
        previous_complete = True
        for operation in operation_names:
            done = max(semi_made, max(0.0, _f(op_state.get(operation))))
            complete = to_make <= _EPS or done + _EPS >= to_make
            available = to_make > _EPS and previous_complete and not complete
            operations.append(
                {
                    "nazwa": operation,
                    "wykonano": done,
                    "do_wykonania": to_make,
                    "wykonana": complete,
                    "dostepna": available,
                }
            )
            previous_complete = complete

        mobile_semis.append(
            {
                "kod": code,
                "nazwa": str(progress.get("nazwa") or target.get("nazwa") or code),
                "potrzeba": _f(progress.get("potrzeba")),
                "z_magazynu": _f(progress.get("z_magazynu")),
                "do_wykonania": to_make,
                "wykonano": _f(progress.get("wykonano")),
                "pozostalo": _f(progress.get("pozostalo")),
                "operacje": operations,
            }
        )

    result["wmm_polprodukty"] = mobile_semis
    return impl._wmm_revision_item(result)


def _find_mobile_order(impl: Any, order_id: str) -> dict[str, Any]:
    return _mobile_order(impl, _read_order(order_id))


def install(impl: Any) -> None:
    """Dołącz GET szczegółu zlecenia i POST ukończenia operacji."""
    if getattr(impl, "_WMM_PLANISTA_MOBILE_V1", False):
        return

    impl._planista_mobile_order = lambda order: _mobile_order(impl, order)
    impl._planista_mobile_find_order = lambda order_id: _find_mobile_order(impl, order_id)

    base_reconcile = impl._wmm_reconcile_result

    def reconcile(path: str, request_id: str):
        match = re.fullmatch(
            r"/api/v1/planista/orders/([^/]+)/semiproducts/([^/]+)/operations/([^/]+)",
            path,
        )
        if match:
            try:
                order = _read_order(unquote(match.group(1)))
            except RuntimeError:
                return None
            return (
                _mobile_order(impl, order)
                if impl._wmm_applied(order, request_id, path)
                else None
            )
        return base_reconcile(path, request_id)

    impl._wmm_reconcile_result = reconcile

    original_get = impl._WmmHandler.do_GET

    def planista_get(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/v1/planista/orders/([^/]+)", path)
        if not match:
            return original_get(self)
        if not self._require_pairing_key():
            return None
        try:
            self._send(
                200,
                {
                    "ok": True,
                    "item": _find_mobile_order(impl, unquote(match.group(1))),
                },
            )
        except RuntimeError as exc:
            self._send(404, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] szczegóły zlecenia nieudane")
            self._send(500, {"ok": False, "error": f"Błąd szczegółów zlecenia: {exc}"})
        return None

    impl._WmmHandler.do_GET = planista_get

    original_post = impl._WmmHandler.do_POST

    def planista_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        match = re.fullmatch(
            r"/api/v1/planista/orders/([^/]+)/semiproducts/([^/]+)/operations/([^/]+)",
            path,
        )
        if not match:
            return original_post(self)

        payload = self._read_json()
        if not self._require_pairing_key():
            return None
        if payload.get("completed") is not True:
            self._send(
                400,
                {
                    "ok": False,
                    "error": "Operację można z telefonu tylko oznaczyć jako wykonaną.",
                },
            )
            return None

        order_id = unquote(match.group(1))
        semi_code = unquote(match.group(2))
        operation = unquote(match.group(3))
        author = self._author()
        request_id = self._request_id()
        fingerprint = hashlib.sha256(
            json.dumps(
                {"author": author, "payload": payload},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        try:
            def perform():
                import planista_semi_progress_runtime as PS

                order_path = _order_path(order_id)
                with file_write_lock(order_path, label="operacji Planisty z WMM"):
                    current = _read_order(order_id)
                    impl._wmm_expect_revision(
                        current,
                        str(payload.get("base_revision") or ""),
                    )
                    marker = f"{path}|{request_id}" if request_id else ""
                    updated = PS._complete_polprodukt_operation_unlocked(
                        order_id,
                        semi_code,
                        operation,
                        kto=author,
                        request_marker=marker,
                    )
                    return _mobile_order(impl, updated)

            replayed, item = impl._run_idempotent(
                request_id,
                path,
                perform,
                fingerprint,
            )
            self._send(200, {"ok": True, "item": item, "replayed": replayed})
        except impl.WmmRevisionConflict as exc:
            self._send(
                409,
                {"ok": False, "code": "WMM_REVISION_CONFLICT", "error": str(exc)},
            )
        except impl.WmmIdempotencyPending as exc:
            self._send(409, {"ok": False, "code": "WMM_PENDING", "error": str(exc)})
        except impl.WmmIdempotencyConflict as exc:
            self._send(
                409,
                {"ok": False, "code": "WMM_IDEMPOTENCY_CONFLICT", "error": str(exc)},
            )
        except (RuntimeError, ValueError, KeyError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] odhaczenie operacji nieudane")
            self._send(500, {"ok": False, "error": f"Błąd zapisu operacji: {exc}"})
        return None

    impl._WmmHandler.do_POST = planista_post
    impl._WMM_PLANISTA_MOBILE_V1 = True
