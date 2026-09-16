# -*- coding: utf-8 -*-
"""WMM -> Maszyny: istniejące przeglądy WM + obowiązkowy autor z sesji."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import unquote, urlparse

from services import wmm_machine_mobile as legacy


_DONE = {
    "done",
    "wykonany",
    "wykonane",
    "zrobione",
    "zamkniety",
    "zamknięty",
    "completed",
}
_CANCELLED = {"cancelled", "canceled", "anulowany", "anulowane"}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _wmm_note(actor: str, action: str, extra: object = "") -> str:
    suffix = str(extra or "").strip()
    base = f"[WMM] {actor} — {action}"
    return base + (f" — {suffix}" if suffix else "")


def _active_identity(handler: Any, impl: Any) -> tuple[str, str]:
    """Zwróć trwałe user_id i czytelny login wyłącznie z aktywnej sesji WMM."""

    session_id = str(handler.headers.get("X-WMM-Session") or "").strip()
    user = impl._touch_session(session_id) if session_id else None
    if not isinstance(user, dict):
        raise PermissionError(
            "Sesja użytkownika WMM wygasła. Zaloguj się ponownie, aby zapis miał właściwego autora."
        )
    actor = str(user.get("login") or user.get("name") or "").strip()
    user_id = str(user.get("user_id") or user.get("id") or "").strip()
    if not actor:
        raise PermissionError(
            "Nie udało się ustalić loginu użytkownika WMM. Zaloguj się ponownie."
        )
    if not user_id:
        raise PermissionError(
            "Nie udało się ustalić trwałego ID użytkownika WMM. Zaloguj się ponownie."
        )
    return user_id, actor


def _active_author(handler: Any, impl: Any) -> str:
    """Zgodność wsteczna: zwróć czytelny login z aktywnej sesji WMM."""

    return _active_identity(handler, impl)[1]


def _status_key(value: object) -> str:
    return str(value or "planned").strip().casefold()


def _combined_actionable_reviews(machine: dict[str, Any]) -> list[dict[str, Any]]:
    """Lista istniejących planów WM: ręczne reviews + cykliczne z harmonogramu."""

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
        status = _status_key(entry.get("status"))
        if status in _DONE or status in _CANCELLED:
            continue
        row = dict(entry)
        source = str(row.get("source") or "manual").strip().casefold() or "manual"
        row["source"] = source
        row["source_label"] = "Cykliczny" if source == "cycle" else "Ręczny / zaplanowany w WM"
        rows.append(row)
    return rows


def planned_reviews(impl: Any, machine_id: str) -> list[dict[str, Any]]:
    machine = impl._find_machine(machine_id)
    if not isinstance(machine, dict):
        raise RuntimeError("Nie znaleziono maszyny.")
    return _combined_actionable_reviews(machine)


def _find_display_entry(machine: dict[str, Any], review_id: str) -> dict[str, Any]:
    wanted = str(review_id or "").strip()
    if not wanted:
        raise RuntimeError("Nie wybrano zaplanowanego przeglądu.")
    for entry in _combined_actionable_reviews(machine):
        if str(entry.get("id") or "").strip() == wanted:
            return entry
    raise RuntimeError(
        "Ten zaplanowany przegląd nie jest już aktywny w WM. Odśwież listę."
    )


def _materialize_existing_review(
    machine: dict[str, Any],
    display_entry: dict[str, Any],
) -> dict[str, Any]:
    """Ręczny wpis już istnieje; tylko wirtualny wpis cykliczny materializuje desktopowy model."""

    wanted_id = str(display_entry.get("id") or "").strip()
    for review in legacy._machine_reviews(machine):
        if str(review.get("id") or "").strip() == wanted_id:
            return review

    source = str(display_entry.get("source") or "manual").strip().casefold()
    if source != "cycle":
        raise RuntimeError(
            "Zaplanowany przegląd ręczny nie istnieje już w danych maszyny WM. Odśwież listę."
        )
    return legacy._materialize_cycle_review(machine, display_entry)


def _start_planned_review(
    impl: Any,
    machine_id: str,
    review_id: str,
    actor: str,
    actor_user_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    result: dict[str, Any] = {}

    def mutate(machine: dict[str, Any]) -> None:
        display = _find_display_entry(machine, review_id)
        review = _materialize_existing_review(machine, display)
        status = _status_key(review.get("status"))
        if status == "in_progress":
            raise RuntimeError("Ten przegląd jest już rozpoczęty.")
        if status in _DONE:
            raise RuntimeError("Ten przegląd jest już wykonany.")

        review["status"] = "in_progress"
        review["started_at"] = _now_iso()
        review["started_by"] = actor
        if actor_user_id:
            review["started_by_user_id"] = actor_user_id
        note = _wmm_note(
            actor,
            "Rozpoczęto zaplanowany przegląd",
            f"plan: {review.get('planned_date') or review.get('date') or '—'}",
        )
        legacy._sync_review_to_disposition(
            machine,
            review,
            status="in_progress",
            actor=actor,
            note=note,
        )
        legacy._apply_wm_machine_status(machine, "alert", actor=actor, note=note)
        result.update(review)

    updated = impl._update_machine(machine_id, mutate)
    return updated, dict(result)


def _complete_planned_review(
    impl: Any,
    machine_id: str,
    review_id: str,
    actor: str,
    result_note: str = "",
    actor_user_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    result: dict[str, Any] = {}

    def mutate(machine: dict[str, Any]) -> None:
        display = _find_display_entry(machine, review_id)
        review = _materialize_existing_review(machine, display)
        status = _status_key(review.get("status"))
        if status in _DONE:
            raise RuntimeError("Ten przegląd jest już wykonany.")

        note = _wmm_note(actor, "Zaplanowany przegląd wykonany", result_note)
        review["status"] = "done"
        review["completed_at"] = _now_iso()
        review["completed_by"] = [actor]
        if actor_user_id:
            review["completed_by_user_ids"] = [actor_user_id]
        review["result_note"] = note
        legacy._sync_review_to_disposition(
            machine,
            review,
            status="done",
            actor=actor,
            note=note,
        )
        has_active_review = any(
            _status_key(item.get("status")) == "in_progress"
            for item in legacy._machine_reviews(machine)
        )
        if (
            legacy._normalize_status(machine.get("status")) == "alert"
            and not has_active_review
        ):
            legacy._apply_wm_machine_status(machine, "ok", actor=actor, note=note)
        result.update(review)

    updated = impl._update_machine(machine_id, mutate)
    return updated, dict(result)


def _start_quick_repair(
    impl: Any,
    machine_id: str,
    actor: str,
    note: str = "",
) -> dict[str, Any]:
    text = _wmm_note(actor, "Szybka naprawa — rozpoczęcie", note)

    def mutate(machine: dict[str, Any]) -> None:
        if legacy._normalize_status(machine.get("status")) == "warn":
            raise RuntimeError(
                "Maszyna ma już status Awaria. Zakończ bieżącą naprawę zamiast rozpoczynać następną."
            )
        legacy._begin_repair_period(machine, author=actor, note=text)

    return impl._update_machine(machine_id, mutate)


def _finish_quick_repair(
    impl: Any,
    machine_id: str,
    actor: str,
    note: str = "",
) -> tuple[dict[str, Any], int]:
    text = _wmm_note(actor, "Szybka naprawa — zakończenie", note)
    result = {"duration": 0}

    def mutate(machine: dict[str, Any]) -> None:
        if legacy._normalize_status(machine.get("status")) != "warn":
            raise RuntimeError("Maszyna nie ma aktywnego statusu Awaria.")
        result["duration"] = legacy._finish_repair_period(
            machine,
            author=actor,
            close_note=text,
        )

    updated = impl._update_machine(machine_id, mutate)
    return updated, int(result["duration"])


def install(impl: Any) -> None:
    if getattr(impl, "_WMM_MACHINE_MOBILE_V4", False):
        return

    original_do_get = impl._WmmHandler.do_GET
    original_do_post = impl._WmmHandler.do_POST

    def machine_mobile_v4_do_get(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        planned_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/planned-reviews", path)
        if not planned_match:
            return original_do_get(self)
        if not self._require_pairing_key():
            return None
        try:
            items = planned_reviews(impl, unquote(planned_match.group(1)))
            self._send(200, {"ok": True, "count": len(items), "items": items})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] odczyt zaplanowanych przeglądów nieudany")
            self._send(500, {"ok": False, "error": f"Błąd odczytu przeglądów: {exc}"})
        return None

    def machine_mobile_v4_do_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        repair_start = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/start", path)
        repair_finish = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/finish", path)
        planned_match = impl.re.fullmatch(
            r"/api/v1/machines/([^/]+)/(?:planned-reviews|cycle-reviews)/([^/]+)/(start|complete)",
            path,
        )
        match = repair_start or repair_finish or planned_match
        if not match:
            return original_do_post(self)

        payload = self._read_json()
        if not self._require_pairing_key():
            return None
        try:
            actor_user_id, actor = _active_identity(self, impl)
            if repair_start:
                item = _start_quick_repair(
                    impl,
                    unquote(repair_start.group(1)),
                    actor,
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(200, {"ok": True, "item": item, "author": actor, "author_user_id": actor_user_id})
                return None
            if repair_finish:
                item, duration = _finish_quick_repair(
                    impl,
                    unquote(repair_finish.group(1)),
                    actor,
                    str(payload.get("note") or payload.get("uwaga") or ""),
                )
                self._send(
                    200,
                    {
                        "ok": True,
                        "item": item,
                        "duration_minutes": duration,
                        "author": actor,
                        "author_user_id": actor_user_id,
                    },
                )
                return None

            machine_id = unquote(planned_match.group(1))
            review_id = unquote(planned_match.group(2))
            action = planned_match.group(3)
            if action == "start":
                item, review = _start_planned_review(
                    impl, machine_id, review_id, actor, actor_user_id
                )
            else:
                item, review = _complete_planned_review(
                    impl,
                    machine_id,
                    review_id,
                    actor,
                    str(payload.get("note") or payload.get("uwaga") or ""),
                    actor_user_id,
                )
            self._send(
                200,
                {
                    "ok": True,
                    "item": item,
                    "review": review,
                    "author": actor,
                    "author_user_id": actor_user_id,
                },
            )
        except PermissionError as exc:
            self._send(401, {"ok": False, "error": str(exc), "reauth": True})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] szybka akcja Maszyny v4 nieudana")
            self._send(500, {"ok": False, "error": f"Błąd zapisu Maszyny: {exc}"})
        return None

    impl._WmmHandler.do_GET = machine_mobile_v4_do_get
    impl._WmmHandler.do_POST = machine_mobile_v4_do_post
    impl._WMM_MACHINE_MOBILE_V4 = True
