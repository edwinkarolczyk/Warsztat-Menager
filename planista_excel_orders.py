# WM-VERSION: 0.2
# Plik: planista_excel_orders.py
# version: 1.1
# 1.1: blokuje powielony klucz Nr zlec. + Produkt WM w jednym planie Excel.
"""Planowanie i kontrolowane wykonanie synchronizacji Excel -> zlecenia WM.

Moduł nie jest podpięty bezpośrednio do przycisku importu. Najpierw buduje
plan zmian, a zapis wymaga jawnej listy zatwierdzonych tożsamości. Dzięki temu
zadanie 12 może pokazać użytkownikowi podgląd przed modyfikacją zleceń.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from config_manager import ConfigManager
from planista_excel_changes import CHANGE_REMOVED
from planista_excel_match import STATUS_FOUND
import zlecenia_logika as ZL


ACTION_CREATE = "Utwórz"
ACTION_UPDATE = "Aktualizuj"
ACTION_NONE = "Bez zmian"
ACTION_SKIP = "Nie importuj"
ACTION_PROTECTED = "Chronione"
ACTION_CONFLICT = "Wymaga decyzji"
ACTION_REMOVED = "Usunięta w Excelu"

PROVENANCE_FIELD = "planista_excel"
PROVENANCE_SCHEMA = 1
PROTECTED_STATUSES = {
    "w przygotowaniu",
    "w trakcie",
    "wstrzymane",
    "zakończone",
    "anulowane",
}


class ExcelOrderSyncError(ValueError):
    """Błąd walidacji lub kontrolowanego zapisu synchronizacji."""


def _text(value) -> str:
    return str(value or "").strip()


def _norm(value) -> str:
    return " ".join(_text(value).casefold().split())


def _qty(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _identity(nr_zlec, wm_symbol) -> str:
    return f"{_norm(nr_zlec)}|{_norm(wm_symbol)}"


def _provenance(order: dict) -> dict:
    raw = order.get(PROVENANCE_FIELD)
    return raw if isinstance(raw, dict) else {}


def _order_business_identity(order: dict) -> str:
    prov = _provenance(order)
    nr_zlec = prov.get("nr_zlec") if prov else order.get("zlec_wew")
    wm_symbol = prov.get("wm_symbol") if prov else order.get("produkt")
    if not _text(nr_zlec) or not _text(wm_symbol):
        return ""
    return _identity(nr_zlec, wm_symbol)


def _source_meta(payload: dict, row: dict) -> dict:
    return {
        "schema": PROVENANCE_SCHEMA,
        "typ": "plan_excel",
        "nr_zlec": _text(row.get("nr_zlec")),
        "wm_symbol": _text(row.get("wm_symbol")),
        "excel_oznaczenie": _text(row.get("excel_oznaczenie")),
        "proces": _text(row.get("proces")),
        "source_name": _text(payload.get("source_name")),
        "source_path": _text(payload.get("source_path")),
        "sheet": _text(payload.get("sheet")),
        "source_sha256": _text(payload.get("source_sha256")),
        "identity": _identity(row.get("nr_zlec"), row.get("wm_symbol")),
        "last_sync_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _plan_item(
    row: dict,
    action: str,
    *,
    reason: str,
    order: dict | None = None,
    changes: list[str] | None = None,
) -> dict:
    return {
        "identity": _identity(row.get("nr_zlec"), row.get("wm_symbol")),
        "action": action,
        "reason": reason,
        "order_id": _text((order or {}).get("id")),
        "nr_zlec": _text(row.get("nr_zlec")),
        "wm_symbol": _text(row.get("wm_symbol")),
        "wm_name": _text(row.get("wm_nazwa")),
        "ilosc": _qty(row.get("ilosc")),
        "termin": _text(row.get("data_wysylki")),
        "proces": _text(row.get("proces")),
        "source_row": row.get("source_row", ""),
        "changes": list(changes or []),
        "row": dict(row),
    }


def _current_excel_key_counts(payload: dict) -> dict[str, int]:
    """Policz jednoznaczne klucze w bieżącym Excelu bez ich agregowania."""
    counts: dict[str, int] = defaultdict(int)
    for raw in list(payload.get("rows") or []):
        if not isinstance(raw, dict):
            continue
        if _text(raw.get("match_status")) != STATUS_FOUND:
            continue
        nr_zlec = _text(raw.get("nr_zlec"))
        wm_symbol = _text(raw.get("wm_symbol"))
        if nr_zlec and wm_symbol:
            counts[_identity(nr_zlec, wm_symbol)] += 1
    return dict(counts)


def build_order_sync_plan(payload: dict, orders: list[dict] | None = None) -> dict:
    """Zbuduj plan synchronizacji bez zapisywania zleceń WM."""
    current_orders = list(ZL.list_zlecenia() if orders is None else orders)
    imported_by_key: dict[str, list[dict]] = defaultdict(list)
    business_by_key: dict[str, list[dict]] = defaultdict(list)
    imported_by_external: dict[str, list[dict]] = defaultdict(list)
    current_key_counts = _current_excel_key_counts(payload)

    for order in current_orders:
        if not isinstance(order, dict):
            continue
        key = _order_business_identity(order)
        if key:
            business_by_key[key].append(order)
        prov = _provenance(order)
        if prov:
            pkey = _identity(prov.get("nr_zlec"), prov.get("wm_symbol"))
            if pkey != "|":
                imported_by_key[pkey].append(order)
            if _text(prov.get("nr_zlec")):
                imported_by_external[_norm(prov.get("nr_zlec"))].append(order)

    planned: list[dict] = []
    for raw in list(payload.get("rows") or []):
        row = dict(raw) if isinstance(raw, dict) else {}
        if _text(row.get("match_status")) != STATUS_FOUND:
            planned.append(
                _plan_item(
                    row,
                    ACTION_SKIP,
                    reason="Pozycja nie ma jednoznacznie dopasowanego Produktu WM.",
                )
            )
            continue

        nr_zlec = _text(row.get("nr_zlec"))
        wm_symbol = _text(row.get("wm_symbol"))
        qty = _qty(row.get("ilosc"))
        if not nr_zlec or not wm_symbol:
            planned.append(
                _plan_item(
                    row,
                    ACTION_SKIP,
                    reason="Brak zewnętrznego Nr zlec. lub ID Produktu WM.",
                )
            )
            continue
        if qty is None or qty <= 0:
            planned.append(
                _plan_item(
                    row,
                    ACTION_SKIP,
                    reason="Ilość z Excela musi być większa od zera.",
                )
            )
            continue

        key = _identity(nr_zlec, wm_symbol)
        if current_key_counts.get(key, 0) > 1:
            planned.append(
                _plan_item(
                    row,
                    ACTION_CONFLICT,
                    reason=(
                        "Excel zawiera więcej niż jedną pozycję z tym samym "
                        "Nr zlec. i Produktem WM; WM nie sumuje ich ani nie "
                        "tworzy automatycznie."
                    ),
                )
            )
            continue

        imported_matches = imported_by_key.get(key, [])
        if len(imported_matches) > 1:
            planned.append(
                _plan_item(
                    row,
                    ACTION_CONFLICT,
                    reason="Więcej niż jedno zlecenie importowane ma ten sam klucz Nr zlec. + Produkt WM.",
                )
            )
            continue

        if not imported_matches:
            excel_fields = {str(x) for x in list(row.get("excel_change_fields") or [])}
            external_imports = imported_by_external.get(_norm(nr_zlec), [])
            if "Produkt" in excel_fields and external_imports:
                planned.append(
                    _plan_item(
                        row,
                        ACTION_CONFLICT,
                        reason="Excel zmienił Produkt dla istniejącego zewnętrznego Nr zlec.; wymagana jest decyzja użytkownika.",
                        order=external_imports[0] if len(external_imports) == 1 else None,
                        changes=["Produkt"],
                    )
                )
                continue

            manual_matches = [
                order
                for order in business_by_key.get(key, [])
                if not _provenance(order)
            ]
            if manual_matches:
                planned.append(
                    _plan_item(
                        row,
                        ACTION_CONFLICT,
                        reason="Istnieje ręczne zlecenie z tym samym Nr zlec. i Produktem; WM nie połączy go automatycznie.",
                        order=manual_matches[0] if len(manual_matches) == 1 else None,
                    )
                )
                continue

            planned.append(
                _plan_item(
                    row,
                    ACTION_CREATE,
                    reason="Brak istniejącego zlecenia o tym stabilnym kluczu.",
                )
            )
            continue

        order = imported_matches[0]
        changes: list[str] = []
        if _qty(order.get("ilosc")) != qty:
            changes.append("Ilość")
        if _text(order.get("termin")) != _text(row.get("data_wysylki")):
            changes.append("Data wysyłki")
        if _text(_provenance(order).get("proces")) != _text(row.get("proces")):
            changes.append("Proces")

        if not changes:
            planned.append(
                _plan_item(
                    row,
                    ACTION_NONE,
                    reason="Zlecenie WM ma już tę samą ilość, termin i proces.",
                    order=order,
                )
            )
            continue

        status = _norm(order.get("status"))
        if status in PROTECTED_STATUSES:
            planned.append(
                _plan_item(
                    row,
                    ACTION_PROTECTED,
                    reason=f"Zlecenie ma status „{_text(order.get('status'))}” i nie może być automatycznie nadpisane.",
                    order=order,
                    changes=changes,
                )
            )
            continue

        planned.append(
            _plan_item(
                row,
                ACTION_UPDATE,
                reason="Istniejące zlecenie importowane wymaga aktualizacji.",
                order=order,
                changes=changes,
            )
        )

    for raw in list(payload.get("removed_rows") or []):
        row = dict(raw) if isinstance(raw, dict) else {}
        key = _identity(row.get("nr_zlec"), row.get("wm_symbol"))
        matches = imported_by_key.get(key, [])
        order = matches[0] if len(matches) == 1 else None
        reason = "Pozycja zniknęła z Excela; WM nie usuwa zlecenia automatycznie."
        if len(matches) > 1:
            reason = "Pozycja zniknęła z Excela, ale kilka zleceń ma ten sam klucz; wymagana jest decyzja użytkownika."
        planned.append(
            _plan_item(
                row,
                ACTION_REMOVED,
                reason=reason,
                order=order,
                changes=[CHANGE_REMOVED],
            )
        )

    summary: dict[str, int] = defaultdict(int)
    for item in planned:
        summary[item["action"]] += 1
    return {
        "items": planned,
        "summary": dict(summary),
        "can_write": any(item["action"] in {ACTION_CREATE, ACTION_UPDATE} for item in planned),
    }


def _orders_dir() -> Path:
    return Path(ConfigManager().path_data()) / "zlecenia"


def _write_order_provenance(order_id: str, meta: dict, *, autor: str) -> dict:
    path = _orders_dir() / f"{order_id}.json"
    if not path.is_file():
        raise ExcelOrderSyncError(f"Nie znaleziono zlecenia WM {order_id} po zapisie.")
    try:
        order = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExcelOrderSyncError(f"Nie można odczytać zlecenia WM {order_id}: {exc}") from exc
    if not isinstance(order, dict):
        raise ExcelOrderSyncError(f"Zlecenie WM {order_id} ma nieprawidłowy format.")

    order[PROVENANCE_FIELD] = dict(meta)
    order.setdefault("historia", []).append(
        {
            "kiedy": datetime.now().isoformat(timespec="seconds"),
            "kto": autor,
            "co": f"synchronizacja Excel: {meta.get('nr_zlec', '')} / {meta.get('wm_symbol', '')}",
        }
    )
    temp = path.with_name(path.name + ".excel-sync.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise ExcelOrderSyncError(f"Nie można zapisać pochodzenia Excel dla zlecenia {order_id}: {exc}") from exc
    return order


def apply_order_sync(
    payload: dict,
    plan: dict,
    *,
    approved_identities: set[str] | list[str] | tuple[str, ...],
    autor: str = "Planista Excel",
) -> dict:
    """Zapisz wyłącznie jawnie zatwierdzone pozycje Utwórz/Aktualizuj."""
    approved = {_text(value) for value in approved_identities if _text(value)}
    if not approved:
        raise ExcelOrderSyncError("Brak jawnie zatwierdzonych pozycji do synchronizacji.")

    results: list[dict] = []
    for item in list(plan.get("items") or []):
        if not isinstance(item, dict) or item.get("identity") not in approved:
            continue
        action = item.get("action")
        if action not in {ACTION_CREATE, ACTION_UPDATE}:
            results.append(
                {
                    "identity": item.get("identity", ""),
                    "action": action,
                    "status": "pominięto",
                    "reason": "Ta pozycja nie jest bezpieczną operacją zapisu automatycznego.",
                }
            )
            continue

        row = dict(item.get("row") or {})
        source_meta = _source_meta(payload, row)
        if action == ACTION_CREATE:
            current_key = item.get("identity", "")
            if any(
                _order_business_identity(order) == current_key
                for order in ZL.list_zlecenia()
                if isinstance(order, dict)
            ):
                raise ExcelOrderSyncError(
                    "W międzyczasie pojawiło się zlecenie o tym samym Nr zlec. "
                    f"i Produkcie WM: {current_key}. Odśwież podgląd synchronizacji."
                )
            order, shortages = ZL.create_zlecenie(
                item["wm_symbol"],
                item["ilosc"],
                autor=autor,
                zlec_wew=item["nr_zlec"],
                termin=item["termin"],
            )
            order_id = _text(order.get("id"))
            _write_order_provenance(order_id, source_meta, autor=autor)
            results.append(
                {
                    "identity": item["identity"],
                    "action": ACTION_CREATE,
                    "status": "ok",
                    "order_id": order_id,
                    "shortages": list(shortages or []),
                }
            )
            continue

        order_id = _text(item.get("order_id"))
        if not order_id:
            raise ExcelOrderSyncError(f"Brak ID istniejącego zlecenia dla {item.get('identity', '')}.")
        current = next(
            (order for order in ZL.list_zlecenia() if _text(order.get("id")) == order_id),
            None,
        )
        if not isinstance(current, dict):
            raise ExcelOrderSyncError(f"Nie znaleziono istniejącego zlecenia WM {order_id}.")
        if _norm(current.get("status")) in PROTECTED_STATUSES:
            raise ExcelOrderSyncError(
                f"Zlecenie WM {order_id} zmieniło status i jest teraz chronione przed automatyczną aktualizacją."
            )

        kwargs = {"kto": autor}
        if "Ilość" in list(item.get("changes") or []):
            kwargs["ilosc"] = item["ilosc"]
        if "Data wysyłki" in list(item.get("changes") or []):
            kwargs["termin"] = item["termin"]
        ZL.update_zlecenie(order_id, **kwargs)
        _write_order_provenance(order_id, source_meta, autor=autor)
        results.append(
            {
                "identity": item["identity"],
                "action": ACTION_UPDATE,
                "status": "ok",
                "order_id": order_id,
                "changes": list(item.get("changes") or []),
            }
        )

    return {
        "results": results,
        "written": sum(1 for item in results if item.get("status") == "ok"),
    }
