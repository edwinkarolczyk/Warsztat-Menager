"""
attendance_utils.py

Minimalna ewidencja obecności na zmianach (plan / zalogował / potwierdzony / brak po 4h).

Dane: data/ewidencja_obecnosci.json
Struktura (minimalna, bez migracji profili):
{
  "YYYY-MM-DD": {
    "RANO": {
      "login": {
        "planned": true,
        "logged_ts": "ISO",
        "confirmed": false,
        "confirmed_by": "login",
        "confirmed_ts": "ISO"
      }
    },
    "POPO": { ... }
  }
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from typing import Any
from tkinter import ttk

from config_manager import ConfigManager  # [ROOT]

# [ROOT] Dane obecności muszą iść do folderu ROOT ustawionego w Ustawieniach
try:
    _cfg = ConfigManager()
    DATA_PATH = Path(_cfg.path_data("ewidencja_obecnosci.json"))
except Exception:
    # fallback awaryjny (gdy ConfigManager nie jest dostępny)
    DATA_PATH = Path("data") / "ewidencja_obecnosci.json"


def _safe_read_json(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return default
    return default


def _safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _leave_notice_state_path() -> Path:
    """Stan powiadomień urlopowych brygadzisty, obok leave_requests.json."""
    try:
        from core import root_paths

        return root_paths.get_root_anchor() / "brygadzista_leave_login_state.json"
    except Exception:
        return DATA_PATH.parent / "brygadzista_leave_login_state.json"


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except Exception:
        return None


def _new_pending_leave_requests_since_previous_login(bryg_login: str) -> list[dict]:
    """Zwróć nowe oczekujące wnioski i przesuń znacznik bieżącego logowania."""
    login_key = str(bryg_login or "").strip().casefold()
    if not login_key:
        return []

    state_path = _leave_notice_state_path()
    state = _safe_read_json(state_path, {})
    if not isinstance(state, dict):
        state = {}

    now = datetime.now().astimezone()
    previous = _parse_iso_datetime(state.get(login_key))
    new_requests: list[dict] = []

    try:
        from services.leave_workflow_service import read_requests

        pending = read_requests(status="pending")
    except Exception:
        pending = []

    # Pierwsze uruchomienie tylko ustala punkt startowy. Dzięki temu stare,
    # istniejące już wnioski nie są przedstawiane jako "nowe".
    if previous is not None:
        for row in pending:
            if not isinstance(row, dict):
                continue
            created_at = _parse_iso_datetime(row.get("created_at"))
            if created_at is None:
                continue
            try:
                if previous < created_at <= now:
                    new_requests.append(dict(row))
            except TypeError:
                continue

    state[login_key] = now.isoformat(timespec="seconds")
    try:
        _safe_write_json(state_path, state)
    except Exception:
        pass

    new_requests.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return new_requests


def _format_leave_request(row: dict, login_to_name: dict[str, str]) -> str:
    login = str(row.get("login") or "").strip()
    name = login_to_name.get(login.casefold(), login or "Pracownik")
    date_start = str(row.get("date_start") or "").strip()
    date_end = str(row.get("date_end") or "").strip()
    if date_start and date_end and date_start != date_end:
        date_text = f"{date_start} – {date_end}"
    else:
        date_text = date_start or date_end or "brak terminu"

    raw_days = row.get("quantity_days")
    try:
        days_value = float(raw_days)
        days_text = str(int(days_value)) if days_value.is_integer() else f"{days_value:g}"
    except (TypeError, ValueError):
        dates = row.get("dates")
        days_text = str(len(dates)) if isinstance(dates, list) else "?"

    return f"{name} — {date_text} — {days_text} dni"


def ensure_planned(date_ymd: str, slot: str, planned_logins: set[str]) -> None:
    """Zapisz plan (planned=True) dla loginów zaplanowanych na slot danego dnia."""
    if not date_ymd or slot not in ("RANO", "POPO"):
        return
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.setdefault(date_ymd, {})
    slot_map = day.setdefault(slot, {})
    changed = False
    for lg in planned_logins:
        login = str(lg or "").strip().lower()
        if not login:
            continue
        rec = slot_map.get(login)
        if not isinstance(rec, dict):
            slot_map[login] = {
                "planned": True,
                "logged_ts": "",
                "confirmed": False,
                "confirmed_by": "",
                "confirmed_ts": "",
            }
            changed = True
            continue
        if rec.get("planned") is not True:
            rec["planned"] = True
            changed = True
    if changed:
        _safe_write_json(DATA_PATH, doc)


def mark_login(date_ymd: str, slot: str, login: str, ts_iso: str) -> None:
    """Oznacz, że user się zalogował (=> żółty do czasu potwierdzenia)."""
    if not date_ymd or slot not in ("RANO", "POPO"):
        return
    login_n = str(login or "").strip().lower()
    if not login_n:
        return
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.setdefault(date_ymd, {})
    slot_map = day.setdefault(slot, {})
    rec = slot_map.get(login_n)
    if not isinstance(rec, dict):
        rec = {
            "planned": True,
            "logged_ts": "",
            "confirmed": False,
            "confirmed_by": "",
            "confirmed_ts": "",
            "reason": "",
        }
        slot_map[login_n] = rec
    rec["planned"] = True
    rec["logged_ts"] = str(ts_iso or "")
    if rec.get("confirmed") is True:
        # jeśli już potwierdzony, nie cofamy
        pass
    _safe_write_json(DATA_PATH, doc)


def confirm_login(
    date_ymd: str,
    slot: str,
    login: str,
    bryg_login: str,
    ts_iso: str,
) -> None:
    """Potwierdź obecność (=> zielony)."""
    if not date_ymd or slot not in ("RANO", "POPO"):
        return
    login_n = str(login or "").strip().lower()
    if not login_n:
        return
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.setdefault(date_ymd, {})
    slot_map = day.setdefault(slot, {})
    rec = slot_map.get(login_n)
    if not isinstance(rec, dict):
        rec = {
            "planned": True,
            "logged_ts": "",
            "confirmed": False,
            "confirmed_by": "",
            "confirmed_ts": "",
            "reason": "",
        }
        slot_map[login_n] = rec
    rec["planned"] = True
    rec["confirmed"] = True
    rec["confirmed_by"] = str(bryg_login or "")
    rec["confirmed_ts"] = str(ts_iso or "")
    _safe_write_json(DATA_PATH, doc)


def set_reason(
    date_ymd: str,
    slot: str,
    login: str,
    bryg_login: str,
    reason: str,
    ts_iso: str,
) -> None:
    """Ustaw powód nieobecności (L4/UR/UŻ/ŚW)."""
    if not date_ymd or slot not in ("RANO", "POPO"):
        return
    login_n = str(login or "").strip().lower()
    if not login_n:
        return
    r = str(reason or "").strip().upper()
    if r not in ("L4", "UR", "UŻ", "SW", "ŚW"):
        # akceptujemy też "SW" jako alias dla "ŚW"
        return
    if r == "SW":
        r = "ŚW"
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.setdefault(date_ymd, {})
    slot_map = day.setdefault(slot, {})
    rec = slot_map.get(login_n)
    if not isinstance(rec, dict):
        rec = {
            "planned": True,
            "logged_ts": "",
            "confirmed": False,
            "confirmed_by": "",
            "confirmed_ts": "",
            "reason": "",
        }
        slot_map[login_n] = rec
    rec["planned"] = True
    rec["reason"] = r
    # powód wygrywa z potwierdzeniem
    rec["confirmed"] = False
    rec["confirmed_by"] = str(bryg_login or "")
    rec["confirmed_ts"] = str(ts_iso or "")
    _safe_write_json(DATA_PATH, doc)


def _get_rec(date_ymd: str, slot: str, login: str) -> dict:
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.get(date_ymd) if isinstance(doc, dict) else None
    slot_map = day.get(slot) if isinstance(day, dict) else None
    rec = slot_map.get(login) if isinstance(slot_map, dict) else None
    return rec if isinstance(rec, dict) else {}


def status_for(
    date_ymd: str,
    slot: str,
    login: str,
    shift_start: datetime,
    now: datetime,
    grace_hours: int = 4,
) -> str:
    """
    Zwraca: PLANNED / LOGGED / CONFIRMED / EXCUSED / OVERDUE
    """
    login_n = str(login or "").strip().lower()
    rec = _get_rec(date_ymd, slot, login_n)
    if rec.get("reason"):
        return "EXCUSED"
    if rec.get("confirmed") is True:
        return "CONFIRMED"
    if rec.get("logged_ts"):
        return "LOGGED"
    # brak logowania
    try:
        if now >= (shift_start + timedelta(hours=int(grace_hours))):
            return "OVERDUE"
    except Exception:
        pass
    return "PLANNED"


@dataclass
class Digest:
    pending_confirm: list[str]
    overdue_missing: list[str]


def digest_for(
    date_ymd: str,
    slot: str,
    planned_logins: set[str],
    shift_start: datetime,
    now: datetime,
) -> Digest:
    pending: list[str] = []
    overdue: list[str] = []
    for lg in sorted(planned_logins):
        st = status_for(
            date_ymd,
            slot,
            lg,
            shift_start=shift_start,
            now=now,
            grace_hours=4,
        )
        if st == "LOGGED":
            pending.append(lg)
        elif st == "OVERDUE":
            overdue.append(lg)
        else:
            # EXCUSED/CONFIRMED/PLANNED ignorujemy tutaj
            pass
    return Digest(pending_confirm=pending, overdue_missing=overdue)


def open_brygadzista_modal(
    owner: tk.Misc,
    *,
    title: str,
    date_ymd: str,
    slot: str,
    planned_logins: set[str],
    login_to_name: dict[str, str],
    shift_start: datetime,
    now: datetime,
    bryg_login: str,
) -> None:
    """
    Okno brygadzisty: obecność oraz informacja o nowych wnioskach urlopowych.
    Potwierdzenie obecności ustawia zielony status. Wnioski są tu tylko do odczytu.
    """
    dg = digest_for(date_ymd, slot, planned_logins, shift_start=shift_start, now=now)
    new_leave_requests = _new_pending_leave_requests_since_previous_login(bryg_login)
    if not dg.pending_confirm and not dg.overdue_missing and not new_leave_requests:
        return

    win = tk.Toplevel(owner)
    win.title(title)
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass
    win.grab_set()

    wrap = ttk.Frame(win, padding=12)
    wrap.pack(fill="both", expand=True)

    header = f"Ewidencja obecności: {date_ymd} / {slot}"
    ttk.Label(wrap, text=header).pack(anchor="w", pady=(0, 8))

    if new_leave_requests:
        leave_box = ttk.LabelFrame(
            wrap,
            text=(
                "Nowe wnioski urlopowe od poprzedniego logowania "
                f"({len(new_leave_requests)})"
            ),
            padding=8,
        )
        leave_box.pack(fill="x", pady=(0, 10))
        lb_leave = tk.Listbox(
            leave_box,
            height=min(6, max(1, len(new_leave_requests))),
        )
        lb_leave.pack(fill="x", expand=False)
        for request in new_leave_requests:
            lb_leave.insert("end", _format_leave_request(request, login_to_name))
        ttk.Label(
            leave_box,
            text="Decyzję podejmiesz w: Profil → Brygadzista → Urlopy.",
        ).pack(anchor="w", pady=(6, 0))

    cols = ttk.Frame(wrap)
    cols.pack(fill="both", expand=True)
    left = ttk.Frame(cols)
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right = ttk.Frame(cols)
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    ttk.Label(left, text="🟡 Do potwierdzenia (zalogowali się):").pack(anchor="w")
    lb_pending = tk.Listbox(left, height=10)
    lb_pending.pack(fill="both", expand=True, pady=(4, 8))

    ttk.Label(right, text="🔴 Brak logowania po 4h:").pack(anchor="w")
    lb_over = tk.Listbox(right, height=10)
    lb_over.pack(fill="both", expand=True, pady=(4, 8))

    ttk.Label(right, text="🔵 Usprawiedliwieni (L4/UR/UŻ/ŚW):").pack(anchor="w")
    lb_excused = tk.Listbox(right, height=6)
    lb_excused.pack(fill="both", expand=False, pady=(4, 8))

    def _extract_login(item_text: str) -> str:
        # format: "Imię Nazwisko  (@login)"
        if not item_text:
            return ""
        if "(@" in item_text:
            try:
                return item_text.split("(@", 1)[1].split(")", 1)[0].strip().lower()
            except Exception:
                return ""
        return ""

    def _selected_login() -> str:
        # najpierw pending, potem overdue, potem excused
        try:
            if lb_pending.curselection():
                return _extract_login(lb_pending.get(lb_pending.curselection()[0]))
        except Exception:
            pass
        try:
            if lb_over.curselection():
                return _extract_login(lb_over.get(lb_over.curselection()[0]))
        except Exception:
            pass
        try:
            if lb_excused.curselection():
                return _extract_login(lb_excused.get(lb_excused.curselection()[0]))
        except Exception:
            pass
        return ""

    def _fill():
        lb_pending.delete(0, "end")
        for lg in dg.pending_confirm:
            lb_pending.insert("end", f"{login_to_name.get(lg, lg)}  (@{lg})")
        lb_over.delete(0, "end")
        for lg in dg.overdue_missing:
            lb_over.insert("end", f"{login_to_name.get(lg, lg)}  (@{lg})")

        # excused: z pliku ewidencji, tylko dla planu
        lb_excused.delete(0, "end")
        for lg in sorted(planned_logins):
            try:
                rec = _get_rec(date_ymd, slot, str(lg).strip().lower())
                r = (rec.get("reason") or "").strip()
                if r:
                    lb_excused.insert(
                        "end", f"{login_to_name.get(lg, lg)}  ({r})  (@{lg})"
                    )
            except Exception:
                continue

    def _refresh():
        nonlocal dg
        dg = digest_for(
            date_ymd,
            slot,
            planned_logins,
            shift_start=shift_start,
            now=datetime.now(),
        )
        _fill()

    def _confirm_selected():
        lg = _selected_login()
        if not lg:
            return
        ts = datetime.now().isoformat(timespec="seconds")
        confirm_login(date_ymd, slot, lg, bryg_login=bryg_login, ts_iso=ts)
        _refresh()

    def _confirm_all():
        ts = datetime.now().isoformat(timespec="seconds")
        for lg in list(dg.pending_confirm):
            confirm_login(date_ymd, slot, lg, bryg_login=bryg_login, ts_iso=ts)
        _refresh()

    def _set_reason(reason: str):
        lg = _selected_login()
        if not lg:
            return
        ts = datetime.now().isoformat(timespec="seconds")
        set_reason(
            date_ymd, slot, lg, bryg_login=bryg_login, reason=reason, ts_iso=ts
        )
        _refresh()

    btns = ttk.Frame(wrap)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(
        btns, text="Potwierdź zaznaczonego (🟢)", command=_confirm_selected
    ).pack(side="left")
    ttk.Button(btns, text="Potwierdź wszystkich (🟢)", command=_confirm_all).pack(
        side="left", padx=(8, 0)
    )

    ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=10)

    ttk.Button(btns, text="L4", command=lambda: _set_reason("L4")).pack(side="left")
    ttk.Button(btns, text="UR", command=lambda: _set_reason("UR")).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(btns, text="UŻ", command=lambda: _set_reason("UŻ")).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(btns, text="ŚW", command=lambda: _set_reason("ŚW")).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(btns, text="Zamknij", command=win.destroy).pack(side="right")

    # dwuklik na liście "Do potwierdzenia" = potwierdź zaznaczonego
    try:
        lb_pending.bind("<Double-Button-1>", lambda _e: _confirm_selected())
    except Exception:
        pass

    _fill()


def add_alert(
    date_ymd: str,
    *,
    kind: str,
    login: str,
    msg: str,
    meta: dict[str, Any] | None = None,
    ts_iso: str = "",
) -> None:
    """
    Zapis alertu dziennego (np. logowanie poza zmianą, brak planu).
    Struktura:
      doc[date]["_alerts"] = [
        {
          "kind": "...",
          "login": "...",
          "msg": "...",
          "ts": "...",
          "meta": {...}
        }
      ]
    """
    if not date_ymd:
        return
    login_n = str(login or "").strip().lower()
    if not login_n:
        return

    doc = _safe_read_json(DATA_PATH, {})
    day = doc.setdefault(date_ymd, {})
    alerts = day.setdefault("_alerts", [])

    if not isinstance(alerts, list):
        alerts = []
        day["_alerts"] = alerts

    alerts.append(
        {
            "kind": str(kind or "").strip(),
            "login": login_n,
            "msg": str(msg or "").strip(),
            "ts": str(ts_iso or ""),
            "meta": meta or {},
        }
    )

    _safe_write_json(DATA_PATH, doc)


def get_alerts(date_ymd: str) -> list[dict[str, Any]]:
    """Zwróć alerty dzienne (jeśli są)."""
    doc = _safe_read_json(DATA_PATH, {})
    day = doc.get(date_ymd) if isinstance(doc, dict) else None
    alerts = day.get("_alerts") if isinstance(day, dict) else None
    return alerts if isinstance(alerts, list) else []
