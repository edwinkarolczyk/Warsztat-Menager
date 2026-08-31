# version: 1.1
"""Bezpieczna korekta wpisów przeglądów/serwisów maszyn dla Brygadzisty.

Korekta dotyka wyłącznie pól opisowych i dat wpisu serwisowego. Nie pozwala
zmieniać statusu, ID, źródła cyklu ani klucza/powiązania Dyspozycji.
Każda zmiana zostawia ślad w ``edit_history``.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_USAGE_TITLE_PREFIX = "Użytkowanie maszyny"
_ACTIVE_REVIEW_COLUMNS = ("date", "type", "status", "people", "details")
_HISTORY_REVIEW_COLUMNS = ("plan", "done", "type", "people", "details")
_MAX_DECORATE_RETRIES = 25
_SAFE_FIELDS = (
    "planned_date",
    "suggested_workers",
    "description",
    "completed_at",
    "completed_by",
    "result_note",
)
_FIELD_LABELS = {
    "planned_date": "Planowana data",
    "suggested_workers": "Sugerowani",
    "description": "Zakres / opis",
    "completed_at": "Data wykonania",
    "completed_by": "Wykonali",
    "result_note": "Wynik / uwagi",
}


def _normalize_role(value: object) -> str:
    try:
        from wm_access import normalize_role_name

        return str(normalize_role_name(str(value or "")) or "").strip().casefold()
    except Exception:
        return str(value or "").strip().casefold()


def _active_login(window: Any) -> str:
    current = window
    while current is not None:
        for attr in ("_wm_login", "active_login", "login", "user_login"):
            try:
                value = str(getattr(current, attr, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
        current = getattr(current, "master", None)

    try:
        from services.profile_service import ProfileService

        return str(ProfileService.ensure_active_user_or_none() or "").strip()
    except Exception:
        return ""


def _actor_is_foreman(actor: str) -> bool:
    actor = str(actor or "").strip()
    if not actor:
        return False
    try:
        from services.profile_service import get_user

        user = get_user(actor) or {}
        return _normalize_role(
            user.get("rola") or user.get("role") or user.get("ranga")
        ) == "brygadzista"
    except Exception:
        return False


def _active_role(window: Any) -> str:
    current = window
    while current is not None:
        for attr in ("_wm_rola", "rola", "role", "user_role"):
            try:
                value = getattr(current, attr, "")
            except Exception:
                value = ""
            if str(value or "").strip():
                return _normalize_role(value)
        current = getattr(current, "master", None)

    login = _active_login(window)
    if not login:
        return ""
    return "brygadzista" if _actor_is_foreman(login) else ""


def _walk_widgets(widget: Any):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield from _walk_widgets(child)


def _widget_text(widget: Any) -> str:
    try:
        return str(widget.cget("text") or "").strip()
    except Exception:
        return ""


def _tree_columns(tree: Any) -> tuple[str, ...]:
    try:
        raw = tree.cget("columns")
        if isinstance(raw, (tuple, list)):
            return tuple(str(item) for item in raw)
        return tuple(str(item) for item in tree.tk.splitlist(raw))
    except Exception:
        return ()


def _machine_id_from_window(window: Any) -> str:
    try:
        title = str(window.title() or "")
    except Exception:
        return ""
    if not title.startswith(_USAGE_TITLE_PREFIX):
        return ""
    tail = title[len(_USAGE_TITLE_PREFIX):].strip()
    tail = re.sub(r"^[\s—–-]+", "", tail).strip()
    return tail.split()[0].strip() if tail else ""


def _id_variants(value: object) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw.casefold()}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return out


def _same_machine_id(left: object, right: object) -> bool:
    return bool(_id_variants(left) & _id_variants(right))


def _load_machine(gui_module: Any, machine_id: str):
    cfg = gui_module.get_config() or {}
    rows, primary_path = gui_module.load_machines_rows_with_fallback(
        cfg, gui_module.resolve_rel
    )
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    for idx, row in enumerate(rows):
        current_id = row.get("id") or row.get("nr_ewid") or row.get("nr")
        if _same_machine_id(current_id, machine_id):
            return rows, primary_path, idx, dict(row)
    return rows, primary_path, None, None


def _save_machine(
    gui_module: Any,
    rows: list[dict],
    primary_path: str,
    idx: int,
    machine: dict,
) -> bool:
    clean = dict(machine)
    strip = getattr(gui_module, "_strip_schedule_fields", None)
    if callable(strip):
        try:
            clean = strip(clean)
        except Exception:
            clean = dict(machine)
    rows[idx] = clean
    saver = getattr(gui_module, "_save_machines", None)
    if not callable(saver):
        return False
    return bool(saver(primary_path, rows))


def _parse_plan(gui_module: Any, value: object) -> dt.date | None:
    parser = getattr(gui_module, "_parse_schedule_date", None)
    if callable(parser):
        try:
            parsed = parser(value)
            if isinstance(parsed, dt.datetime):
                return parsed.date()
            if isinstance(parsed, dt.date):
                return parsed
        except Exception:
            pass
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except Exception:
        return None


def _format_plan(gui_module: Any, value: object) -> str:
    formatter = getattr(gui_module, "_format_machine_review_date", None)
    if callable(formatter):
        try:
            return str(formatter(value))
        except Exception:
            pass
    parsed = _parse_plan(gui_module, value)
    return parsed.isoformat() if parsed else "—"


def _format_done(gui_module: Any, value: object) -> str:
    formatter = getattr(gui_module, "_format_machine_history_dt", None)
    if callable(formatter):
        try:
            return str(formatter(value))
        except Exception:
            pass
    return str(value or "") or "—"


def _review_status_key(gui_module: Any, value: object) -> str:
    helper = getattr(gui_module, "_review_status_key", None)
    if callable(helper):
        try:
            return str(helper(value) or "")
        except Exception:
            pass
    raw = str(value or "").strip().casefold()
    if raw in {"done", "wykonany", "completed"}:
        return "done"
    if raw in {"cancelled", "anulowany", "canceled"}:
        return "cancelled"
    return "planned"


def _people(value: object) -> list[str]:
    raw = value if isinstance(value, list) else str(value or "").split(",")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        login = str(item or "").strip()
        if not login:
            continue
        key = login.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(login)
    return out


def _review_context_from_tree(tree: Any) -> dict[str, Any] | None:
    columns = _tree_columns(tree)
    if columns not in {_ACTIVE_REVIEW_COLUMNS, _HISTORY_REVIEW_COLUMNS}:
        return None
    try:
        selected = tree.selection()
        if not selected:
            return None
        values = list(tree.item(selected[0], "values") or [])
    except Exception:
        return None
    if columns == _ACTIVE_REVIEW_COLUMNS and len(values) >= 5:
        return {
            "kind": "active",
            "plan": str(values[0] or ""),
            "done": "",
            "type": str(values[1] or ""),
            "status": str(values[2] or ""),
            "people": str(values[3] or ""),
            "details": str(values[4] or ""),
        }
    if columns == _HISTORY_REVIEW_COLUMNS and len(values) >= 5:
        return {
            "kind": "history",
            "plan": str(values[0] or ""),
            "done": str(values[1] or ""),
            "type": str(values[2] or ""),
            "status": "Wykonany",
            "people": str(values[3] or ""),
            "details": str(values[4] or ""),
        }
    return None


def _selected_review_context(window: Any) -> dict[str, Any] | None:
    tree = getattr(window, "_wm_review_correction_tree", None)
    if tree is not None:
        context = _review_context_from_tree(tree)
        if context is not None:
            return context

    try:
        focus = window.focus_get()
    except Exception:
        focus = None
    if focus is not None:
        context = _review_context_from_tree(focus)
        if context is not None:
            return context

    for widget in _walk_widgets(window):
        context = _review_context_from_tree(widget)
        if context is not None:
            return context
    return None


def _review_source(entry: dict) -> str:
    return str(entry.get("source") or "manual").strip().casefold()


def _candidate_matches(gui_module: Any, entry: dict, context: dict[str, Any]) -> bool:
    plan = _format_plan(
        gui_module,
        entry.get("date") or entry.get("planned_date") or entry.get("completed_at"),
    )
    if plan != str(context.get("plan") or ""):
        return False

    display_type = str(context.get("type") or "").strip()
    if display_type == "Przegląd cykliczny":
        if _review_source(entry) != "cycle":
            return False
    elif display_type:
        actual_type = str(entry.get("type") or entry.get("typ") or "").strip()
        if actual_type != display_type:
            return False

    if context.get("kind") == "history":
        done = str(context.get("done") or "").strip()
        if (
            done
            and done != "—"
            and _format_done(gui_module, entry.get("completed_at")) != done
        ):
            return False
        if _review_status_key(gui_module, entry.get("status")) != "done":
            return False
    else:
        status_text = str(context.get("status") or "").strip().casefold()
        entry_status = str(entry.get("status") or "").strip().casefold()
        if (
            "trakcie" in status_text
            and entry_status not in {"in_progress", "w_trakcie", "w trakcie"}
        ):
            return False
        if (
            "planowan" in status_text
            and _review_status_key(gui_module, entry.get("status")) == "done"
        ):
            return False
    return True


def _find_persisted_review(gui_module: Any, machine: dict, context: dict[str, Any]):
    reviews = machine.get("reviews")
    if not isinstance(reviews, list):
        return None, "missing"
    matches = [
        entry
        for entry in reviews
        if isinstance(entry, dict) and _candidate_matches(gui_module, entry, context)
    ]
    if len(matches) == 1:
        return matches[0], "ok"
    if len(matches) > 1:
        return None, "ambiguous"
    return None, "missing"


def _default_cycle_entry(
    gui_module: Any, machine: dict, context: dict[str, Any]
) -> dict | None:
    plan = _parse_plan(gui_module, context.get("plan"))
    if plan is None or str(context.get("type") or "") != "Przegląd cykliczny":
        return None
    review_type_fn = getattr(gui_module, "_machine_default_review_type", None)
    review_type = (
        str(review_type_fn(machine))
        if callable(review_type_fn)
        else str(machine.get("default_review_type") or "Przegląd okresowy")
    )
    suggested = _people(context.get("people")) or _people(machine.get("review_workers"))
    new_id = getattr(
        gui_module,
        "_new_review_id",
        lambda: "rev_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"),
    )()
    month_names = dict(getattr(gui_module, "MONTH_LABELS_PL", []))
    month_name = month_names.get(plan.month, str(plan.month))
    return {
        "id": str(new_id),
        "type": review_type or "Przegląd okresowy",
        "planned_date": plan.isoformat(),
        "status": "planned",
        "source": "cycle",
        "cycle_year": plan.year,
        "cycle_month": plan.month,
        "suggested_workers": suggested,
        "description": f"Przegląd cykliczny: {month_name} {plan.year}",
        "completed_at": "",
        "completed_by": [],
        "result_note": "",
        "photos": [],
    }


def _load_user_logins(gui_module: Any, extra: list[str] | None = None) -> list[str]:
    values: list[str] = []
    loader = getattr(gui_module, "_load_wm_user_logins", None)
    if callable(loader):
        try:
            values.extend(
                str(item).strip() for item in (loader() or []) if str(item).strip()
            )
        except Exception:
            pass
    values.extend(extra or [])
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        login = str(value or "").strip()
        if not login:
            continue
        key = login.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(login)
    return out


def _safe_snapshot(entry: dict) -> dict[str, Any]:
    return {
        "planned_date": str(entry.get("planned_date") or entry.get("date") or ""),
        "suggested_workers": _people(
            entry.get("suggested_workers") or entry.get("suggested_people")
        ),
        "description": str(entry.get("description") or ""),
        "completed_at": str(entry.get("completed_at") or ""),
        "completed_by": _people(entry.get("completed_by")),
        "result_note": str(entry.get("result_note") or ""),
    }


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, list) or isinstance(right, list):
        return _people(left) == _people(right)
    return str(left or "") == str(right or "")


def _merge_completion_date(
    gui_module: Any, old_value: object, new_date: dt.date
) -> str:
    parser = getattr(gui_module, "_parse_machine_dt", None)
    old_dt = None
    if callable(parser):
        try:
            old_dt = parser(old_value)
        except Exception:
            old_dt = None
    if not isinstance(old_dt, dt.datetime):
        old_dt = dt.datetime.now().replace(microsecond=0)
    return dt.datetime.combine(
        new_date, old_dt.time().replace(microsecond=0)
    ).isoformat()


def _cycle_identity(
    entry: dict, fallback_plan: dt.date | None
) -> tuple[int, int] | None:
    try:
        year = int(entry.get("cycle_year") or 0)
        month = int(entry.get("cycle_month") or 0)
    except Exception:
        year = month = 0
    if year > 0 and 1 <= month <= 12:
        return year, month
    if fallback_plan is not None:
        return fallback_plan.year, fallback_plan.month
    return None


def _update_linked_dyspozycja(
    machine_id: str,
    entry: dict,
    *,
    original_plan: dt.date | None,
    new_plan: dt.date,
    actor: str,
    reason: str,
    edited_at: str,
) -> str:
    """Zmień wyłącznie termin istniejącej auto-Dyspozycji; nie zmieniaj linku wpisu."""
    if original_plan == new_plan or _review_source(entry) != "cycle":
        return ""

    try:
        from dyspozycje_store import get_dyspozycja, load_dyspozycje, update_dyspozycja
    except Exception as exc:
        return f"Nie udało się załadować Dyspozycji: {exc}"

    linked_id = str(entry.get("dyspozycja_id") or "").strip()
    identity = _cycle_identity(entry, original_plan)
    if not linked_id and identity is not None:
        year, month = identity
        matches: list[dict] = []
        for item in load_dyspozycje():
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            if str(meta.get("auto_source") or "").strip() != "machine_cycle_review":
                continue
            if not _same_machine_id(
                meta.get("machine_id") or item.get("obiekt_id"), machine_id
            ):
                continue
            try:
                same_cycle = (
                    int(meta.get("cycle_year") or 0) == year
                    and int(meta.get("cycle_month") or 0) == month
                )
            except Exception:
                same_cycle = False
            if same_cycle:
                matches.append(item)
        if len(matches) == 1:
            linked_id = str(matches[0].get("id") or "").strip()

    if not linked_id:
        return ""

    try:
        current = get_dyspozycja(linked_id)
        if not current:
            return ""
        meta = dict(current.get("meta") or {})
        if str(meta.get("auto_source") or "").strip() != "machine_cycle_review":
            return ""
        meta["planned_review_date"] = new_plan.isoformat()
        meta["last_review_correction"] = {
            "edited_at": edited_at,
            "edited_by": actor,
            "reason": reason,
        }
        updated = update_dyspozycja(
            linked_id,
            {"termin": new_plan.isoformat(), "meta": meta},
        )
        if updated is None:
            return "Nie udało się zaktualizować terminu powiązanej Dyspozycji."
        return ""
    except Exception as exc:
        logger.exception("[Maszyny][CORRECTION] Błąd aktualizacji Dyspozycji")
        return (
            "Korekta maszyny została zapisana, ale termin Dyspozycji "
            f"nie został zmieniony: {exc}"
        )


def _apply_correction(
    gui_module: Any,
    *,
    machine_id: str,
    context: dict[str, Any],
    expected_review_id: str,
    requested: dict[str, Any],
    actor: str,
    reason: str,
) -> tuple[bool, str, dict | None]:
    if not _actor_is_foreman(actor):
        return False, "Korektę wpisu może zapisać tylko Brygadzista.", None

    reason = str(reason or "").strip()
    if len(reason) < 3:
        return False, "Podaj powód korekty.", None

    rows, primary_path, idx, machine = _load_machine(gui_module, machine_id)
    if idx is None or machine is None:
        return False, "Nie znaleziono maszyny w aktywnym pliku danych.", None

    target = None
    if expected_review_id:
        reviews = machine.get("reviews")
        if isinstance(reviews, list):
            for entry in reviews:
                if (
                    isinstance(entry, dict)
                    and str(entry.get("id") or "").strip() == expected_review_id
                ):
                    target = entry
                    break
    if target is None:
        target, state = _find_persisted_review(gui_module, machine, context)
        if state == "ambiguous":
            return (
                False,
                "Nie można jednoznacznie wskazać wpisu. Korekta nie została zapisana.",
                None,
            )

    virtual_cycle = False
    if target is None:
        target = _default_cycle_entry(gui_module, machine, context)
        if target is None:
            return False, "Nie znaleziono zapisanego wpisu do korekty.", None
        virtual_cycle = True

    before = _safe_snapshot(target)
    original_plan = _parse_plan(gui_module, before.get("planned_date"))
    new_plan = requested.get("planned_date")
    if not isinstance(new_plan, dt.date):
        return False, "Podaj poprawną planowaną datę.", None

    if _review_source(target) == "cycle":
        identity = _cycle_identity(target, original_plan)
        if identity is not None and (new_plan.year, new_plan.month) != identity:
            return (
                False,
                "Przegląd cykliczny można skorygować tylko w obrębie tego samego "
                "miesiąca. Zmianę miesiąca wykonaj w ustawieniach cyklu maszyny.",
                None,
            )

    status_key = _review_status_key(gui_module, target.get("status"))
    completed_at = before.get("completed_at")
    completed_by = before.get("completed_by")
    result_note = before.get("result_note")
    if status_key == "done" or completed_at:
        completed_date = requested.get("completed_date")
        if not isinstance(completed_date, dt.date):
            return False, "Podaj poprawną datę wykonania.", None
        if completed_date > dt.date.today():
            return False, "Data wykonania nie może być w przyszłości.", None
        completed_at = _merge_completion_date(gui_module, completed_at, completed_date)
        completed_by = _people(requested.get("completed_by"))
        if not completed_by:
            return (
                False,
                "Wybierz przynajmniej jedną osobę, która wykonała przegląd/serwis.",
                None,
            )
        result_note = str(requested.get("result_note") or "").strip()

    after = {
        "planned_date": new_plan.isoformat(),
        "suggested_workers": _people(requested.get("suggested_workers")),
        "description": str(requested.get("description") or "").strip(),
        "completed_at": completed_at,
        "completed_by": completed_by,
        "result_note": result_note,
    }
    changes = {
        field: {"from": before.get(field), "to": after.get(field)}
        for field in _SAFE_FIELDS
        if not _same_value(before.get(field), after.get(field))
    }
    if not changes:
        return False, "Nie zmieniono żadnego pola.", target

    if virtual_cycle:
        reviews = (
            list(machine.get("reviews") or [])
            if isinstance(machine.get("reviews"), list)
            else []
        )
        reviews.append(target)
        machine["reviews"] = reviews

    for field in _SAFE_FIELDS:
        target[field] = after[field]

    edited_at = dt.datetime.now().replace(microsecond=0).isoformat()
    history_raw = target.get("edit_history")
    history = list(history_raw) if isinstance(history_raw, list) else []
    history.append(
        {
            "edited_at": edited_at,
            "edited_by": actor,
            "reason": reason,
            "changes": changes,
        }
    )
    target["edit_history"] = history
    target["last_edited_at"] = edited_at
    target["last_edited_by"] = actor

    if not _save_machine(gui_module, rows, primary_path, idx, machine):
        return False, "Nie udało się zapisać korekty do pliku maszyn.", None

    dysp_warning = _update_linked_dyspozycja(
        machine_id,
        target,
        original_plan=original_plan,
        new_plan=new_plan,
        actor=actor,
        reason=reason,
        edited_at=edited_at,
    )
    if dysp_warning:
        return True, dysp_warning, target
    return True, "Korekta została zapisana.", target


def _history_text(entry: dict) -> str:
    history = entry.get("edit_history")
    if not isinstance(history, list) or not history:
        return "Brak wcześniejszych korekt tego wpisu."
    blocks: list[str] = []
    for item in reversed(history[-20:]):
        if not isinstance(item, dict):
            continue
        lines = [
            f"{item.get('edited_at') or '—'} — {item.get('edited_by') or '—'}",
            f"Powód: {item.get('reason') or '—'}",
        ]
        changes = (
            item.get("changes") if isinstance(item.get("changes"), dict) else {}
        )
        for field, delta in changes.items():
            if not isinstance(delta, dict):
                continue
            label = _FIELD_LABELS.get(field, str(field))
            old = delta.get("from")
            new = delta.get("to")
            if isinstance(old, list):
                old = ", ".join(str(x) for x in old)
            if isinstance(new, list):
                new = ", ".join(str(x) for x in new)
            lines.append(f"{label}: {old or '—'} → {new or '—'}")
        blocks.append("\n".join(lines))
    return (
        "\n\n".join(blocks)
        if blocks
        else "Brak wcześniejszych korekt tego wpisu."
    )


def _open_correction_dialog(window: Any, gui_module: Any) -> None:
    box = getattr(gui_module, "messagebox", None)
    ttk = getattr(gui_module, "ttk", None)
    tk_module = getattr(gui_module, "tk", None)
    if box is None or ttk is None or tk_module is None:
        return

    if _active_role(window) != "brygadzista":
        box.showwarning(
            "Korekta wpisu",
            "Korektę wpisu może wykonać tylko Brygadzista.",
            parent=window,
        )
        return

    actor = _active_login(window)
    if not _actor_is_foreman(actor):
        box.showwarning(
            "Korekta wpisu",
            "Nie udało się potwierdzić uprawnień Brygadzisty.",
            parent=window,
        )
        return

    machine_id = _machine_id_from_window(window)
    context = _selected_review_context(window)
    if not machine_id or context is None:
        box.showinfo(
            "Korekta wpisu",
            "Najpierw zaznacz przegląd/serwis na liście.",
            parent=window,
        )
        return

    _rows, _path, idx, machine = _load_machine(gui_module, machine_id)
    if idx is None or machine is None:
        box.showerror(
            "Korekta wpisu", "Nie znaleziono maszyny w danych.", parent=window
        )
        return

    target, state = _find_persisted_review(gui_module, machine, context)
    if state == "ambiguous":
        box.showerror(
            "Korekta wpisu",
            "Znaleziono kilka pasujących wpisów. Dla bezpieczeństwa korekta "
            "została zablokowana.",
            parent=window,
        )
        return
    if target is None:
        target = _default_cycle_entry(gui_module, machine, context)
        if target is None:
            box.showerror(
                "Korekta wpisu", "Nie znaleziono wpisu do korekty.", parent=window
            )
            return
        persisted_target = False
    else:
        persisted_target = True

    original = _safe_snapshot(target)
    plan = (
        _parse_plan(gui_module, original.get("planned_date"))
        or _parse_plan(gui_module, context.get("plan"))
        or dt.date.today()
    )
    completed_raw = str(original.get("completed_at") or "")
    completed_date = _parse_plan(gui_module, completed_raw) if completed_raw else None
    is_done = (
        _review_status_key(gui_module, target.get("status")) == "done"
        or bool(completed_raw)
    )

    base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
    real_toplevel = getattr(base_tk, "Toplevel", None)
    if real_toplevel is None:
        return
    dialog = real_toplevel(window)
    dialog.title("Korekta przeglądu / serwisu")
    dialog.geometry("760x700" if is_done else "760x570")
    dialog.minsize(680, 520)
    dialog.transient(window)
    dialog.grab_set()

    form = ttk.Frame(dialog, padding=12)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    plan_var = base_tk.StringVar(
        master=dialog, value=_format_plan(gui_module, plan)
    )
    ttk.Label(form, text="Planowana data:").grid(
        row=0, column=0, sticky="e", padx=4, pady=4
    )
    plan_row = ttk.Frame(form)
    plan_row.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
    ttk.Entry(plan_row, textvariable=plan_var).pack(
        side="left", fill="x", expand=True
    )

    def _pick_date(var, initial, title):
        try:
            from calendar_ui_runtime import open_date_picker

            open_date_picker(
                dialog,
                initial=initial,
                on_select=lambda chosen: var.set(_format_plan(gui_module, chosen)),
                title=title,
            )
        except Exception as exc:
            box.showerror(
                "Kalendarz",
                f"Nie udało się otworzyć kalendarza:\n{exc}",
                parent=dialog,
            )

    ttk.Button(
        plan_row,
        text="📅",
        width=3,
        command=lambda: _pick_date(
            plan_var,
            _parse_plan(gui_module, plan_var.get()) or plan,
            "Planowana data przeglądu / serwisu",
        ),
    ).pack(side="left", padx=(6, 0))

    current_suggested = _people(original.get("suggested_workers"))
    current_completed = _people(original.get("completed_by"))
    users = _load_user_logins(
        gui_module, current_suggested + current_completed + [actor]
    )

    ttk.Label(form, text="Sugerowani:").grid(
        row=1, column=0, sticky="ne", padx=4, pady=4
    )
    suggested_frame = ttk.Frame(form)
    suggested_frame.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
    suggested_vars: dict[str, Any] = {}
    for pos, login in enumerate(users):
        var = base_tk.BooleanVar(master=dialog, value=login in current_suggested)
        suggested_vars[login] = var
        ttk.Checkbutton(suggested_frame, text=login, variable=var).grid(
            row=pos // 4,
            column=pos % 4,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

    ttk.Label(form, text="Zakres / opis:").grid(
        row=2, column=0, sticky="ne", padx=4, pady=4
    )
    desc = base_tk.Text(form, height=5, wrap="word")
    desc.grid(row=2, column=1, sticky="nsew", padx=4, pady=4)
    desc.insert("1.0", str(original.get("description") or ""))

    row = 3
    completed_var = None
    completed_vars: dict[str, Any] = {}
    result = None
    if is_done:
        completed_var = base_tk.StringVar(
            master=dialog,
            value=_format_plan(gui_module, completed_date or dt.date.today()),
        )
        ttk.Label(form, text="Data wykonania:").grid(
            row=row, column=0, sticky="e", padx=4, pady=4
        )
        completed_row = ttk.Frame(form)
        completed_row.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        ttk.Entry(completed_row, textvariable=completed_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            completed_row,
            text="📅",
            width=3,
            command=lambda: _pick_date(
                completed_var,
                _parse_plan(gui_module, completed_var.get())
                or completed_date
                or dt.date.today(),
                "Data wykonania przeglądu / serwisu",
            ),
        ).pack(side="left", padx=(6, 0))
        row += 1

        ttk.Label(form, text="Wykonali:").grid(
            row=row, column=0, sticky="ne", padx=4, pady=4
        )
        completed_frame = ttk.Frame(form)
        completed_frame.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        for pos, login in enumerate(users):
            var = base_tk.BooleanVar(master=dialog, value=login in current_completed)
            completed_vars[login] = var
            ttk.Checkbutton(completed_frame, text=login, variable=var).grid(
                row=pos // 4,
                column=pos % 4,
                sticky="w",
                padx=(0, 10),
                pady=2,
            )
        row += 1

        ttk.Label(form, text="Wynik / uwagi:").grid(
            row=row, column=0, sticky="ne", padx=4, pady=4
        )
        result = base_tk.Text(form, height=5, wrap="word")
        result.grid(row=row, column=1, sticky="nsew", padx=4, pady=4)
        result.insert("1.0", str(original.get("result_note") or ""))
        row += 1

    ttk.Label(form, text="Powód korekty:").grid(
        row=row, column=0, sticky="ne", padx=4, pady=4
    )
    reason = base_tk.Text(form, height=3, wrap="word")
    reason.grid(row=row, column=1, sticky="nsew", padx=4, pady=4)
    row += 1

    history_count = (
        len(target.get("edit_history") or [])
        if isinstance(target.get("edit_history"), list)
        else 0
    )
    history_row = ttk.Frame(form)
    history_row.grid(row=row, column=1, sticky="w", padx=4, pady=(4, 6))
    ttk.Label(history_row, text=f"Historia korekt: {history_count}").pack(side="left")
    ttk.Button(
        history_row,
        text="Pokaż historię",
        command=lambda: box.showinfo(
            "Historia korekt", _history_text(target), parent=dialog
        ),
    ).pack(side="left", padx=(8, 0))
    row += 1

    ttk.Label(
        form,
        text="Chronione: status, ID, źródło/cykl i klucz Dyspozycji nie są edytowane.",
    ).grid(row=row, column=1, sticky="w", padx=4, pady=(0, 8))
    row += 1

    buttons = ttk.Frame(form)
    buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    expected_id = str(target.get("id") or "").strip() if persisted_target else ""

    def _save() -> None:
        if not _actor_is_foreman(actor):
            box.showwarning(
                "Korekta wpisu",
                "Uprawnienie Brygadzisty nie jest już aktywne. Korekta nie została zapisana.",
                parent=dialog,
            )
            return

        reason_text = reason.get("1.0", "end").strip()
        if len(reason_text) < 3:
            box.showwarning(
                "Korekta wpisu", "Podaj powód korekty.", parent=dialog
            )
            return
        plan_date = _parse_plan(gui_module, plan_var.get())
        if plan_date is None:
            box.showwarning(
                "Korekta wpisu", "Podaj poprawną planowaną datę.", parent=dialog
            )
            return

        requested = {
            "planned_date": plan_date,
            "suggested_workers": [
                login
                for login, var in suggested_vars.items()
                if bool(var.get())
            ],
            "description": desc.get("1.0", "end").strip(),
        }
        if is_done and completed_var is not None:
            requested["completed_date"] = _parse_plan(
                gui_module, completed_var.get()
            )
            requested["completed_by"] = [
                login
                for login, var in completed_vars.items()
                if bool(var.get())
            ]
            requested["result_note"] = (
                result.get("1.0", "end").strip() if result is not None else ""
            )

        ok, message, _saved_entry = _apply_correction(
            gui_module,
            machine_id=machine_id,
            context=context,
            expected_review_id=expected_id,
            requested=requested,
            actor=actor,
            reason=reason_text,
        )
        if not ok:
            box.showwarning("Korekta wpisu", message, parent=dialog)
            return

        if "Dyspozycji" in message and "nie" in message.casefold():
            box.showwarning("Korekta wpisu", message, parent=dialog)
        else:
            box.showinfo(
                "Korekta wpisu",
                "Korekta została zapisana. Okno maszyny zostanie zamknięte, "
                "aby przy ponownym otwarciu wczytać świeże dane.",
                parent=dialog,
            )
        dialog.destroy()
        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass

    ttk.Button(buttons, text="Zapisz korektę", command=_save).pack(
        side="left", padx=4
    )
    ttk.Button(buttons, text="Anuluj", command=dialog.destroy).pack(
        side="left", padx=4
    )


def _decorate_usage_window(window: Any, gui_module: Any) -> None:
    if getattr(window, "_wm_review_correction_decorated", False):
        return
    try:
        title = str(window.title() or "")
    except Exception:
        return
    if not title.startswith(_USAGE_TITLE_PREFIX):
        return

    if _active_role(window) != "brygadzista":
        window._wm_review_correction_decorated = True
        return

    ttk = getattr(gui_module, "ttk", None)
    if ttk is None:
        return

    action_frame = None
    review_trees: list[Any] = []
    for widget in _walk_widgets(window):
        columns = _tree_columns(widget)
        if columns in {_ACTIVE_REVIEW_COLUMNS, _HISTORY_REVIEW_COLUMNS}:
            review_trees.append(widget)
        try:
            child_texts = {_widget_text(child) for child in widget.winfo_children()}
        except Exception:
            child_texts = set()
        if (
            "Dodaj przegląd / serwis" in child_texts
            and "Oznacz jako wykonany" in child_texts
        ):
            action_frame = widget

    if action_frame is None:
        retries = int(getattr(window, "_wm_review_correction_retries", 0) or 0) + 1
        window._wm_review_correction_retries = retries
        if retries >= _MAX_DECORATE_RETRIES:
            window._wm_review_correction_decorated = True
            logger.warning(
                "[Maszyny][CORRECTION] Nie znaleziono paska akcji po %d próbach.",
                retries,
            )
            return
        try:
            window.after(80, lambda: _decorate_usage_window(window, gui_module))
        except Exception:
            pass
        return

    def _remember(tree):
        def _on_select(_event=None):
            try:
                if tree.selection():
                    window._wm_review_correction_tree = tree
            except Exception:
                pass

        return _on_select

    for tree in review_trees:
        try:
            tree.bind("<<TreeviewSelect>>", _remember(tree), add="+")
        except Exception:
            pass

    ttk.Button(
        action_frame,
        text="Korekta wpisu",
        command=lambda: _open_correction_dialog(window, gui_module),
    ).pack(side="left", padx=(6, 0))
    window._wm_review_correction_decorated = True


def install_machine_review_correction(gui_module: Any) -> bool:
    """Dodaj bezpieczną korektę wpisów wyłącznie dla roli Brygadzista."""
    if gui_module is None:
        return False
    tk_module = getattr(gui_module, "tk", None)
    if tk_module is None:
        return False
    if getattr(tk_module, "_wm_machine_correction_proxy", False):
        return True

    real_toplevel = getattr(tk_module, "Toplevel", None)
    if real_toplevel is None:
        return False

    class _CorrectionAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def _decorate() -> None:
                try:
                    _decorate_usage_window(self, gui_module)
                except Exception:
                    logger.exception(
                        "[Maszyny][CORRECTION] Błąd dekorowania okna maszyny."
                    )

            try:
                self.after_idle(_decorate)
            except Exception:
                _decorate()

    class _TkCorrectionProxy:
        _wm_machine_correction_proxy = True
        _wm_machine_backdate_proxy = bool(
            getattr(tk_module, "_wm_machine_backdate_proxy", False)
        )
        _wm_docx_runtime_proxy = bool(
            getattr(tk_module, "_wm_docx_runtime_proxy", False)
        )
        _wm_base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
        Toplevel = _CorrectionAwareToplevel

        def __getattr__(self, name: str):
            return getattr(tk_module, name)

    gui_module.tk = _TkCorrectionProxy()
    return True


__all__ = ["install_machine_review_correction"]
