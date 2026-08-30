# version: 1.0
"""Agregaty dla zakładki Brygadzista w Profilu WM.

Moduł wyłącznie odczytuje istniejące dane WM i buduje jeden spójny snapshot
na potrzeby GUI. Nie zapisuje narzędzi, maszyn, zadań ani urlopów.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from core import root_paths
from services.profile_service import get_all_users, load_assign_orders, load_assign_tools
from wm_tools_helpers import iter_tools_json, tool_task_id

logger = logging.getLogger(__name__)

_DONE = {
    "zrobione", "done", "zamkniete", "zamknięte", "zamknieta", "zamknięta",
    "finished", "close", "closed", "completed", "wykonane", "wykonany", "wykonano",
}
_IN_PROGRESS = {
    "w toku", "w_toku", "in progress", "in_progress", "realizacja", "progress",
    "started", "rozpoczete", "rozpoczęte",
}
_URGENT = {"pilne", "pilny", "urgent", "overdue"}
_MACHINE_PROBLEM = {
    "warn", "warning", "awaria", "uszkodzona", "uszkodzone", "uszkodzony",
    "stop", "niesprawna", "niesprawne", "niesprawny",
}
_TOOL_PROBLEM_WORDS = ("napraw", "uszk", "awari", "niespraw", "ostrzen", "zagub")
_PERIOD_LABELS = {
    "today": "Dzisiaj",
    "7d": "7 dni",
    "30d": "30 dni",
    "month": "Ten miesiąc",
    "year": "Rok",
    "all": "Cały okres",
}


def period_labels() -> dict[str, str]:
    return dict(_PERIOD_LABELS)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return _text(value).casefold()


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except Exception:
            continue
    return None


def _period_bounds(period: str, today: date | None = None) -> tuple[date | None, date | None]:
    today = today or date.today()
    key = _norm(period)
    if key == "today":
        return today, today
    if key == "7d":
        return today - timedelta(days=6), today
    if key == "30d":
        return today - timedelta(days=29), today
    if key == "month":
        return today.replace(day=1), today
    if key == "year":
        return date(today.year, 1, 1), today
    return None, today


def _in_period(value: Any, start: date | None, end: date | None) -> bool:
    parsed = _parse_dt(value)
    if parsed is None:
        return False
    day = parsed.date()
    return not ((start is not None and day < start) or (end is not None and day > end))


def _read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _normalize_records(payload: Any, keys: Iterable[str]) -> list[dict]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            seq = payload.get(key)
            if isinstance(seq, list):
                return [dict(item) for item in seq if isinstance(item, dict)]
        values = [value for value in payload.values() if isinstance(value, dict)]
        if values:
            return [dict(item) for item in values]
    return []


def _display_name(user: dict) -> str:
    direct = _text(user.get("display_name") or user.get("nazwa") or user.get("name"))
    if direct:
        return direct
    full = " ".join(part for part in (_text(user.get("imie")), _text(user.get("nazwisko"))) if part)
    return full or _text(user.get("login")) or "—"


def _active_users() -> list[dict]:
    try:
        raw = get_all_users()
    except Exception as exc:
        logger.warning("[WM-DBG][FOREMAN] profiles read failed: %s", exc)
        raw = []
    if isinstance(raw, dict):
        raw = raw.get("users") or raw.get("profiles") or list(raw.values())
    users: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        login = _text(item.get("login"))
        if not login:
            continue
        role = _norm(item.get("rola") or item.get("role"))
        status = _norm(item.get("status"))
        if item.get("active") is False or status in {"nieaktywny", "zablokowany", "dezaktywowany"}:
            continue
        if role in {"guest", "gość", "gosc"}:
            continue
        row = dict(item)
        row["login"] = login
        users.append(row)
    users.sort(key=lambda row: (_display_name(row).casefold(), row["login"].casefold()))
    return users


def _leave_candidates() -> list[Path]:
    candidates = [
        root_paths.get_root_anchor() / "leaves.json",
        root_paths.get_data_root() / "leaves.json",
        root_paths.get_data_root() / "profile" / "leaves.json",
        Path.cwd() / "leaves.json",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.expanduser().resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _load_leaves() -> tuple[list[dict], str]:
    existing: list[tuple[float, Path]] = []
    for path in _leave_candidates():
        try:
            if path.is_file():
                existing.append((path.stat().st_mtime, path))
        except Exception:
            continue
    if existing:
        existing.sort(key=lambda item: item[0], reverse=True)
        path = existing[0][1]
        rows = _normalize_records(_read_json(path, []), ("leaves", "items", "entries"))
        return rows, str(path)
    try:
        from leaves import read_all
        rows = read_all()
        return [dict(row) for row in rows if isinstance(row, dict)], "leaves.read_all()"
    except Exception:
        return [], ""


def _user_leave_stats(user: dict, leaves: list[dict], year: int) -> dict[str, Any]:
    login = _norm(user.get("login"))
    used = l4 = nn = 0.0
    late = 0
    for row in leaves:
        if _norm(row.get("login")) != login or _text(row.get("date"))[:4] != str(year):
            continue
        kind = _norm(row.get("type"))
        try:
            qty = float(row.get("quantity_days") or 0.0)
        except Exception:
            qty = 0.0
        if kind == "urlop":
            used += qty
        elif kind == "l4":
            l4 += qty
        elif kind == "nn":
            nn += qty
        elif kind == "spoznienie":
            try:
                late += int(row.get("minutes") or 0)
            except Exception:
                pass
    ent = user.get("entitlements") if isinstance(user.get("entitlements"), dict) else {}
    try:
        limit = float((ent or {}).get("urlop_rocznie", 26) or 26)
    except Exception:
        limit = 26.0
    return {"limit": limit, "used": used, "remaining": limit - used, "l4": l4, "nn": nn, "late_minutes": late}


def _today_absences(leaves: list[dict], today: date) -> dict[str, str]:
    labels = {"urlop": "Urlop", "l4": "L4", "nn": "NN", "inny": "Nieobecny"}
    wanted = today.isoformat()
    result: dict[str, str] = {}
    for row in leaves:
        if _text(row.get("date"))[:10] != wanted:
            continue
        login = _norm(row.get("login"))
        kind = _norm(row.get("type"))
        if login and kind in labels:
            result[login] = labels[kind]
    return result


def _shift_for_login(login: str, today: date) -> str:
    try:
        from grafiki.shifts_schedule import _shift_times, _slot_for_mode, _user_mode, _week_idx
        if today.weekday() == 6:
            return "Wolne"
        mode = _user_mode(login)
        slot = _slot_for_mode(mode, _week_idx(today))
        if today.weekday() == 5:
            slot = "RANO"
        times = _shift_times()
        if slot == "RANO":
            return f"1 ({times['R_START'].strftime('%H:%M')}–{times['R_END'].strftime('%H:%M')})"
        return f"2 ({times['P_START'].strftime('%H:%M')}–{times['P_END'].strftime('%H:%M')})"
    except Exception:
        return "—"


def _task_done(task: dict) -> bool:
    return task.get("done") is True or _norm(task.get("status") or task.get("state")) in _DONE


def _task_actor(task: dict) -> str:
    for key in ("by", "done_by", "user", "wykonal", "wykonał", "closed_by", "finished_by", "zamknal", "zamknął"):
        value = _text(task.get(key))
        if value:
            return value
    return _text(task.get("assigned_to") or task.get("przypisane_do") or task.get("login")) if _task_done(task) else ""


def _task_assigned(task: dict) -> str:
    return _text(task.get("assigned_to") or task.get("przypisane_do") or task.get("login") or task.get("operator") or task.get("pracownik"))


def _task_done_at(task: dict) -> str:
    return _text(task.get("date_done") or task.get("ts_done") or task.get("done_at") or task.get("archived_at") or task.get("completed_at") or task.get("closed_at"))


def _task_deadline(task: dict) -> str:
    return _text(task.get("termin") or task.get("deadline") or task.get("due_date") or task.get("data_do") or task.get("data_plan"))


def _task_title(task: dict) -> str:
    return _text(task.get("tytul") or task.get("title") or task.get("nazwa") or task.get("opis")) or "Zadanie"


def _normalize_task(task: dict, *, kind: str, object_id: str, object_name: str, task_id: str, assigned_override: str = "") -> dict[str, Any]:
    assigned = assigned_override or _task_assigned(task)
    done = _task_done(task)
    status = _text(task.get("status") or task.get("state") or ("Zrobione" if done else "Nowe"))
    priority = _norm(task.get("priorytet") or task.get("priority"))
    return {
        "id": task_id,
        "title": _task_title(task),
        "kind": kind,
        "object_id": object_id,
        "object_name": object_name,
        "assigned": assigned,
        "done_by": _task_actor(task),
        "done": done,
        "status": status,
        "deadline": _task_deadline(task),
        "done_at": _task_done_at(task),
        "urgent": _norm(status) in _URGENT or priority in _URGENT,
        "in_progress": _norm(status) in _IN_PROGRESS,
    }


def _load_generic_tasks(assign_orders: dict[str, Any]) -> list[dict]:
    data_root = root_paths.get_data_root()
    candidates = [data_root / "zadania.json", data_root / "zlecenia.json", root_paths.path_dyspozycje()]
    try:
        candidates.extend(sorted(root_paths.path_orders_dir().glob("*.json")))
    except Exception:
        pass
    result: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for path in candidates:
        if not path.is_file():
            continue
        rows = _normalize_records(_read_json(path, []), ("zadania", "zlecenia", "orders", "items", "dyspozycje"))
        for row in rows:
            rid = _text(row.get("nr") or row.get("id") or row.get("kod"))
            title = _task_title(row)
            assigned = _task_assigned(row)
            if rid:
                assigned = _text(assign_orders.get(rid) or assign_orders.get(f"ZLEC-{rid}")) or assigned
            path_name = path.name.casefold()
            if "dyspozyc" in path_name:
                kind = _text(row.get("typ_dyspozycji")) or "dyspozycja"
            elif "zlec" in path_name or row.get("nr") is not None:
                kind = "zlecenie"
            else:
                kind = _text(row.get("typ")) or "zadanie"
            key = (kind, rid, title, assigned.casefold())
            if key in seen:
                continue
            seen.add(key)
            task_id = f"ZLEC-{rid}" if kind == "zlecenie" and rid else (rid or title)
            result.append(_normalize_task(row, kind=kind, object_id=rid, object_name=title if kind == "zlecenie" else "", task_id=task_id, assigned_override=assigned))
    return result


def _tool_is_problem(status: Any) -> bool:
    value = _norm(status)
    return bool(value and any(token in value for token in _TOOL_PROBLEM_WORDS))


def _tool_problem_events(doc: dict, start: date | None, end: date | None) -> list[dict]:
    history = doc.get("historia")
    if not isinstance(history, list):
        return []
    rows: list[dict] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        action = _norm(item.get("action") or item.get("typ"))
        target = item.get("na") or item.get("current") or item.get("status")
        if action and action not in {"status_changed", "zmiana statusu", "status"}:
            continue
        if not _tool_is_problem(target):
            continue
        ts = item.get("ts") or item.get("date") or item.get("created_at")
        if start is not None and not _in_period(ts, start, end):
            continue
        rows.append(dict(item))
    return rows


def _load_tool_data(assign_tools: dict[str, Any], start: date | None, end: date | None) -> tuple[list[dict], list[dict], dict[str, Counter], list[dict]]:
    all_tasks: list[dict] = []
    equipment: list[dict] = []
    worker_tools: dict[str, Counter] = defaultdict(Counter)
    current_alerts: list[dict] = []
    for path, doc in iter_tools_json():
        if not isinstance(doc, dict):
            continue
        nr = _text(doc.get("nr") or path.stem)
        name = _text(doc.get("nazwa") or doc.get("name")) or f"Narzędzie {nr}"
        status = _text(doc.get("status")) or "—"
        tasks = doc.get("zadania") if isinstance(doc.get("zadania"), list) else []
        done_period = 0
        for idx, raw_task in enumerate(tasks):
            if not isinstance(raw_task, dict):
                continue
            tid = tool_task_id(nr, idx)
            normalized = _normalize_task(raw_task, kind="narzedzie", object_id=nr, object_name=name, task_id=tid, assigned_override=_text(assign_tools.get(tid)))
            all_tasks.append(normalized)
            if normalized["done"] and (start is None or _in_period(normalized["done_at"], start, end)):
                if start is None or normalized["done_at"]:
                    done_period += 1
                    actor = _norm(normalized["done_by"])
                    if actor:
                        worker_tools[actor][f"{nr} {name}".strip()] += 1
        problem_events = _tool_problem_events(doc, start, end)
        parsed_dates = [_parse_dt(item.get("ts") or item.get("date") or item.get("created_at")) for item in problem_events]
        parsed_dates = [item for item in parsed_dates if item is not None]
        last_problem = max(parsed_dates).strftime("%d-%m-%y") if parsed_dates else "—"
        visits = doc.get("wizyty") if isinstance(doc.get("wizyty"), list) else []
        row = {
            "id": nr,
            "name": name,
            "status": status,
            "problems": len(problem_events),
            "done_tasks": done_period,
            "visits": len(visits),
            "last_problem": last_problem,
            "current_problem": _tool_is_problem(status),
        }
        equipment.append(row)
        if row["current_problem"]:
            current_alerts.append({"type": "Narzędzie", "object": f"{nr} — {name}", "info": f"Status: {status}"})
    equipment.sort(key=lambda row: (-int(row["problems"]), -int(row["done_tasks"]), row["id"]))
    return all_tasks, equipment, worker_tools, current_alerts


def _machine_records() -> list[dict]:
    return _normalize_records(_read_json(root_paths.path_machines(), []), ("maszyny", "machines", "items"))


def _machine_problem(status: Any) -> bool:
    return _norm(status) in _MACHINE_PROBLEM


def _duration_minutes(item: dict, start_bound: date | None = None) -> int:
    start_dt = _parse_dt(item.get("started_at"))
    end_dt = _parse_dt(item.get("ended_at") or item.get("closed_at"))
    if start_bound is not None and start_dt and start_dt.date() < start_bound:
        start_dt = datetime.combine(start_bound, datetime.min.time())
    if start_dt and end_dt:
        return max(0, int((end_dt - start_dt).total_seconds() // 60))
    try:
        value = int(float(item.get("duration_minutes") or 0))
    except Exception:
        value = 0
    return max(0, value)


def _as_people(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    raw = _text(value)
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()] if raw else []


def _load_machine_data(start: date | None, end: date | None) -> tuple[list[dict], dict[str, Counter], Counter, list[dict], list[dict]]:
    equipment: list[dict] = []
    worker_machines: dict[str, Counter] = defaultdict(Counter)
    worker_services: Counter = Counter()
    current_alerts: list[dict] = []
    upcoming: list[dict] = []
    today = date.today()
    for machine in _machine_records():
        mid = _text(machine.get("nr_ewid") or machine.get("nr") or machine.get("numer") or machine.get("id"))
        name = _text(machine.get("nazwa") or machine.get("name") or machine.get("typ")) or f"Maszyna {mid}"
        label = f"{mid} — {name}" if mid else name
        status = _text(machine.get("status")) or "—"
        issue_count = downtime = 0
        last_issue_dt: datetime | None = None
        history = machine.get("status_history") if isinstance(machine.get("status_history"), list) else []
        for item in history:
            if not isinstance(item, dict) or not _machine_problem(item.get("status") or item.get("label")):
                continue
            event_ts = item.get("started_at") or item.get("ended_at") or item.get("ts")
            if start is not None and not _in_period(event_ts, start, end):
                continue
            issue_count += 1
            downtime += _duration_minutes(item, start)
            parsed = _parse_dt(event_ts)
            if parsed and (last_issue_dt is None or parsed > last_issue_dt):
                last_issue_dt = parsed
        current = machine.get("status_current") if isinstance(machine.get("status_current"), dict) else {}
        current_status = current.get("status") or status
        if _machine_problem(current_status):
            started = current.get("started_at")
            if start is None or _in_period(started, start, end):
                issue_count += 1
            started_dt = _parse_dt(started)
            if started_dt:
                effective_start = started_dt
                if start is not None and effective_start.date() < start:
                    effective_start = datetime.combine(start, datetime.min.time())
                downtime += max(0, int((datetime.now() - effective_start).total_seconds() // 60))
                if last_issue_dt is None or started_dt > last_issue_dt:
                    last_issue_dt = started_dt
            current_alerts.append({"type": "Maszyna", "object": label, "info": f"Status: {current_status}"})
        service_count = 0
        reviews = machine.get("reviews") if isinstance(machine.get("reviews"), list) else []
        for review in reviews:
            if not isinstance(review, dict):
                continue
            completed_at = review.get("completed_at")
            done = bool(completed_at) or _norm(review.get("status")) in _DONE
            if done and (start is None or _in_period(completed_at, start, end)):
                if start is None or completed_at:
                    service_count += 1
                    for worker in _as_people(review.get("completed_by")):
                        key = _norm(worker)
                        if key:
                            worker_services[key] += 1
                            worker_machines[key][label] += 1
            if not done:
                planned = _parse_dt(review.get("planned_date") or review.get("date"))
                if planned:
                    delta = (planned.date() - today).days
                    if 0 <= delta <= 7:
                        upcoming.append({"type": "Przegląd", "object": label, "info": f"Termin za {delta} dni ({planned.strftime('%d-%m-%y')})"})
        equipment.append({
            "id": mid,
            "name": name,
            "status": status,
            "issues": issue_count,
            "downtime_minutes": downtime,
            "services": service_count,
            "last_issue": last_issue_dt.strftime("%d-%m-%y") if last_issue_dt else "—",
            "current_problem": _machine_problem(current_status),
        })
    equipment.sort(key=lambda row: (-int(row["issues"]), -int(row["downtime_minutes"]), row["id"]))
    return equipment, worker_machines, worker_services, current_alerts, upcoming


def _format_minutes(value: int) -> str:
    total = max(0, int(value or 0))
    hours, minutes = divmod(total, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _object_text(task: dict) -> str:
    kind = _norm(task.get("kind"))
    oid = _text(task.get("object_id"))
    name = _text(task.get("object_name"))
    if kind in {"narzedzie", "narzędzie"}:
        return f"Narzędzie {oid}" + (f" — {name}" if name else "")
    if kind == "zlecenie":
        return f"Zlecenie {oid}" if oid else (name or "Zlecenie")
    if "maszyn" in kind:
        return f"Maszyna {oid}" if oid else (name or "Maszyna")
    return oid or name or task.get("kind") or "—"


def _dedupe_tasks(tasks: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for task in tasks:
        key = (_norm(task.get("kind")), _text(task.get("id")), _norm(task.get("assigned")), _norm(task.get("title")))
        if key in seen:
            continue
        seen.add(key)
        out.append(task)
    return out


def build_snapshot(period: str = "month") -> dict[str, Any]:
    """Zbuduj spójny snapshot panelu brygadzisty."""
    today = date.today()
    start, end = _period_bounds(period, today)
    users = _active_users()
    user_by_login = {_norm(user["login"]): user for user in users}
    leaves, leaves_source = _load_leaves()
    absences = _today_absences(leaves, today)
    leave_stats = {key: _user_leave_stats(user, leaves, today.year) for key, user in user_by_login.items()}
    try:
        assign_tools = dict(load_assign_tools() or {})
    except Exception:
        assign_tools = {}
    try:
        assign_orders = dict(load_assign_orders() or {})
    except Exception:
        assign_orders = {}
    generic_tasks = _load_generic_tasks(assign_orders)
    tool_tasks, tool_rows, worker_tools, tool_alerts = _load_tool_data(assign_tools, start, end)
    all_tasks = _dedupe_tasks(generic_tasks + tool_tasks)
    machine_rows, worker_machines, worker_services, machine_alerts, upcoming = _load_machine_data(start, end)
    open_counts: Counter = Counter()
    in_progress_counts: Counter = Counter()
    urgent_counts: Counter = Counter()
    done_counts: Counter = Counter()
    current_work: dict[str, str] = {}
    normalized_tasks: list[dict] = []
    overdue_alerts: list[dict] = []
    for task in all_tasks:
        assigned_key = _norm(task.get("assigned"))
        actor_key = _norm(task.get("done_by"))
        done = bool(task.get("done"))
        if not done and assigned_key:
            open_counts[assigned_key] += 1
            if task.get("in_progress"):
                in_progress_counts[assigned_key] += 1
                current_work.setdefault(assigned_key, _object_text(task))
            if task.get("urgent"):
                urgent_counts[assigned_key] += 1
            deadline_dt = _parse_dt(task.get("deadline"))
            if deadline_dt and deadline_dt.date() < today:
                overdue_alerts.append({"type": "Zadanie", "object": _object_text(task), "info": f"Po terminie: {deadline_dt.strftime('%d-%m-%y')} • {task.get('title')}"})
        if done and actor_key:
            done_at = task.get("done_at")
            if start is None or _in_period(done_at, start, end):
                if start is None or done_at:
                    done_counts[actor_key] += 1
        row = dict(task)
        row["worker"] = task.get("done_by") if done else task.get("assigned")
        row["object"] = _object_text(task)
        normalized_tasks.append(row)
    team: list[dict] = []
    for key, user in user_by_login.items():
        shift = _shift_for_login(user["login"], today)
        status_today = absences.get(key, "Wolne" if shift == "Wolne" else "Dostępny")
        tools_counter = worker_tools.get(key, Counter())
        machines_counter = worker_machines.get(key, Counter())
        leave = leave_stats.get(key, {})
        team.append({
            "login": user["login"],
            "name": _display_name(user),
            "role": _text(user.get("rola") or user.get("role")) or "—",
            "shift": shift,
            "status": status_today,
            "open": open_counts[key],
            "in_progress": in_progress_counts[key],
            "urgent": urgent_counts[key],
            "done": done_counts[key],
            "tools": len(tools_counter),
            "machines": len(machines_counter),
            "services": worker_services[key],
            "leave_remaining": leave.get("remaining", 0),
            "current_work": current_work.get(key, "—"),
            "top_tools": tools_counter.most_common(3),
            "top_machines": machines_counter.most_common(3),
        })
    team.sort(key=lambda row: row["name"].casefold())
    leaves_rows = [{"login": user["login"], "name": _display_name(user), **leave_stats[key]} for key, user in user_by_login.items()]
    leaves_rows.sort(key=lambda row: row["name"].casefold())
    total_open = sum(1 for task in all_tasks if not task.get("done"))
    total_urgent = sum(1 for task in all_tasks if not task.get("done") and task.get("urgent"))
    available = sum(1 for row in team if row["status"] == "Dostępny")
    absent = len(team) - available
    attention = (machine_alerts + tool_alerts + overdue_alerts + upcoming)[:100]
    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "period": period,
        "period_label": _PERIOD_LABELS.get(period, period),
        "period_start": start.isoformat() if start else "",
        "period_end": end.isoformat() if end else "",
        "leaves_source": leaves_source,
        "summary": {
            "team": len(team),
            "available": available,
            "absent": absent,
            "open_tasks": total_open,
            "urgent_tasks": total_urgent,
            "machine_alerts": len(machine_alerts),
            "tool_alerts": len(tool_alerts),
            "done_period": sum(done_counts.values()),
            "services_period": sum(worker_services.values()),
            "machine_issues_period": sum(int(row["issues"]) for row in machine_rows),
            "tool_problems_period": sum(int(row["problems"]) for row in tool_rows),
        },
        "team": team,
        "leaves": leaves_rows,
        "tasks": normalized_tasks,
        "machines": machine_rows,
        "tools": tool_rows,
        "attention": attention,
        "format_minutes": _format_minutes,
    }


__all__ = ["build_snapshot", "period_labels"]
