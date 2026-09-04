# version: 1.0
"""Podpina neutralny model płatnych dni do Obecności/Urlopów.

Nie liczy wypłat. Uzupełnia jedynie rekordy o kod dnia, procent płatności
oraz ekwiwalent płatnego dnia. Dni nierozstrzygnięte pozostają bez procentu.
"""
from __future__ import annotations

import uuid
from typing import Any, Iterable

from services import day_pay_service

_INSTALLED = False


def _decorate_attendance_module() -> None:
    from services import attendance_service as att

    if getattr(att, "_wm_day_pay_seed", False):
        return

    original_mark_login = att.mark_login
    original_confirm_login = att.confirm_login
    original_set_reason = att.set_reason
    original_set_manual_day = att.set_manual_day
    original_month_records = att.month_records
    original_summary = att.summary_for_month

    def _decorate_stored(date_ymd: str, login: str, *, reason: str | None = None,
                         manual_value: float | None = None) -> None:
        try:
            doc = att._read(att.data_path(), {})
        except Exception:
            return
        if not isinstance(doc, dict):
            return
        day = doc.get(str(date_ymd), {})
        if not isinstance(day, dict):
            return
        key = str(login or "").strip().casefold()
        changed = False
        for slot in (att.RANO, att.POPO):
            slot_map = day.get(slot)
            if not isinstance(slot_map, dict):
                continue
            rec = slot_map.get(key)
            if not isinstance(rec, dict):
                continue
            if reason:
                code = day_pay_service.normalize_code(reason)
                day_pay_service.apply_to_record(rec, code, pay_day_value=1.0)
            elif manual_value is not None:
                if manual_value > 0:
                    day_pay_service.apply_to_record(rec, "PRACA", pay_day_value=float(manual_value))
                else:
                    day_pay_service.mark_pending(rec)
            elif rec.get("reason"):
                day_pay_service.apply_to_record(rec, rec.get("reason"), pay_day_value=1.0)
            elif str(rec.get("status") or "") == att.STATUS_PRESENT and rec.get("confirmed"):
                day_pay_service.apply_to_record(
                    rec,
                    "PRACA",
                    pay_day_value=float(rec.get("day_value") or 1.0),
                )
            elif rec.get("approval_required"):
                day_pay_service.mark_pending(rec)
            else:
                continue
            changed = True
        if changed:
            try:
                att._write(att.data_path(), doc)
            except Exception:
                pass

    def mark_login(date_ymd: str, slot: str, login: str, ts_iso: str) -> None:
        original_mark_login(date_ymd, slot, login, ts_iso)
        _decorate_stored(date_ymd, login)

    def confirm_login(date_ymd: str, slot: str, login: str, bryg_login: str, ts_iso: str) -> None:
        original_confirm_login(date_ymd, slot, login, bryg_login, ts_iso)
        _decorate_stored(date_ymd, login)

    def set_reason(date_ymd: str, slot: str, login: str, bryg_login: str, reason: str, ts_iso: str) -> None:
        original_set_reason(date_ymd, slot, login, bryg_login, reason, ts_iso)
        _decorate_stored(date_ymd, login, reason=reason)

    def set_manual_day(date_ymd: str, slot: str, login: str, value: float, actor: str,
                       note: str = "") -> dict:
        row = original_set_manual_day(date_ymd, slot, login, value, actor, note)
        _decorate_stored(date_ymd, login, manual_value=float(value))
        try:
            rows = month_records(login, int(date_ymd[:4]), int(date_ymd[5:7]))
            for item in rows:
                if item.get("date") == date_ymd and item.get("slot") == slot:
                    return dict(item)
        except Exception:
            pass
        return row

    def _decorate_row(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        if item.get("pay_code") and (item.get("pay_percent") is not None or item.get("payroll_pending")):
            return item
        reason = str(item.get("reason") or "").strip()
        if reason:
            return day_pay_service.apply_to_record(item, reason, pay_day_value=1.0)
        status = str(item.get("status") or "")
        if status == att.STATUS_PRESENT and item.get("confirmed"):
            return day_pay_service.apply_to_record(
                item,
                "PRACA",
                pay_day_value=float(item.get("day_value") or 0.0),
            )
        if status in {att.STATUS_MISSING, att.STATUS_PENDING_LATE, att.STATUS_SATURDAY} or item.get("approval_required"):
            return day_pay_service.mark_pending(item)
        # Przyszły zaplanowany dzień nie jest jeszcze pozycją płacową.
        item.setdefault("payroll_pending", False)
        return item

    def month_records(login: str, year: int, month: int, *, now=None) -> list[dict]:
        return [_decorate_row(row) for row in original_month_records(login, year, month, now=now)]

    def summary_for_month(login: str, year: int, month: int, *, now=None) -> dict[str, float]:
        out = dict(original_summary(login, year, month, now=now))
        pay_equivalent = 0.0
        force_majeure = 0.0
        unpaid = 0.0
        payroll_pending = 0.0
        for row in month_records(login, year, month, now=now):
            if row.get("payroll_pending"):
                payroll_pending += 1.0
                continue
            code = day_pay_service.normalize_code(row.get("pay_code"))
            eq = row.get("pay_equivalent_days")
            if eq is not None:
                try:
                    pay_equivalent += float(eq)
                except Exception:
                    pass
            if code == "ŚW":
                force_majeure += float(row.get("pay_day_value") or 0.0)
            if code in {"NN", "UB"}:
                unpaid += float(row.get("pay_day_value") or 0.0)
        out.update({
            "pay_equivalent_days": pay_equivalent,
            "force_majeure": force_majeure,
            "unpaid_days": unpaid,
            "payroll_pending": payroll_pending,
        })
        return out

    att.mark_login = mark_login
    att.confirm_login = confirm_login
    att.set_reason = set_reason
    att.set_manual_day = set_manual_day
    att.month_records = month_records
    att.summary_for_month = summary_for_month
    att._wm_day_pay_seed = True


def _add_leave_kind(login: str, dates: Iterable, actor_login: str, note: str,
                    *, type_name: str, reason_code: str, pay_percent: float) -> int:
    from services import leave_workflow_service as lw

    actor = lw._require_foreman(actor_login)
    login = str(login or "").strip()
    if not login:
        raise ValueError("Wybierz pracownika.")
    selected = lw._normalize_dates(dates)
    rows = lw.read_leaves()
    created = lw._utc_now()
    token = uuid.uuid4().hex[-10:]
    comp = day_pay_service.compensation(reason_code, pay_day_value=1.0, pay_percent=pay_percent)
    for day in selected:
        if any(lw._same_day(row, login, day) for row in rows):
            raise ValueError(f"Dzień {day} ma już wpis nieobecności.")
        row = {
            "id": f"leave_{day}_{login}_{type_name}_{token}",
            "login": login,
            "type": type_name,
            "date": day,
            "shift": None,
            "quantity_days": 1.0,
            "minutes": 0,
            "approved_by": actor,
            "created_at": created,
            "note": str(note or "").strip(),
            "entered_by": actor,
        }
        row.update(comp)
        rows.append(row)
    lw._write_json(lw.leaves_path(), rows)
    lw._sync_attendance_reason(login, selected, actor, reason_code)
    return len(selected)


def _decorate_leave_workflow() -> None:
    from services import leave_workflow_service as lw

    if getattr(lw, "_wm_day_pay_seed", False):
        return

    original_approve = lw.approve_request
    original_add_l4 = lw.add_l4
    original_add_nn = lw.add_nn

    def _decorate_leaves(login: str, dates: Iterable[str], code: str, percent: float | None = None) -> None:
        rows = lw.read_leaves()
        wanted = {str(day)[:10] for day in dates}
        changed = False
        for row in rows:
            if str(row.get("login") or "").strip().casefold() != str(login).strip().casefold():
                continue
            if str(row.get("date") or "")[:10] not in wanted:
                continue
            if row.get("pay_code"):
                continue
            row.update(day_pay_service.compensation(code, pay_day_value=float(row.get("quantity_days") or 1.0), pay_percent=percent))
            changed = True
        if changed:
            lw._write_json(lw.leaves_path(), rows)

    def approve_request(request_id: str, actor_login: str, *, allow_over_balance: bool = False) -> dict:
        result = original_approve(request_id, actor_login, allow_over_balance=allow_over_balance)
        _decorate_leaves(str(result.get("login") or ""), result.get("dates") or [], "UR", 100.0)
        return result

    def add_l4(login: str, dates: Iterable, actor_login: str, note: str = "") -> int:
        selected = [str(day)[:10] for day in dates]
        count = original_add_l4(login, selected, actor_login, note)
        _decorate_leaves(login, selected, "L4", None)
        return count

    def add_nn(login: str, dates: Iterable, actor_login: str, note: str = "") -> int:
        selected = [str(day)[:10] for day in dates]
        count = original_add_nn(login, selected, actor_login, note)
        _decorate_leaves(login, selected, "NN", 0.0)
        return count

    def add_force_majeure(login: str, dates: Iterable, actor_login: str, note: str = "",
                          pay_percent: float = 50.0) -> int:
        return _add_leave_kind(
            login,
            dates,
            actor_login,
            note,
            type_name="sila_wyzsza",
            reason_code="ŚW",
            pay_percent=pay_percent,
        )

    def add_unpaid_leave(login: str, dates: Iterable, actor_login: str, note: str = "") -> int:
        return _add_leave_kind(
            login,
            dates,
            actor_login,
            note,
            type_name="urlop_bezplatny",
            reason_code="UB",
            pay_percent=0.0,
        )

    lw.approve_request = approve_request
    lw.add_l4 = add_l4
    lw.add_nn = add_nn
    lw.add_force_majeure = add_force_majeure
    lw.add_unpaid_leave = add_unpaid_leave
    lw._wm_day_pay_seed = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _decorate_attendance_module()
    _decorate_leave_workflow()
    _INSTALLED = True


__all__ = ["install"]
