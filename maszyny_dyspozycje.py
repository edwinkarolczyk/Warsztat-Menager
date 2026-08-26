# version: 1.1
# Zmiany 1.1:
# - Cykl przeglądu uwzględnia dokładny dzień miesiąca zapisany w maszynie.
# - Dodano dwukierunkową synchronizację cyklicznego serwisu z automatyczną Dyspozycją.
# - Powiązanie zachowuje maszynę, rok i miesiąc, więc kolejne lata są osobnymi cyklami bez duplikatów.
# Zmiany 1.0:
# - Automatyczne Dyspozycje dla cyklicznych przeglądów maszyn do 7 dni przed terminem.
# - Klucz cyklu zawiera maszynę, rok i miesiąc, więc przeglądy powtarzają się co roku bez duplikatów.

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any, Iterable

from dyspozycje_store import (
    add_dyspozycja,
    load_dyspozycje,
    make_dyspozycja,
    set_dyspozycja_status,
)


AUTO_SOURCE = "machine_cycle_review"
AUTO_WINDOW_DAYS = 7

_MONTH_NAMES = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}


def _machine_id(machine: dict[str, Any]) -> str:
    return str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or machine.get("kod")
        or ""
    ).strip()


def _machine_name(machine: dict[str, Any]) -> str:
    return str(
        machine.get("nazwa")
        or machine.get("name")
        or machine.get("opis")
        or ""
    ).strip()


def _machine_type(machine: dict[str, Any]) -> str:
    return str(machine.get("typ") or machine.get("type") or "").strip()


def _review_months(machine: dict[str, Any]) -> list[int]:
    value = (
        machine.get("review_months")
        or machine.get("inspection_months")
        or machine.get("miesiace_przegladu")
        or machine.get("miesiące_przeglądu")
        or machine.get("months")
        or []
    )
    if not isinstance(value, list):
        value = [value]
    out: list[int] = []
    for item in value:
        try:
            month = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12 and month not in out:
            out.append(month)
    return sorted(out)


def _review_day(machine: dict[str, Any]) -> int:
    try:
        day = int(machine.get("review_day") or machine.get("inspection_day") or 1)
    except (TypeError, ValueError):
        day = 1
    return max(1, min(31, day))


def _planned_cycle_date(year: int, month: int, day: int) -> dt.date:
    last_day = calendar.monthrange(int(year), int(month))[1]
    return dt.date(int(year), int(month), min(max(1, int(day)), last_day))


def _default_review_type(machine: dict[str, Any]) -> str:
    return str(
        machine.get("default_review_type")
        or machine.get("domyslny_typ_przegladu")
        or machine.get("typ_przegladu")
        or "Przegląd okresowy"
    ).strip() or "Przegląd okresowy"


def _parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _review_date(review: dict[str, Any], machine: dict[str, Any] | None = None) -> dt.date | None:
    parsed = _parse_date(
        review.get("date")
        or review.get("data")
        or review.get("planned_date")
        or review.get("completed_at")
        or review.get("done_at")
    )
    if parsed is not None:
        return parsed
    try:
        year = int(review.get("cycle_year") or 0)
        month = int(review.get("cycle_month") or 0)
    except (TypeError, ValueError):
        return None
    if year <= 0 or not 1 <= month <= 12:
        return None
    return _planned_cycle_date(year, month, _review_day(machine or {}))


def _is_done_status(value: Any) -> bool:
    raw = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    return raw in {
        "done",
        "wykonany",
        "wykonane",
        "zrobione",
        "zamkniety",
        "zamknięty",
        "completed",
    }


def _cycle_done(
    machine: dict[str, Any],
    *,
    year: int,
    month: int,
    review_type: str,
) -> bool:
    reviews = machine.get("reviews")
    if not isinstance(reviews, list):
        return False
    wanted_type = str(review_type or "").strip().lower()
    for review in reviews:
        if not isinstance(review, dict) or not _is_done_status(review.get("status")):
            continue
        date_value = _review_date(review, machine)
        if date_value is None or date_value.year != year or date_value.month != month:
            continue
        current_type = str(review.get("type") or review.get("typ") or "").strip().lower()
        if not current_type or current_type == wanted_type:
            return True
    return False


