# -*- coding: utf-8 -*-
"""WMM -> Maszyny: pełna lista istniejących przeglądów WM.

Warstwa v5 nie zmienia modelu danych WM. Koryguje tylko odczyt dla telefonu:
łączy bezpośrednie ``machine['reviews']`` z terminami cyklicznymi generowanymi
przez istniejący harmonogram desktopowego WM.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services import wmm_machine_mobile as legacy
from services import wmm_machine_mobile_v4 as v4


def _review_status(value: object) -> str:
    return str(value or "planned").strip().casefold()


def _row_key(row: dict[str, Any]) -> str:
    review_id = str(row.get("id") or "").strip()
    if review_id:
        return f"id:{review_id}"
    planned = str(row.get("planned_date") or row.get("date") or "").strip()
    review_type = str(row.get("type") or "").strip().casefold()
    source = str(row.get("source") or "manual").strip().casefold()
    return f"fallback:{source}:{planned}:{review_type}"


def _normalize_row(row: dict[str, Any], *, default_source: str = "manual") -> dict[str, Any]:
    item = dict(row)
    source = str(item.get("source") or default_source).strip().casefold() or default_source
    item["source"] = source
    item["source_label"] = "Cykliczny" if source == "cycle" else "Ręczny / zaplanowany w WM"
    if not str(item.get("date") or "").strip():
        item["date"] = str(item.get("planned_date") or "").strip()
    if not str(item.get("planned_date") or "").strip():
        item["planned_date"] = str(item.get("date") or "").strip()
    return item


def combined_actionable_reviews(machine: dict[str, Any]) -> list[dict[str, Any]]:
    """Zwróć wszystkie aktywne istniejące plany: ręczne + cykliczne.

    Ręczne wpisy są pobierane bezpośrednio z ``machine['reviews']``. Dzięki temu
    nie znikają nawet wtedy, gdy helper GUI nie zwróci ich w liście łączonej.
    Terminy cykliczne nadal pochodzą z kanonicznego harmonogramu WM.
    """

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any], *, default_source: str = "manual") -> None:
        status = _review_status(row.get("status"))
        if status in v4._DONE or status in v4._CANCELLED:
            return
        item = _normalize_row(row, default_source=default_source)
        key = _row_key(item)
        if key in seen:
            return
        seen.add(key)
        rows.append(item)

    # 1. Wpisy ręczne / zapisane już w danych maszyny WM.
    for review in legacy._machine_reviews(machine):
        add(review, default_source="manual")

    # 2. Wirtualne i zapisane terminy z istniejącego harmonogramu desktopowego WM.
    try:
        import gui_maszyny_legacy as machines_gui

        entries = machines_gui._combined_machine_review_entries(
            machine,
            today=date.today(),
            years_ahead=1,
        )
    except Exception as exc:
        raise RuntimeError(f"Nie udało się odczytać harmonogramu przeglądów WM: {exc}") from exc

    for entry in entries or []:
        if isinstance(entry, dict):
            add(entry, default_source=str(entry.get("source") or "manual"))

    rows.sort(
        key=lambda item: (
            str(item.get("planned_date") or item.get("date") or "9999-99-99"),
            str(item.get("type") or "").casefold(),
        )
    )
    return rows


def install(impl: Any) -> None:
    """Podmień wyłącznie sposób budowania listy dla już zainstalowanej warstwy v4."""

    if getattr(impl, "_WMM_MACHINE_MOBILE_V5", False):
        return

    # v4.planned_reviews oraz v4._find_display_entry odwołują się do tej funkcji
    # dynamicznie, więc nie dokładamy nowych endpointów ani równoległej logiki akcji.
    v4._combined_actionable_reviews = combined_actionable_reviews
    impl._WMM_MACHINE_MOBILE_V5 = True
