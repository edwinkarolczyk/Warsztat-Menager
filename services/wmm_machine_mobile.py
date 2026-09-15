# -*- coding: utf-8 -*-
"""WMM -> Maszyny: szybka naprawa oparta wyłącznie na istniejącym modelu WM."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse


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


def _begin_repair_period(
    machine: dict[str, Any],
    *,
    author: str,
    note: str,
) -> None:
    """Rozpocznij Awarię bez dopisywania osobnego rekordu poprzedniego stanu.

    Szybka naprawa ma dawać w historii jeden okres Awarii, a nie parę
    technicznych wpisów Sprawna/Awaria dla jednego zdarzenia.
    """

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
    # Wymuszamy rzeczywisty status, zamiast ufać historycznemu/staremu status_current.
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
            raise RuntimeError("Maszyna ma już status Awaria. Zakończ bieżącą naprawę zamiast rozpoczynać następną.")
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


def install(impl: Any) -> None:
    """Dołącz mobilną szybką naprawę do istniejących danych Maszyn WM."""

    if getattr(impl, "_WMM_MACHINE_MOBILE_V2", False):
        return

    original_do_post = impl._WmmHandler.do_POST

    def machine_mobile_do_post(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        start_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/start", path)
        finish_match = impl.re.fullmatch(r"/api/v1/machines/([^/]+)/quick-repair/finish", path)
        match = start_match or finish_match
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

            item, duration = finish_quick_repair(
                impl,
                machine_id,
                self._author(),
                str(payload.get("note") or payload.get("uwaga") or ""),
            )
            self._send(200, {"ok": True, "item": item, "duration_minutes": duration})
        except RuntimeError as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            impl.logger.exception("[WMM API] szybka akcja Maszyny nieudana")
            self._send(500, {"ok": False, "error": f"Błąd zapisu Maszyny: {exc}"})
        return None

    impl._WmmHandler.do_POST = machine_mobile_do_post
    impl._WMM_MACHINE_MOBILE_V2 = True
