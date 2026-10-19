# -*- coding: utf-8 -*-
"""Zamykanie dyspozycji braków surowca po przyjęciu towaru do Magazynu."""

from __future__ import annotations

import math


def _quantity(value) -> float:
    try:
        result = float(str(value or 0).replace(",", "."))
        return result if math.isfinite(result) and result >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def close_fulfilled_material_dispositions(item_id: str) -> list[str]:
    """Zamknij tylko dyspozycje braków ze Zleceń, gdy materiał wystarcza.

    Rezerwacje przypisane konkretnemu zleceniu zaliczamy na jego poczet.
    Niezarezerwowany zapas musi pokryć SUMĘ pozostałych potrzeb wszystkich
    otwartych dyspozycji tego surowca; nie przypisujemy tych samych metrów
    równolegle do dwóch zleceń. Ręcznych i wstrzymanych dyspozycji nie ruszamy.
    """
    from dyspozycje_store import load_dyspozycje, set_dyspozycja_status
    import logika_magazyn as LM
    import zlecenia_logika as ZL

    code = str(item_id or "").strip()
    if not code:
        return []
    item = LM.get_item(code)
    if not isinstance(item, dict):
        return []

    stock = _quantity(item.get("stan"))
    reservations = _quantity(item.get("rezerwacje"))
    free = max(0.0, stock - reservations)
    pending = []
    for disposition in load_dyspozycje():
        if not isinstance(disposition, dict):
            continue
        if disposition.get("typ_dyspozycji") != "magazyn":
            continue
        if disposition.get("modul_zrodlowy") != "zlecenia":
            continue
        if disposition.get("status") not in {"nowa", "w_toku"}:
            continue
        meta = disposition.get("meta")
        if not isinstance(meta, dict) or str(meta.get("surowiec") or "") != code:
            continue
        order_id = str(meta.get("zlecenie_id") or "").strip()
        if not order_id or str(disposition.get("obiekt_id") or "") != f"zlecenie:{order_id}:surowiec:{code}":
            continue
        try:
            order = ZL._read_json(ZL._order_path(order_id))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        requirements = (order.get("zapotrzebowanie_surowce") or {}).get(code) or {}
        if not isinstance(requirements, dict):
            continue
        required = _quantity(requirements.get("ilosc"))
        if required <= 0:
            continue
        own_reserved = min(required, _quantity((order.get("rezerwacje_surowce") or {}).get(code)))
        pending.append((disposition, max(0.0, required - own_reserved), own_reserved))

    if not pending:
        return []
    # Uszkodzone/stare rezerwacje nie mogą deklarować większej ilości
    # niż fizycznie istnieje i faktycznie jest zarezerwowana.
    if sum(own for _row, _missing, own in pending) > min(stock, reservations) + 1e-9:
        return []
    if sum(missing for _row, missing, _own in pending) > free + 1e-9:
        return []

    closed = []
    for disposition, _missing, _own in pending:
        dysp_id = str(disposition.get("id") or "").strip()
        if not dysp_id:
            continue
        if disposition.get("status") == "nowa":
            started = set_dyspozycja_status(
                dysp_id, "w_toku", changed_by="system:magazyn"
            )
            if not started:
                continue
        finished = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by="system:magazyn",
            uwagi="Zamknięto automatycznie: uzupełniono wymagany stan surowca w Magazynie.",
        )
        if finished:
            closed.append(dysp_id)
    return closed
