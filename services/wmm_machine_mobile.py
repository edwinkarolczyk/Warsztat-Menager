# -*- coding: utf-8 -*-
"""WMM -> Maszyny: szybkie akcje oparte wyłącznie na istniejącym modelu WM."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import unquote, urlparse


REVIEW_TYPES = (
    "Przegląd okresowy",
    "Serwis planowany",
    "Konserwacja",
    "Kalibracja",
    "Czyszczenie",
    "Inne",
)

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


def _close_current_period(
    machine: dict[str, Any],
    *,
    new_status: str,
    author: str,
    close_note: str,
) -> int:
    now = _now_iso()
    old_status = _normalize_status(machine.get("status"))
    current = machine.get("status_current")
    if not isinstance(current, dict):
        current = {
            "status": old_status,
            "label": _STATUS_LABELS.get(old_status, str(machine.get("status") or old_status)),
            "started_at": now,
            "changed_by": author,
            "note": "",
            "photos": [],
        }

    closed = dict(current)
    closed.setdefault("status", old_status)
    closed.setdefault("label", _STATUS_LABELS.get(old_status, old_status))
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

    normalized_new = _normalize_status(new_status)
    machine["status"] = normalized_new
    machine["status_current"] = {
        "status": normalized_new,
        "label": _STATUS_LABELS.get(normalized_new, normalized_new),
        "started_at": now,
        "changed_by": author,
        "note": close_note,
        "photos": [],
    }
    return int(closed.get("duration_minutes") or 0)


def _append_generic_history(
    impl: Any,
    machine: dict[str, Any],
    action: str,
    author: str,
    note: str,
) -> None:
    helper = getattr(impl, "_append_history", None)
    if callable(helper):
        helper(machine, action, author, note)


def start_quick_repair(
    impl: Any,
    machine_id: str,
    author: str,
    note: str = "",
) -> dict[str, Any]:
    """Ustaw istniejący status WM ``Awaria`` i rozpocznij pomiar czasu statusu."""

    actor = str(author or "WMM").strip() or "WMM"
    text = _wmm_text("Szybka naprawa — rozpoczęcie", note)

    def mutate(machine: dict[str, Any]) -> None:
        if _normalize_status(machine.get("status")) == "warn":
            raise RuntimeError("Maszyna ma już status Awaria. Zakończ bieżącą naprawę zamiast rozpoczynać następną.")
        _close_current_period(
            machine,
            new_status="warn",
            author=actor,
            close_note=text,
        )
        _append_generic_history(impl, machine, "WMM - rozpoczęcie naprawy", actor, text)

    return impl._update_machine(machine_id, mutate)


def finish_quick_repair(
    impl: Any,
    machine_id: str,
    author: str,
    note: str = "",
) -> tuple[dict[str, Any], int]:
    """Zamknij istniejący okres ``Awaria`` i przywróć istniejący status WM ``Sprawna``."""

    actor = str(author or "WMM").strip() or "WMM"
    text = _wmm_text("Szybka naprawa — zakończenie", note)
    result: dict[str, int] = {"duration": 0}

    def mutate(machine: dict[str, Any]) -> None:
        if _normalize_status(machine.get("status")) != "warn":
            raise RuntimeError("Maszyna nie ma aktywnego statusu Awaria.")
        result["duration"] = _close_current_period(
            machine,
            new_status="ok",
            author=actor,
            close_note=text,
        )
        _append_generic_history(impl, machine, "WMM - zakończenie naprawy", actor, text)

    updated = impl._update_machine(machine_id, mutate)
    return updated, int(result["duration"])


def _planned_date(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise RuntimeError("Wybierz planowaną datę przeglądu.")
    try:
        parsed = date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise RuntimeError("Planowana data ma nieprawidłowy format.") from exc
    return parsed.isoformat()


def add_planned_review(
    impl: Any,
    machine_id: str,
    author: str,
    *,
    review_type: str,
    planned_date: object,
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Dodaj zwykły ręczny wpis ``reviews`` zgodny z desktopowym WM."""

    kind = str(review_type or "").strip()
    if kind not in REVIEW_TYPES:
        raise RuntimeError("Wybierz typ przeglądu dostępny w Warsztat Menager.")
    plan = _planned_date(planned_date)
    actor = str(author or "WMM").strip() or "WMM"
    created: dict[str, Any] = {}

    def mutate(machine: dict[str, Any]) -> None:
        reviews = machine.get("reviews")
        if not isinstance(reviews, list):
            reviews = []

        base_id = "rev_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        existing_ids = {
            str(row.get("id") or "").strip()
            for row in reviews
            if isinstance(row, dict)
        }
        review_id = base_id
        suffix = 2
        while review_id in existing_ids:
            review_id = f"{base_id}_{suffix}"
            suffix += 1

        entry = {
            "id": review_id,
            "type": kind,
            "planned_date": plan,
            "status": "planned",
            "source": "manual",
            "suggested_workers": [],
            "description": _wmm_text("Dodano przegląd planowany", description),
            "completed_at": "",
            "completed_by": [],
            "result_note": "",
            "photos": [],
        }
        reviews.append(entry)
        machine["reviews"] = reviews
        created.update(entry)
        _append_generic_history(
            impl,
            machine,
            "WMM - dodano przegląd planowany",
            actor,
            f"{kind} • {plan}",
        )

    updated = impl._update_machine(machine_id, mutate)
    return updated, dict(created)


def install(impl: Any) -> None:
    """Dołącz wyłącznie mobilne skróty do istniejących danych Maszyn WM."""

    if getattr(impl, "_WMM_MACHINE_MOBILE_V1", False):
        return

    original_do_post = impl._WmmHandler.do_POST

    def machine_mobile_do_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        start_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/start", path)
        finish_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/finish", path)
        review_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/reviews", path)
        match = start_match or finish_match or review_match
        if not match:
            return original_do_post(self)

        payload = self._read_json()
        if not self._require_pairing_key():
            return None
        machine_id = unquote(match.group(1))
        try:
            if start_match:
                item = start_quick_repair(
                    impl,
                    machine_id,
                    self._author(),
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(200, {"ok": True, "item": item})
                return None
            if finish_match:
                item, duration = finish_quick_repair(
                    impl,
                    machine_id,
                    self._author(),
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(200, {"ok": True, "item": item, "duration_minutes": duration})
                return None

            item, review = add_planned_review(
                impl,
                machine_id,
                self._author(),
                review_type=str(payload.get("type") or payload.get("typ") or ""),
                planned_date=payload.get("planned_date") or payload.get("date"),
                description=str(payload.get("description") or payload.get("opis") or ""),
            )
            self._send(201, {"ok": True, "item": item, "review": review})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] szybka akcja Maszyny nieudana")
            self._send(500, {"ok": False, "error": f"Błąd zapisu Maszyny: {exc}"})
        return None

    impl._WmmHandler.do_POST = machine_mobile_do_post
    impl._WMM_MACHINE_MOBILE_V1 = True
