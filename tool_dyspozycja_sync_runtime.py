# version: 1.0
"""Synchronizacja statusu serwisowego Narzędzia z jego Dyspozycją.

Bez automatycznego tworzenia nowych Dyspozycji. Zmieniamy tylko jednoznacznie
powiązaną aktywną Dyspozycję typu narzedzie dla tego samego obiektu.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dyspozycje_store as DS


_START_STATUSES = {"w ostrzeniu", "w naprawie", "w serwisie"}
_DONE_STATUSES = {"po ostrzeniu"}
_SERVICE_STATUSES = {
    "do ostrzenia", "w ostrzeniu", "po ostrzeniu",
    "w naprawie", "w serwisie", "uszkodzone",
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _id_variants(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return out


def _tool_id(tool: dict[str, Any], fallback: Any = "") -> str:
    return str(tool.get("nr") or tool.get("numer") or tool.get("id") or fallback or "").strip()


def _is_service_completion(tool: dict[str, Any], *, previous_status: str, new_status: str) -> bool:
    new_key = _norm(new_status)
    if new_key in _DONE_STATUSES:
        return True
    if new_key != "sprawne":
        return False
    mode = _norm(tool.get("tryb") or tool.get("mode"))
    previous_key = _norm(previous_status)
    return mode in {"stare", "st", "sn"} or previous_key in _SERVICE_STATUSES


def _matching_active(tool_id: str) -> list[dict[str, Any]]:
    variants = _id_variants(tool_id)
    if not variants:
        return []
    out: list[dict[str, Any]] = []
    for row in DS.load_dyspozycje():
        if not isinstance(row, dict):
            continue
        if _norm(row.get("typ_dyspozycji")) != "narzedzie":
            continue
        if _norm(row.get("status")) == "zamknieta":
            continue
        object_id = str(row.get("obiekt_id") or row.get("object_id") or row.get("narzedzie_id") or "").strip()
        if not variants.intersection(_id_variants(object_id)):
            continue
        out.append(row)
    return out


def _choose_target(rows: list[dict[str, Any]], action: str) -> dict[str, Any] | None:
    if not rows:
        return None
    if action == "close":
        running = [row for row in rows if _norm(row.get("status")) == "w_toku"]
        if len(running) == 1:
            return running[0]
        if len(rows) == 1:
            return rows[0]
        return None
    running = [row for row in rows if _norm(row.get("status")) == "w_toku"]
    if len(running) == 1:
        return running[0]
    candidates = [row for row in rows if _norm(row.get("status")) in {"nowa", "wstrzymana"}]
    return candidates[0] if len(candidates) == 1 else None


def _append_sync_meta(row: dict[str, Any], *, tool_id: str, previous_status: str, new_status: str, actor: str, action: str) -> dict[str, Any]:
    meta = dict(row.get("meta") or {})
    history_raw = meta.get("tool_sync_history")
    history = list(history_raw) if isinstance(history_raw, list) else []
    when = str(row.get("zamknieto_at") or "") if action == "close" else str(row.get("rozpoczal_at") or "")
    if not when:
        when = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    history.append({
        "tool_id": tool_id,
        "z_statusu": str(previous_status or "").strip(),
        "na_status": str(new_status or "").strip(),
        "akcja": action,
        "kto": str(actor or "").strip(),
        "kiedy": when,
    })
    meta["tool_sync_history"] = history[-100:]
    updated = DS.update_dyspozycja(str(row.get("id") or ""), {"meta": meta})
    return updated or row


def sync_tool_disposition(tool: dict[str, Any], *, actor: str, previous_status: str = "", new_status: str | None = None, tool_id: str = "") -> dict[str, Any]:
    """Synchronizuj jedną aktywną Dyspozycję z serwisowym statusem Narzędzia."""
    tool = dict(tool or {})
    identity = _tool_id(tool, tool_id)
    status = str(new_status if new_status is not None else tool.get("status") or "").strip()
    status_key = _norm(status)
    action = ""
    if status_key in _START_STATUSES:
        action = "start"
    elif _is_service_completion(tool, previous_status=previous_status, new_status=status):
        action = "close"
    else:
        return {"changed": False, "reason": "status_not_service_transition"}

    matches = _matching_active(identity)
    target = _choose_target(matches, action)
    if target is None:
        return {
            "changed": False,
            "reason": "no_unique_active_disposition" if matches else "no_active_disposition",
            "active_count": len(matches),
        }

    dysp_id = str(target.get("id") or "").strip()
    current = _norm(target.get("status"))
    if action == "start":
        if current == "w_toku":
            changed = target
        else:
            changed = DS.set_dyspozycja_status(dysp_id, "w_toku", changed_by=actor)
        if not changed:
            return {"changed": False, "reason": "transition_rejected", "dyspozycja_id": dysp_id}
        changed = _append_sync_meta(changed, tool_id=identity, previous_status=previous_status, new_status=status, actor=actor, action="start")
        return {
            "changed": current != "w_toku",
            "action": "start",
            "dyspozycja_id": dysp_id,
            "status": changed.get("status"),
            "wykonuje": changed.get("wykonuje"),
        }

    changed = target
    if current == "nowa":
        changed = DS.set_dyspozycja_status(dysp_id, "w_toku", changed_by=actor)
        if not changed:
            return {"changed": False, "reason": "start_before_close_rejected", "dyspozycja_id": dysp_id}
        current = "w_toku"
    if current in {"w_toku", "wstrzymana"}:
        changed = DS.set_dyspozycja_status(dysp_id, "zamknieta", changed_by=actor)
    if not changed or _norm(changed.get("status")) != "zamknieta":
        return {"changed": False, "reason": "close_rejected", "dyspozycja_id": dysp_id}
    changed = _append_sync_meta(changed, tool_id=identity, previous_status=previous_status, new_status=status, actor=actor, action="close")
    return {
        "changed": True,
        "action": "close",
        "dyspozycja_id": dysp_id,
        "status": changed.get("status"),
        "zamkniete_przez": changed.get("zamkniete_przez"),
        "zamknieto_at": changed.get("zamknieto_at"),
    }


__all__ = ["sync_tool_disposition"]
