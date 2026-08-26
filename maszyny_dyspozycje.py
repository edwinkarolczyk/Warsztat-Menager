# version: 1.0
# Zmiany 1.0:
# - Automatyczne Dyspozycje dla cyklicznych przeglądów maszyn do 7 dni przed terminem.
# - Klucz cyklu zawiera maszynę, rok i miesiąc, więc przeglądy powtarzają się co roku bez duplikatów.

from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

from dyspozycje_store import add_dyspozycja, load_dyspozycje, make_dyspozycja


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
        date_value = _parse_date(
            review.get("date")
            or review.get("data")
            or review.get("planned_date")
            or review.get("completed_at")
            or review.get("done_at")
        )
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

    # Sprawdzamy bieżący i następny rok. Dzięki temu np. 26 grudnia
    # może już utworzyć Dyspozycję na cykl 1 stycznia kolejnego roku.
    years = (today.year, today.year + 1)

    for machine in machines or []:
        if not isinstance(machine, dict):
            continue
        machine_id = _machine_id(machine)
        months = _review_months(machine)
        if not machine_id or not months:
            continue

        name = _machine_name(machine)
        machine_type = _machine_type(machine)
        review_type = _default_review_type(machine)
        machine_label = f"{machine_id} - {name}" if name else machine_id

        for year in years:
            for month in months:
                planned = dt.date(year, month, 1)
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

                month_name = _MONTH_NAMES.get(month, str(month))
                details = [
                    "Dyspozycja dodana automatycznie z cyklicznego przeglądu maszyny.",
                    f"Maszyna: {machine_label}.",
                ]
                if machine_type:
                    details.append(f"Typ maszyny: {machine_type}.")
                details.extend(
                    [
                        f"Cykl: {month_name} {year}.",
                        f"Planowany termin przeglądu: {planned.strftime('%d-%m-%Y')}.",
                    ]
                )

                specs.append(
                    {
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
                            "cycle_year": year,
                            "cycle_month": month,
                            "cycle_month_name": month_name,
                            "planned_review_date": planned.isoformat(),
                            "review_type": review_type,
                        },
                    }
                )
                existing_keys.add(auto_key)

    return specs


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
        # Ponowny odczyt tuż przed zapisem zmniejsza ryzyko duplikatu,
        # gdy odświeżenie zostanie wywołane drugi raz niemal równocześnie.
        if auto_key and auto_key in _existing_auto_keys(load_dyspozycje()):
            continue
        item = make_dyspozycja(**spec)
        created.append(add_dyspozycja(item))
    return created
