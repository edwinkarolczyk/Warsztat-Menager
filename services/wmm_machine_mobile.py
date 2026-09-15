# -*- coding: utf-8 -*-
"""WMM -> Maszyny: szybkie akcje oparte wyłącznie na istniejącym modelu WM."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any
from urllib.parse import unquote, urlparse


logger = logging.getLogger(__name__)

_STATUS_LABELS = {
    "ok": "Sprawna",
    "alert": "Serwis / przegląd",
    "warn": "Awaria",
}

_STATUS_ALIASES = {
    "ok": "ok",
    "sprawna": "ok",
    "sprawny": "ok",
    "sprawne": "ok",
    "alert": "alert",
    "serwis": "alert",
    "przeglad": "alert",
    "przegląd": "alert",
    "serwis/przeglad": "alert",
    "serwis/przegląd": "alert",
    "warn": "warn",
    "warm": "warn",
    "warning": "warn",
    "awaria": "warn",
    "stop": "warn",
}

_DONE_REVIEW_STATUSES = {
    "done",
    "wykonany",
    "wykonane",
    "zrobione",
    "zamkniety",
    "zamknięty",
    "completed",
}
_CANCELLED_REVIEW_STATUSES = {
    "cancelled",
    "canceled",
    "anulowany",
    "anulowane",
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _normalize_status(value: object) -> str:
    raw = str(value or "").strip().casefold().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    return _STATUS_ALIASES.get(raw, _STATUS_ALIASES.get(raw.replace(" ", ""), raw or "ok"))


def _parse_dt(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _duration_minutes(started_at: object, ended_at: object) -> int:
    start = _parse_dt(started_at)
    end = _parse_dt(ended_at)
    if start is None or end is None:
        return 0
    try:
        return max(0, int((end - start).total_seconds()) // 60)
    except Exception:
        return 0


def _wmm_text(prefix: str, text: object = "") -> str:
    extra = str(text or "").strip()
    return f"[WMM] {prefix}" + (f" — {extra}" if extra else "")


def _begin_repair_period(
    machine: dict[str, Any],
    *,
    author: str,
    note: str,
) -> None:
    """Rozpocznij Awarię bez dopisywania osobnego rekordu poprzedniego stanu."""

    now = _now_iso()
    machine["status"] = "warn"
    machine["status_current"] = {
        "status": "warn",
        "label": _STATUS_LABELS["warn"],
        "started_at": now,
        "changed_by": author,
        "note": note,
        "photos": [],
    }


def _finish_repair_period(
    machine: dict[str, Any],
    *,
    author: str,
    close_note: str,
) -> int:
    """Zamknij dokładnie jeden okres Awarii i ustaw bieżący stan Sprawna."""

    now = _now_iso()
    current = machine.get("status_current")
    if not isinstance(current, dict) or _normalize_status(current.get("status")) != "warn":
        current = {
            "status": "warn",
            "label": _STATUS_LABELS["warn"],
            "started_at": now,
            "changed_by": author,
            "note": "[WMM] Szybka naprawa",
            "photos": [],
        }

    closed = dict(current)
    closed["status"] = "warn"
    closed["label"] = _STATUS_LABELS["warn"]
    closed.setdefault("photos", [])
    closed["ended_at"] = now
    closed["duration_minutes"] = _duration_minutes(closed.get("started_at"), now)
    closed["closed_by"] = author
    closed["close_note"] = close_note

    history = machine.get("status_history")
    if not isinstance(history, list):
        history = []
    history.append(closed)
    machine["status_history"] = history

    machine["status"] = "ok"
    machine["status_current"] = {
        "status": "ok",
        "label": _STATUS_LABELS["ok"],
        "started_at": now,
        "changed_by": author,
        "note": close_note,
        "photos": [],
    }
    return int(closed.get("duration_minutes") or 0)


def start_quick_repair(
    impl: Any,
    machine_id: str,
    author: str,
    note: str = "",
) -> dict[str, Any]:
    """Ustaw istniejący status WM ``Awaria`` i rozpocznij pomiar czasu naprawy."""

    actor = str(author or "WMM").strip() or "WMM"
    text = _wmm_text("Szybka naprawa — rozpoczęcie", note)

    def mutate(machine: dict[str, Any]) -> None:
        if _normalize_status(machine.get("status")) == "warn":
            raise RuntimeError(
                "Maszyna ma już status Awaria. Zakończ bieżącą naprawę zamiast rozpoczynać następną."
            )
        _begin_repair_period(machine, author=actor, note=text)

    return impl._update_machine(machine_id, mutate)


def finish_quick_repair(
    impl: Any,
    machine_id: str,
    author: str,
    note: str = "",
) -> tuple[dict[str, Any], int]:
    """Zamknij jeden okres ``Awaria`` i przywróć istniejący status WM ``Sprawna``."""

    actor = str(author or "WMM").strip() or "WMM"
    text = _wmm_text("Szybka naprawa — zakończenie", note)
    result: dict[str, int] = {"duration": 0}

    def mutate(machine: dict[str, Any]) -> None:
        if _normalize_status(machine.get("status")) != "warn":
            raise RuntimeError("Maszyna nie ma aktywnego statusu Awaria.")
        result["duration"] = _finish_repair_period(
            machine,
            author=actor,
            close_note=text,
        )

    updated = impl._update_machine(machine_id, mutate)
    return updated, int(result["duration"])


def _wm_combined_cycle_entries(machine: dict[str, Any]) -> list[dict[str, Any]]:
    """Użyj dokładnie listy harmonogramu budowanej przez desktopowy moduł Maszyn."""

    try:
        import gui_maszyny_legacy as machines_gui

        entries = machines_gui._combined_machine_review_entries(
            machine,
            today=date.today(),
            years_ahead=1,
        )
    except Exception as exc:
        raise RuntimeError(f"Nie udało się odczytać harmonogramu przeglądów WM: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("source") or "").strip().casefold() != "cycle":
            continue
        status = str(entry.get("status") or "planned").strip().casefold()
        if status in _DONE_REVIEW_STATUSES or status in _CANCELLED_REVIEW_STATUSES:
            continue
        row = dict(entry)
        row.setdefault("display_type", "Przegląd cykliczny")
        rows.append(row)
    return rows


def cycle_reviews(impl: Any, machine_id: str) -> list[dict[str, Any]]:
    machine = impl._find_machine(machine_id)
    if not isinstance(machine, dict):
        raise RuntimeError("Nie znaleziono maszyny.")
    return _wm_combined_cycle_entries(machine)


def _machine_reviews(machine: dict[str, Any]) -> list[dict[str, Any]]:
    raw = machine.get("reviews")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _find_cycle_display_entry(machine: dict[str, Any], review_id: str) -> dict[str, Any]:
    wanted = str(review_id or "").strip()
    if not wanted:
        raise RuntimeError("Nie wybrano przeglądu cyklicznego.")
    for entry in _wm_combined_cycle_entries(machine):
        if str(entry.get("id") or "").strip() == wanted:
            return entry
    raise RuntimeError(
        "Ten przegląd cykliczny nie jest już aktywny w harmonogramie WM. Odśwież listę."
    )


def _new_review_id(reviews: list[dict[str, Any]]) -> str:
    base = "rev_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    existing = {str(item.get("id") or "").strip() for item in reviews}
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def _materialize_cycle_review(
    machine: dict[str, Any],
    display_entry: dict[str, Any],
) -> dict[str, Any]:
    """Materializuj wirtualny cycle_YYYY_MM tak samo jak desktop przy pierwszej akcji."""

    reviews = _machine_reviews(machine)
    wanted_id = str(display_entry.get("id") or "").strip()
    for review in reviews:
        if str(review.get("id") or "").strip() == wanted_id:
            return review

    if str(display_entry.get("source") or "").strip().casefold() != "cycle":
        raise RuntimeError("Wybrany wpis nie jest przeglądem cyklicznym WM.")

    raw_date = str(display_entry.get("date") or display_entry.get("planned_date") or "").strip()
    try:
        planned = date.fromisoformat(raw_date[:10])
    except ValueError as exc:
        raise RuntimeError("Przegląd cykliczny nie ma poprawnej daty planowanej.") from exc

    suggested = display_entry.get("suggested_workers") or display_entry.get("suggested_people") or []
    if not isinstance(suggested, list):
        suggested = [str(suggested)] if str(suggested or "").strip() else []

    month_names = (
        "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
        "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
    )
    entry = {
        "id": _new_review_id(reviews),
        "type": str(display_entry.get("type") or "Przegląd okresowy").strip() or "Przegląd okresowy",
        "planned_date": planned.isoformat(),
        "status": "planned",
        "source": "cycle",
        "cycle_year": planned.year,
        "cycle_month": planned.month,
        "suggested_workers": [str(item).strip() for item in suggested if str(item or "").strip()],
        "description": f"Przegląd cykliczny: {month_names[planned.month - 1]} {planned.year}",
        "completed_at": "",
        "completed_by": [],
        "result_note": "",
        "photos": [],
    }
    reviews.append(entry)
    machine["reviews"] = reviews
    return entry


def _sync_review_to_disposition(
    machine: dict[str, Any],
    review: dict[str, Any],
    *,
    status: str,
    actor: str,
    note: str,
) -> None:
    """Synchronizuj istniejącą Dyspozycję tym samym helperem co desktop WM."""

    try:
        from _maszyny_dyspozycje_core import sync_review_to_dyspozycja

        linked = sync_review_to_dyspozycja(
            machine,
            review,
            status=status,
            actor=actor,
            note=note,
        )
    except Exception:
        logger.exception("[WMM][MASZYNY] Synchronizacja przeglądu z Dyspozycją nieudana.")
        return
    if linked:
        review["dyspozycja_id"] = str(linked.get("id") or "").strip()


def _apply_wm_machine_status(
    machine: dict[str, Any],
    new_status: str,
    *,
    actor: str,
    note: str,
) -> None:
    """Użyj istniejącego mechanizmu statusu Maszyny zamiast tworzyć mobilny wariant."""

    try:
        import gui_maszyny_legacy as machines_gui

        machines_gui._apply_machine_status_change(
            machine,
            new_status,
            actor=actor,
            note=note,
            photos=[],
        )
    except Exception as exc:
        raise RuntimeError(f"Nie udało się zmienić statusu maszyny przez mechanizm WM: {exc}") from exc


def start_cycle_review(
    impl: Any,
    machine_id: str,
    review_id: str,
    author: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    actor = str(author or "WMM").strip() or "WMM"
    result: dict[str, Any] = {}

    def mutate(machine: dict[str, Any]) -> None:
        display = _find_cycle_display_entry(machine, review_id)
        review = _materialize_cycle_review(machine, display)
        status = str(review.get("status") or "planned").strip().casefold()
        if status == "in_progress":
            raise RuntimeError("Ten przegląd cykliczny jest już rozpoczęty.")
        if status in _DONE_REVIEW_STATUSES:
            raise RuntimeError("Ten przegląd cykliczny jest już wykonany.")

        review["status"] = "in_progress"
        review["started_at"] = _now_iso()
        review["started_by"] = actor
        note = _wmm_text(
            "Rozpoczęto przegląd cykliczny",
            f"plan: {review.get('planned_date') or '—'}",
        )
        _sync_review_to_disposition(
            machine,
            review,
            status="in_progress",
            actor=actor,
            note=note,
        )
        _apply_wm_machine_status(machine, "alert", actor=actor, note=note)
        result.update(review)

    updated = impl._update_machine(machine_id, mutate)
    return updated, dict(result)


def complete_cycle_review(
    impl: Any,
    machine_id: str,
    review_id: str,
    author: str,
    result_note: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    actor = str(author or "WMM").strip() or "WMM"
    result: dict[str, Any] = {}

    def mutate(machine: dict[str, Any]) -> None:
        display = _find_cycle_display_entry(machine, review_id)
        review = _materialize_cycle_review(machine, display)
        status = str(review.get("status") or "planned").strip().casefold()
        if status in _DONE_REVIEW_STATUSES:
            raise RuntimeError("Ten przegląd cykliczny jest już wykonany.")

        note = _wmm_text("Przegląd cykliczny wykonany", result_note)
        review["status"] = "done"
        review["completed_at"] = _now_iso()
        review["completed_by"] = [actor]
        review["result_note"] = note
        _sync_review_to_disposition(
            machine,
            review,
            status="done",
            actor=actor,
            note=note,
        )
        if _normalize_status(machine.get("status")) == "alert":
            _apply_wm_machine_status(machine, "ok", actor=actor, note=note)
        result.update(review)

    updated = impl._update_machine(machine_id, mutate)
    return updated, dict(result)


def install(impl: Any) -> None:
    """Dołącz mobilną naprawę i obsługę istniejących przeglądów cyklicznych WM."""

    if getattr(impl, "_WMM_MACHINE_MOBILE_V3", False):
        return

    original_do_get = impl._WmmHandler.do_GET
    original_do_post = impl._WmmHandler.do_POST

    def machine_mobile_do_get(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        cycle_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/cycle-reviews", path)
        if not cycle_match:
            return original_do_get(self)
        if not self._require_pairing_key():
            return None
        try:
            items = cycle_reviews(impl, unquote(cycle_match.group(1)))
            self._send(200, {"ok": True, "count": len(items), "items": items})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] odczyt przeglądów cyklicznych nieudany")
            self._send(500, {"ok": False, "error": f"Błąd odczytu przeglądów cyklicznych: {exc}"})
        return None

    def machine_mobile_do_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        repair_start_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/start", path)
        repair_finish_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/finish", path)
        cycle_match = impl.re.fullmatch(
            r"/api/v1/machines/([^/]+)/cycle-reviews/([^/]+)/(start|complete)",
            path,
        )
        match = repair_start_match or repair_finish_match or cycle_match
        if not match:
            return original_do_post(self)

        payload = self._read_json()
        if not self._require_pairing_key():
            return None
        try:
            if repair_start_match:
                item = start_quick_repair(
                    impl,
                    unquote(repair_start_match.group(1)),
                    self._author(),
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(200, {"ok": True, "item": item})
                return None

            if repair_finish_match:
                item, duration = finish_quick_repair(
                    impl,
                    unquote(repair_finish_match.group(1)),
                    self._author(),
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(200, {"ok": True, "item": item, "duration_minutes": duration})
                return None

            machine_id = unquote(cycle_match.group(1))
            review_id = unquote(cycle_match.group(2))
            action = cycle_match.group(3)
            if action == "start":
                item, review = start_cycle_review(
                    impl,
                    machine_id,
                    review_id,
                    self._author(),
                )
            else:
                item, review = complete_cycle_review(
                    impl,
                    machine_id,
                    review_id,
                    self._author(),
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
            self._send(200, {"ok": True, "item": item, "review": review})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] szybka akcja Maszyny nieudana")
            self._send(500, {"ok": False, "error": f"Błąd zapisu Maszyny: {exc}"})
        return None

    impl._WmmHandler.do_GET = machine_mobile_do_get
    impl._WmmHandler.do_POST = machine_mobile_do_post
    impl._WMM_MACHINE_MOBILE_V3 = True
