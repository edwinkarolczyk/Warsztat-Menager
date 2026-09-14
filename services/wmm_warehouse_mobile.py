# -*- coding: utf-8 -*-
"""Bezpieczne przyjęcia magazynowe z WMM bez edycji kartoteki surowca."""

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import secrets
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from machine_file_guard import warehouse_transaction_lock


WarehouseLoader = Callable[[], list[dict[str, Any]]]


def _item_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("kod") or row.get("symbol") or "").strip()


def _read_optional_json(impl: Any, path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return impl._read_json(path)
    except RuntimeError:
        return default


def _list_payload(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("items", "rows", "data"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _receipt_rows(impl: Any) -> list[dict[str, Any]]:
    path = impl._data_dir() / "magazyn" / "przyjecia.json"
    return _list_payload(_read_optional_json(impl, path, []))


def _with_receipts(
    impl: Any,
    base_loader: WarehouseLoader,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in base_loader()]
    receipts = _receipt_rows(impl)
    by_item: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        key = str(receipt.get("item_id") or receipt.get("kod") or "").strip().casefold()
        if not key:
            continue
        by_item.setdefault(key, []).append(dict(receipt))

    for row in rows:
        key = _item_id(row)
        row["id"] = key
        history = by_item.get(key.casefold(), [])
        history.sort(
            key=lambda record: str(record.get("ts") or record.get("timestamp") or record.get("data") or ""),
            reverse=True,
        )
        row["receipts"] = history[:50]
    return rows


def _find_existing(rows: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    needle = str(item_id or "").strip().casefold()
    if not needle:
        return None
    for row in rows:
        values = (row.get("id"), row.get("kod"), row.get("symbol"))
        if any(str(value or "").strip().casefold() == needle for value in values):
            return dict(row)
    return None


def _positive_qty(value: Any) -> float:
    try:
        qty = float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Ilość przyjęcia musi być liczbą.") from exc
    if not math.isfinite(qty) or qty <= 0:
        raise RuntimeError("Ilość przyjęcia musi być większa od zera.")
    if qty > 1_000_000_000:
        raise RuntimeError("Ilość przyjęcia jest zbyt duża.")
    return qty


def _current_stock(state: Any) -> float:
    if isinstance(state, dict):
        value = state.get("stan", state.get("ilosc", 0.0))
    else:
        value = state
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _append_record(impl: Any, path: Path, record: dict[str, Any]) -> None:
    raw = _read_optional_json(impl, path, [])
    if isinstance(raw, list):
        rows = list(raw)
        rows.append(record)
        impl._write_json_atomic(path, rows)
        return
    if isinstance(raw, dict):
        value = dict(raw)
        rows = value.get("items")
        if not isinstance(rows, list):
            rows = []
        rows = list(rows)
        rows.append(record)
        value["items"] = rows
        impl._write_json_atomic(path, value)
        return
    impl._write_json_atomic(path, [record])


def receive_existing_material(
    impl: Any,
    base_loader: WarehouseLoader,
    item_id: str,
    payload: dict[str, Any],
    author: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Zwiększ wyłącznie stan istniejącego surowca i dopisz historię PZ."""

    qty = _positive_qty(payload.get("qty", payload.get("ilosc")))
    document = str(payload.get("document") or payload.get("dokument") or "").strip()[:120]
    supplier = str(payload.get("supplier") or payload.get("dostawca") or "").strip()[:160]
    note = str(payload.get("note") or payload.get("uwaga") or "").strip()[:500]
    warehouse_dir = impl._data_dir() / "magazyn"
    states_path = warehouse_dir / "stany.json"
    receipts_path = warehouse_dir / "przyjecia.json"
    history_path = warehouse_dir / "magazyn_history.json"

    with warehouse_transaction_lock(states_path):
        # Sprawdzamy ponownie pod blokadą. WMM nie może utworzyć nowej kartoteki.
        master = _find_existing(base_loader(), item_id)
        if master is None:
            raise RuntimeError(
                "Nie znaleziono surowca w Magazynie. Dodaj lub popraw kartotekę w desktopowym WM."
            )

        states = _read_optional_json(impl, states_path, {})
        if not isinstance(states, dict):
            raise RuntimeError("Nieprawidłowy plik stanów Magazynu.")

        key = _item_id(master)
        state_raw = states.get(key, {})
        before = _current_stock(state_raw)
        after = before + qty
        if isinstance(state_raw, dict):
            state = dict(state_raw)
        else:
            state = {}
        state["stan"] = after
        if "ilosc" in state:
            state["ilosc"] = after
        state.setdefault("nazwa", str(master.get("nazwa") or master.get("name") or key).strip())
        states[key] = state

        now = datetime.now()
        user = str(author or "WMM").strip() or "WMM"
        receipt = {
            "id": f"PZ-WMM-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2).upper()}",
            "typ": "PZ",
            "op": "PZ",
            "ts": now.isoformat(timespec="seconds"),
            "data": now.strftime("%Y-%m-%d"),
            "item_id": key,
            "qty": qty,
            "jednostka": str(master.get("jednostka") or "").strip(),
            "user": user,
            "source": "WMM",
            "document": document,
            "supplier": supplier,
            "comment": note,
            "stan_przed": before,
            "stan_po": after,
        }

        # Wszystkie zapisy są w tej samej blokadzie Magazynu; kartoteka surowca
        # nie jest zapisywana ani modyfikowana.
        _append_record(impl, receipts_path, receipt)
        _append_record(impl, history_path, receipt)
        impl._write_json_atomic(states_path, states)

    updated = _find_existing(_with_receipts(impl, base_loader), item_id)
    if updated is None:
        raise RuntimeError("Przyjęcie zapisano, ale nie udało się odświeżyć pozycji Magazynu.")
    return updated, receipt


def install(impl: Any) -> None:
    """Dołącz odczyt historii i POST /warehouse/<id>/receive do WMM API."""

    if getattr(impl, "_WMM_WAREHOUSE_RECEIVE_V1", False):
        return

    base_loader = impl._warehouse

    def warehouse_loader() -> list[dict[str, Any]]:
        return _with_receipts(impl, base_loader)

    impl._warehouse = warehouse_loader

    original_do_post = impl._WmmHandler.do_POST

    def warehouse_do_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        match = impl.re.fullmatch(r"/api/v1/warehouse/([^/]+)/receive", path)
        if not match:
            return original_do_post(self)

        payload = self._read_json()
        if not self._require_pairing_key():
            return None
        try:
            item, receipt = receive_existing_material(
                impl,
                base_loader,
                unquote(match.group(1)),
                payload,
                self._author(),
            )
            self._send(201, {"ok": True, "item": item, "receipt": receipt})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - awaryjny bezpiecznik API
            impl.logger.exception("[WMM API] przyjęcie magazynowe nieudane")
            self._send(500, {"ok": False, "error": f"Błąd przyjęcia materiału: {exc}"})
        return None

    impl._WmmHandler.do_POST = warehouse_do_post
    impl._WMM_WAREHOUSE_RECEIVE_V1 = True