def _cycle_key(machine_id: str, year: int, month: int) -> str:
    return f"machine-cycle-review:{machine_id}:{year}:{month:02d}"


def _existing_auto_keys(rows: Iterable[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
            continue
        key = str(meta.get("auto_key") or "").strip()
        if key:
            keys.add(key)
    return keys


def _find_auto_by_key(rows: Iterable[dict[str, Any]], auto_key: str) -> dict[str, Any] | None:
    wanted = str(auto_key or "").strip()
    if not wanted:
        return None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
            continue
        if str(meta.get("auto_key") or "").strip() == wanted:
            return row
    return None


def _build_cycle_spec(
    machine: dict[str, Any],
    *,
    planned: dt.date,
    review_type: str | None = None,
) -> dict[str, Any]:
    machine_id = _machine_id(machine)
    name = _machine_name(machine)
    machine_type = _machine_type(machine)
    review_type = str(review_type or _default_review_type(machine)).strip() or "Przegląd okresowy"
    machine_label = f"{machine_id} - {name}" if name else machine_id
    month_name = _MONTH_NAMES.get(planned.month, str(planned.month))
    auto_key = _cycle_key(machine_id, planned.year, planned.month)

    details = [
        "Dyspozycja dodana automatycznie z cyklicznego przeglądu maszyny.",
        f"Maszyna: {machine_label}.",
    ]
    if machine_type:
        details.append(f"Typ maszyny: {machine_type}.")
    details.extend(
        [
            f"Cykl: {month_name} {planned.year}.",
            f"Planowany termin przeglądu: {planned.strftime('%d-%m-%Y')}.",
        ]
    )

    return {
        "typ_dyspozycji": "maszyna",
        "tytul": f"Przegląd cykliczny – {machine_label}",
        "opis": " ".join(details),
        "autor": "system",
        "przypisane_do": "",
        "dla_wszystkich": True,
        "termin": planned.isoformat(),
        "priorytet": "normalny",
        "modul_zrodlowy": "maszyny",
        "obiekt_id": machine_id,
        "status": "nowa",
        "meta": {
            "auto_source": AUTO_SOURCE,
            "auto_key": auto_key,
            "auto_created": True,
            "machine_id": machine_id,
            "object_label": machine_label,
            "cycle_year": planned.year,
            "cycle_month": planned.month,
            "cycle_month_name": month_name,
            "planned_review_date": planned.isoformat(),
            "review_type": review_type,
        },
    }


def collect_due_machine_cycle_specs(
    machines: Iterable[dict[str, Any]],
    existing_dyspozycje: Iterable[dict[str, Any]],
    *,
    today: dt.date | None = None,
    window_days: int = AUTO_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Zwraca brakujące automatyczne Dyspozycje dla cykli w najbliższych dniach."""

    today = today or dt.date.today()
    window_days = max(0, int(window_days))
    existing_keys = _existing_auto_keys(existing_dyspozycje)
    specs: list[dict[str, Any]] = []
    years = (today.year, today.year + 1)

    for machine in machines or []:
        if not isinstance(machine, dict):
            continue
        machine_id = _machine_id(machine)
        months = _review_months(machine)
        if not machine_id or not months:
            continue

        review_type = _default_review_type(machine)
        review_day = _review_day(machine)
        for year in years:
            for month in months:
                planned = _planned_cycle_date(year, month, review_day)
                days_to_due = (planned - today).days
                if days_to_due < 0 or days_to_due > window_days:
                    continue
                if _cycle_done(
                    machine,
                    year=year,
                    month=month,
                    review_type=review_type,
                ):
                    continue

                auto_key = _cycle_key(machine_id, year, month)
                if auto_key in existing_keys:
                    continue
                specs.append(
                    _build_cycle_spec(
                        machine,
                        planned=planned,
                        review_type=review_type,
                    )
                )
                existing_keys.add(auto_key)

    return specs


def find_cycle_dyspozycja_for_review(
    machine: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any] | None:
    machine_id = _machine_id(machine)
    planned = _review_date(review, machine)
    if not machine_id or planned is None:
        return None
    auto_key = _cycle_key(machine_id, planned.year, planned.month)
    return _find_auto_by_key(load_dyspozycje(), auto_key)


def _ensure_cycle_dyspozycja_for_review(
    machine: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any] | None:
    existing = find_cycle_dyspozycja_for_review(machine, review)
    if existing:
        return existing
    machine_id = _machine_id(machine)
    planned = _review_date(review, machine)
    if not machine_id or planned is None:
        return None
    spec = _build_cycle_spec(
        machine,
        planned=planned,
        review_type=str(review.get("type") or review.get("typ") or _default_review_type(machine)),
    )
    item = make_dyspozycja(**spec)
    return add_dyspozycja(item)


def sync_review_to_dyspozycja(
    machine: dict[str, Any],
    review: dict[str, Any],
    *,
    status: str,
    actor: str = "",
    note: str = "",
) -> dict[str, Any] | None:
    """Przenieś rozpoczęcie/wykonanie cyklicznego serwisu do jego Dyspozycji."""

    source = str(review.get("source") or "").strip().lower()
    review_id = str(review.get("id") or "").strip().lower()
    is_cycle = (
        source == "cycle"
        or review_id.startswith("cycle_")
        or bool(review.get("cycle_year") and review.get("cycle_month"))
    )
    if not is_cycle:
        return None

    item = _ensure_cycle_dyspozycja_for_review(machine, review)
    if not item:
        return None
    review["dyspozycja_id"] = str(item.get("id") or "")
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    if meta.get("auto_key"):
        review["auto_key"] = str(meta.get("auto_key"))

    target = str(status or "").strip().lower()
    current = str(item.get("status") or "nowa").strip().lower()
    dysp_id = str(item.get("id") or "").strip()
    if not dysp_id:
        return item

    if target in {"in_progress", "w_toku", "started"}:
        if current == "nowa":
            return set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
        if current == "wstrzymana":
            return set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
        return item

    if target in {"done", "wykonany", "completed", "zamknieta"}:
        if current == "nowa":
            item = set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
            current = str(item.get("status") or current).strip().lower()
        if current in {"w_toku", "wstrzymana"}:
            return set_dyspozycja_status(
                dysp_id,
                "zamknieta",
                changed_by=actor,
                uwagi=note,
            ) or item
    return item


def _id_variants(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw, raw.lower()}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return out


def sync_machine_review_from_dyspozycja(
    dyspozycja: dict[str, Any],
    *,
    actor: str = "",
    result_note: str = "",
) -> bool:
    """Przenieś start/zamknięcie automatycznej Dyspozycji do wpisu serwisowego maszyny."""

    if not isinstance(dyspozycja, dict):
        return False
    meta = dyspozycja.get("meta") if isinstance(dyspozycja.get("meta"), dict) else {}
    if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
        return False

    machine_id = str(meta.get("machine_id") or dyspozycja.get("obiekt_id") or "").strip()
    dysp_id = str(dyspozycja.get("id") or "").strip()
    planned = _parse_date(meta.get("planned_review_date") or dyspozycja.get("termin"))
    if not machine_id or not dysp_id or planned is None:
        return False

    try:
        from gui_maszyny import (
            _apply_machine_status_change,
            _machine_now_iso,
            _normalize_machine_status,
            _save_machines,
            get_config,
            load_machines_rows_with_fallback,
            resolve_rel,
        )
    except Exception:
        return False

    cfg = get_config() or {}
    rows, primary_path = load_machines_rows_with_fallback(cfg, resolve_rel)
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    wanted_ids = _id_variants(machine_id)
    machine_index = None
    for idx, row in enumerate(rows):
        rid = _machine_id(row)
        if wanted_ids.intersection(_id_variants(rid)):
            machine_index = idx
            break
    if machine_index is None:
        return False

    machine = dict(rows[machine_index])
    raw_reviews = machine.get("reviews")
    reviews = [
        dict(review)
        for review in raw_reviews
        if isinstance(review, dict)
    ] if isinstance(raw_reviews, list) else []
    review_type = str(meta.get("review_type") or _default_review_type(machine)).strip()
    auto_key = str(meta.get("auto_key") or _cycle_key(machine_id, planned.year, planned.month))

    target_review: dict[str, Any] | None = None
    for review in reviews:
        if str(review.get("dyspozycja_id") or "").strip() == dysp_id:
            target_review = review
            break
    if target_review is None:
        for review in reviews:
            source = str(review.get("source") or "").strip().lower()
            date_value = _review_date(review, machine)
            current_type = str(review.get("type") or review.get("typ") or "").strip()
            if (
                source == "cycle"
                and date_value is not None
                and date_value.year == planned.year
                and date_value.month == planned.month
                and (not current_type or current_type == review_type)
            ):
                target_review = review
                break

    if target_review is None:
        month_name = _MONTH_NAMES.get(planned.month, str(planned.month))
        target_review = {
            "id": f"rev_auto_{planned.year}{planned.month:02d}_{machine_id}",
            "type": review_type or "Przegląd okresowy",
            "planned_date": planned.isoformat(),
            "status": "planned",
            "source": "cycle",
            "cycle_year": planned.year,
            "cycle_month": planned.month,
            "suggested_workers": list(machine.get("review_workers") or [])
            if isinstance(machine.get("review_workers"), list)
            else [],
            "description": f"Przegląd cykliczny: {month_name} {planned.year}",
            "completed_at": "",
            "completed_by": [],
            "result_note": "",
            "photos": [],
        }
        reviews.append(target_review)

    target_review["dyspozycja_id"] = dysp_id
    target_review["auto_key"] = auto_key
    target_review["planned_date"] = planned.isoformat()
    target_review["source"] = "cycle"
    target_review["cycle_year"] = planned.year
    target_review["cycle_month"] = planned.month

    status = str(dyspozycja.get("status") or "").strip().lower()
    who = str(
        actor
        or dyspozycja.get("zamkniete_przez")
        or dyspozycja.get("wykonuje")
        or dyspozycja.get("autor")
        or "system"
    ).strip()

    if status == "w_toku" and not _is_done_status(target_review.get("status")):
        target_review["status"] = "in_progress"
        target_review["started_at"] = str(
            dyspozycja.get("rozpoczal_at") or _machine_now_iso()
        )
        target_review["started_by"] = who
        if _normalize_machine_status(machine.get("status")) != "warn":
            note = (
                f"Rozpoczęto {review_type or 'przegląd / serwis'}"
                f" | plan: {planned.isoformat()} | Dyspozycja: {dysp_id}"
            )
            _apply_machine_status_change(
                machine,
                "alert",
                actor=who,
                note=note,
                photos=[],
            )
    elif status == "zamknieta":
        target_review["status"] = "done"
        target_review["completed_at"] = str(
            dyspozycja.get("zamknieto_at")
            or dyspozycja.get("wykonano")
            or _machine_now_iso()
        )
        target_review["completed_by"] = [who] if who else []
        note_value = str(result_note or dyspozycja.get("uwagi") or "").strip()
        if note_value:
            target_review["result_note"] = note_value
        if _normalize_machine_status(machine.get("status")) == "alert":
            note = (
                f"Wykonano {review_type or 'przegląd / serwis'}"
                f" | plan: {planned.isoformat()} | Dyspozycja: {dysp_id}"
            )
            if note_value:
                note += f" | {note_value}"
            _apply_machine_status_change(
                machine,
                "ok",
                actor=who,
                note=note,
                photos=[],
            )
    else:
        return False

    machine["reviews"] = reviews
    rows[machine_index] = machine
    return bool(_save_machines(primary_path, rows))


def ensure_due_machine_cycle_dyspozycje(
    *,
    today: dt.date | None = None,
    window_days: int = AUTO_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Dodaje brakujące cykliczne Dyspozycje i zwraca tylko nowo utworzone rekordy."""

    try:
        from gui_maszyny import load_machines_rows

        machines = load_machines_rows()
    except Exception:
        machines = []

    existing = load_dyspozycje()
    specs = collect_due_machine_cycle_specs(
        machines,
        existing,
        today=today,
        window_days=window_days,
    )

    created: list[dict[str, Any]] = []
    for spec in specs:
        auto_key = str((spec.get("meta") or {}).get("auto_key") or "").strip()
        if auto_key and auto_key in _existing_auto_keys(load_dyspozycje()):
            continue
        item = make_dyspozycja(**spec)
        created.append(add_dyspozycja(item))
    return created
