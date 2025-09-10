"""Helpers for recording goods receipts (PZ) in the warehouse GUI."""

from __future__ import annotations

import logika_magazyn as LM
import magazyn_io


def record_pz(item_id: str, qty: float, user: str, comment: str = "") -> None:
    """Register a goods receipt for ``item_id``.

    Parameters
    ----------
    item_id:
        Identifier of the item in the warehouse.
    qty:
        Received quantity (positive).
    user:
        Login of the user performing the operation.
    comment:
        Optional free-form comment.
    """

    data = LM.load_magazyn()
    items = data.get("items") or {}
    if item_id not in items:
        raise KeyError(f"Brak pozycji {item_id} w magazynie")

    qty_f = float(qty)
    items[item_id]["stan"] = float(items[item_id].get("stan", 0)) + qty_f

    magazyn_io.append_history(
        items,
        item_id,
        user=user,
        op="PZ",
        qty=qty_f,
        comment=comment,
    )
    LM.save_magazyn(data)

