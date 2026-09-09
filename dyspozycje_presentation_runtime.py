# version: 1.0
"""Kosmetyczna prezentacja Dyspozycji bez zmiany modelu ani zapisanych danych."""
from __future__ import annotations

from typing import Any

_INSTALLED = False

_TYPE_LABELS = {
    "narzedzie": "Narzędzie",
    "maszyna": "Maszyna",
    "magazyn": "Magazyn",
    "zamowienie": "Zlecenie wykonania",
    "zlecenie_wykonania": "Zlecenie wykonania",
}

_PRIORITY_LABELS = {
    "niski": "Niski",
    "normalny": "Normalny",
    "wysoki": "Wysoki",
    "krytyczny": "Krytyczny",
    "low": "Niski",
    "normal": "Normalny",
    "high": "Wysoki",
    "critical": "Krytyczny",
}

_STATUS_LABELS = {
    "ok": "Sprawna",
    "sprawna": "Sprawna",
    "sprawny": "Sprawny",
    "awaria": "Awaria",
    "serwis": "Serwis",
    "warm": "Ostrzeżenie",
    "warning": "Ostrzeżenie",
    "available": "Dostępne",
    "dostepne": "Dostępne",
    "dostępne": "Dostępne",
    "in_use": "W użyciu",
    "w_uzyciu": "W użyciu",
    "w użyciu": "W użyciu",
    "repair": "Do naprawy",
    "do_naprawy": "Do naprawy",
    "do naprawy": "Do naprawy",
    "sharpening": "Do ostrzenia",
    "do_ostrzenia": "Do ostrzenia",
    "do ostrzenia": "Do ostrzenia",
    "modification": "Modyfikacja",
    "modyfikacja": "Modyfikacja",
    "lost": "Zagubione",
    "zagubione": "Zagubione",
    "unclassified": "Niesklasyfikowany",
    "niesklasyfikowany": "Niesklasyfikowany",
    "issued": "Wydany",
    "wydany": "Wydany",
}


def _raw_object_id(item: dict[str, Any]) -> str:
    return str(
        item.get("obiekt_id")
        or item.get("object_id")
        or item.get("narzedzie_id")
        or item.get("maszyna_id")
        or ""
    ).strip()


def _choice_map(loader) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        rows = loader() or []
    except Exception:
        rows = []
    for raw_id, raw_label in rows:
        object_id = str(raw_id or "").strip()
        label = str(raw_label or "").strip()
        if object_id and label:
            out[object_id.casefold()] = label
    return out


def _pretty_choice(object_id: str, label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return object_id or "—"
    prefix = object_id.strip()
    folded = text.casefold()
    if prefix and folded.startswith(prefix.casefold()):
        tail = text[len(prefix):].lstrip(" -—|")
        if tail:
            return f"{prefix} — {tail}"
    return text


def _object_label(item: dict[str, Any]) -> str:
    object_id = _raw_object_id(item)
    if not object_id:
        return "—"

    typ = str(item.get("typ_dyspozycji") or item.get("typ") or "").strip().casefold()
    try:
        from dyspozycje_sources import (
            load_machine_choices,
            load_magazyn_choices,
            load_tool_choices,
            load_zlecenie_wykonania_choices,
        )
        loaders = {
            "narzedzie": load_tool_choices,
            "maszyna": load_machine_choices,
            "magazyn": load_magazyn_choices,
            "zamowienie": load_zlecenie_wykonania_choices,
            "zlecenie_wykonania": load_zlecenie_wykonania_choices,
        }
        loader = loaders.get(typ)
        if loader is not None:
            label = _choice_map(loader).get(object_id.casefold())
            if label:
                return _pretty_choice(object_id, label)
    except Exception:
        pass
    return object_id


def _type_label(item: dict[str, Any]) -> str:
    raw = str(item.get("typ_dyspozycji") or item.get("typ") or "").strip()
    return _TYPE_LABELS.get(raw.casefold(), raw or "—")


def _priority_label(item: dict[str, Any]) -> str:
    raw = str(item.get("priorytet") or "normalny").strip()
    return _PRIORITY_LABELS.get(raw.casefold(), raw.capitalize() if raw else "Normalny")


def _days_word(value: int) -> str:
    value = abs(int(value))
    return "dzień" if value == 1 else "dni"


def _due_in_label(item: dict[str, Any]) -> str:
    import gui_zlecenia as dysp

    if dysp._dysp_is_closed(item):
        return "—"
    raw = str(item.get("termin") or item.get("deadline") or "").strip()
    if not raw:
        return "—"
    try:
        deadline = dysp._dt.date.fromisoformat(raw[:10])
    except Exception:
        return "—"
    days = (deadline - dysp._dt.date.today()).days
    if days == 0:
        return "dziś"
    if days == 1:
        return "jutro"
    if days == -1:
        return "1 dzień po terminie"
    if days < 0:
        overdue = abs(days)
        return f"{overdue} {_days_word(overdue)} po terminie"
    return f"za {days} {_days_word(days)}"


def _stored_status(item: dict[str, Any]) -> str:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    return str(
        item.get("status_obiektu")
        or item.get("status_narzedzia")
        or item.get("status_maszyny")
        or meta.get("status_obiektu")
        or meta.get("status")
        or ""
    ).strip()


def _source_status(item: dict[str, Any]) -> str:
    import gui_zlecenia as dysp

    typ = str(item.get("typ_dyspozycji") or item.get("typ") or "").strip().casefold()
    object_id = _raw_object_id(item)
    variants = dysp._normalize_object_id(object_id)
    if not variants:
        return ""

    if typ == "narzedzie":
        cache = dysp._load_tool_status_cache()
    elif typ == "maszyna":
        cache = dysp._load_machine_status_cache()
    else:
        return ""

    for key in variants:
        value = str(cache.get(key) or "").strip()
        if value:
            return value
    return ""


def _status_label(item: dict[str, Any]) -> str:
    raw = _source_status(item) or _stored_status(item)
    if not raw:
        return "—"
    key = raw.strip().casefold().replace("-", "_")
    return _STATUS_LABELS.get(key, raw)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        import gui_zlecenia as dysp
    except Exception:
        return

    if getattr(dysp, "_wm_presentation_b2_v1", False):
        _INSTALLED = True
        return

    dysp._dysp_object_label = _object_label
    dysp._dysp_type_label = _type_label
    dysp._dysp_priority_label = _priority_label
    dysp._dysp_due_in_label = _due_in_label
    dysp._dysp_related_status_label = _status_label
    dysp._wm_presentation_b2_v1 = True
    _INSTALLED = True


__all__ = ["install"]
