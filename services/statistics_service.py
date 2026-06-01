# version: 1.0
"""Read-only service collecting statistics from Warsztat Menager data files.

Etap 1 modułu Statystyki:
- bez GUI,
- bez zapisu danych,
- bez OpenAI/Jarvisa,
- odpornie na brakujące albo uszkodzone JSON-y.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


_TOOL_CONFIG_FILES = {
    "statusy_narzedzi.json",
    "typy_narzedzi.json",
    "szablony_zadan.json",
}


def _problem(
    problems: list[dict[str, Any]],
    *,
    level: str,
    code: str,
    message: str,
    path: str | Path | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "level": level,
        "code": code,
        "message": message,
    }
    if path is not None:
        item["path"] = str(path)
    if extra:
        item["extra"] = dict(extra)
    problems.append(item)


def _data_root() -> Path:
    """Return active WM data root using ConfigManager when possible."""

    try:
        from config_manager import ConfigManager

        cfg = ConfigManager()
        candidate = cfg.path_data()
        if candidate:
            return Path(candidate)
    except Exception:
        pass

    return Path("data")


def _load_json_safe(path: Path, problems: list[dict[str, Any]]) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        _problem(
            problems,
            level="warning",
            code="missing_file",
            message="Nie znaleziono pliku JSON.",
            path=path,
        )
    except json.JSONDecodeError as exc:
        _problem(
            problems,
            level="error",
            code="broken_json",
            message=f"Uszkodzony JSON: {exc}",
            path=path,
        )
    except Exception as exc:
        _problem(
            problems,
            level="error",
            code="read_error",
            message=f"Nie udało się odczytać JSON: {exc}",
            path=path,
        )
    return None


def _as_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "rows", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_key(value: Any, default: str = "nieznany") -> str:
    text = _norm_text(value).lower()
    return text or default


def _tool_id(tool: Mapping[str, Any]) -> str:
    for key in ("id", "nr", "numer", "kod"):
        value = _norm_text(tool.get(key))
        if value:
            return value
    return ""


def _tool_name(tool: Mapping[str, Any]) -> str:
    return _norm_text(tool.get("nazwa") or tool.get("name"))


def _tool_type(tool: Mapping[str, Any]) -> str:
    return _norm_key(tool.get("typ") or tool.get("typ_narzedzia") or tool.get("type"))


def _tool_status(tool: Mapping[str, Any]) -> str:
    value = tool.get("status") or tool.get("stan") or tool.get("status_aktualny")
    if isinstance(value, Mapping):
        value = value.get("nazwa") or value.get("name")
    return _norm_key(value)


def _tool_tasks(tool: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = tool.get("zadania") or tool.get("tasks") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _tool_visits(tool: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = tool.get("wizyty") or tool.get("visits") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _task_title(task: Mapping[str, Any]) -> str:
    return _norm_text(task.get("tytul") or task.get("title") or task.get("nazwa"))


def _task_assigned_to(task: Mapping[str, Any]) -> str:
    return _norm_text(
        task.get("assigned_to")
        or task.get("przypisane")
        or task.get("do_kogo")
        or task.get("osoba")
        or task.get("user")
    )


def _task_done_by(task: Mapping[str, Any]) -> str:
    return _norm_text(
        task.get("done_by")
        or task.get("by")
        or task.get("wykonal")
        or task.get("wykonał")
    )


def _task_done(task: Mapping[str, Any]) -> bool:
    return bool(task.get("done") is True)


def _visit_start(visit: Mapping[str, Any]) -> str:
    return _norm_text(visit.get("start") or visit.get("ts") or visit.get("start_ts"))


def _visit_end(visit: Mapping[str, Any]) -> str:
    return _norm_text(
        visit.get("end")
        or visit.get("koniec")
        or visit.get("stop")
        or visit.get("end_ts")
        or visit.get("closed_at")
    )


def _parse_dt(value: Any) -> datetime | None:
    text = _norm_text(value)
    if not text:
        return None
    if "T" not in text and " " in text:
        text = text.replace(" ", "T", 1)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _iter_tool_files(data_root: Path, problems: list[dict[str, Any]]) -> Iterable[Path]:
    tools_dir = data_root / "narzedzia"
    if not tools_dir.is_dir():
        _problem(
            problems,
            level="warning",
            code="missing_tools_dir",
            message="Brak katalogu narzędzi.",
            path=tools_dir,
        )
        return []

    return sorted(
        path
        for path in tools_dir.glob("*.json")
        if path.name not in _TOOL_CONFIG_FILES and not path.name.startswith("_")
    )


def _collect_tools(
    data_root: Path,
    problems: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    ids: list[str] = []
    per_status: Counter[str] = Counter()
    per_type: Counter[str] = Counter()
    missing_id_count = 0
    missing_status_count = 0
    without_tasks_count = 0
    with_open_tasks_count = 0
    in_progress_count = 0
    idle_count = 0

    idle_statuses = {"ok", "sprawne", "wolne", "dostepne", "dostępne", "idle", "available"}

    for path in _iter_tool_files(data_root, problems):
        payload = _load_json_safe(path, problems)
        if not isinstance(payload, dict):
            continue

        tool = dict(payload)
        tool.setdefault("_source", str(path))
        tool_id = _tool_id(tool) or path.stem
        if not _tool_id(tool):
            missing_id_count += 1
            _problem(
                problems,
                level="warning",
                code="tool_missing_id",
                message="Narzędzie bez numeru/id.",
                path=path,
            )

        status = _tool_status(tool)
        typ = _tool_type(tool)
        tasks = _tool_tasks(tool)
        open_tasks = sum(1 for task in tasks if not _task_done(task))

        if status == "nieznany":
            missing_status_count += 1
            _problem(
                problems,
                level="warning",
                code="tool_missing_status",
                message="Narzędzie bez statusu.",
                path=path,
                extra={"tool_id": tool_id},
            )

        if not tasks:
            without_tasks_count += 1
        if open_tasks:
            with_open_tasks_count += 1

        if status in idle_statuses:
            idle_count += 1
        else:
            in_progress_count += 1

        ids.append(tool_id)
        per_status[status] += 1
        per_type[typ] += 1
        tools.append(tool)

    duplicates = sorted(key for key, value in Counter(ids).items() if key and value > 1)
    for duplicate in duplicates:
        _problem(
            problems,
            level="warning",
            code="duplicate_tool_id",
            message="Duplikat numeru/id narzędzia.",
            extra={"tool_id": duplicate},
        )

    summary = {
        "count": len(tools),
        "per_status": dict(per_status),
        "per_type": dict(per_type),
        "in_progress_count": in_progress_count,
        "idle_count": idle_count,
        "with_open_tasks_count": with_open_tasks_count,
        "without_tasks_count": without_tasks_count,
        "duplicate_ids": duplicates,
        "missing_id_count": missing_id_count,
        "missing_status_count": missing_status_count,
    }
    return tools, summary


def _collect_tasks_from_tools(
    tools: list[dict[str, Any]],
    problems: list[dict[str, Any]],
) -> dict[str, Any]:
    count = 0
    done_count = 0
    open_count = 0
    missing_title_count = 0
    per_assigned_to: Counter[str] = Counter()
    per_done_by: Counter[str] = Counter()
    tools_with_open_tasks: dict[str, int] = {}

    for tool in tools:
        tool_id = _tool_id(tool) or _norm_text(tool.get("_source")) or "?"
        open_for_tool = 0

        for task in _tool_tasks(tool):
            count += 1
            is_done = _task_done(task)
            if is_done:
                done_count += 1
            else:
                open_count += 1
                open_for_tool += 1

            assigned = _task_assigned_to(task)
            done_by = _task_done_by(task)
            if assigned:
                per_assigned_to[assigned] += 1
            if done_by:
                per_done_by[done_by] += 1

            if not _task_title(task):
                missing_title_count += 1
                _problem(
                    problems,
                    level="warning",
                    code="task_missing_title",
                    message="Zadanie bez tytułu.",
                    extra={"tool_id": tool_id},
                )

        if open_for_tool:
            tools_with_open_tasks[tool_id] = open_for_tool

    done_pct = int(round((done_count / count) * 100)) if count else 0

    return {
        "count": count,
        "done_count": done_count,
        "open_count": open_count,
        "done_pct": done_pct,
        "per_assigned_to": dict(per_assigned_to),
        "per_done_by": dict(per_done_by),
        "missing_title_count": missing_title_count,
        "tools_with_open_tasks": tools_with_open_tasks,
    }


def _collect_visits_from_tools(
    tools: list[dict[str, Any]],
    problems: list[dict[str, Any]],
) -> dict[str, Any]:
    count = 0
    open_count = 0
    closed_count = 0
    visits_without_start = 0
    visits_without_end = 0
    per_tool: Counter[str] = Counter()

    for tool in tools:
        tool_id = _tool_id(tool) or _norm_text(tool.get("_source")) or "?"
        visits = _tool_visits(tool)
        if visits:
            per_tool[tool_id] += len(visits)

        for visit in visits:
            count += 1
            start = _visit_start(visit)
            end = _visit_end(visit)

            if not start:
                visits_without_start += 1
                _problem(
                    problems,
                    level="warning",
                    code="visit_without_start",
                    message="Wizyta bez startu.",
                    extra={"tool_id": tool_id},
                )
            if not end:
                visits_without_end += 1
                open_count += 1
            else:
                closed_count += 1

    top_tools = [
        {"tool_id": tool_id, "visits": visits}
        for tool_id, visits in per_tool.most_common(10)
    ]

    return {
        "count": count,
        "open_count": open_count,
        "closed_count": closed_count,
        "tools_with_visits_count": len(per_tool),
        "max_visits_per_tool": max(per_tool.values(), default=0),
        "top_tools_by_visits": top_tools,
        "visits_without_start": visits_without_start,
        "visits_without_end": visits_without_end,
    }


def _dispatch_candidates(data_root: Path) -> list[Path]:
    return [
        data_root / "dyspozycje.json",
        data_root / "dyspozycje" / "dyspozycje.json",
        data_root / "dyspozycje",
        data_root / "dispatches.json",
        data_root / "dispatch" / "dispatches.json",
    ]


def _iter_dispatch_records(
    data_root: Path,
    problems: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    found_source = False

    for candidate in _dispatch_candidates(data_root):
        if candidate.is_dir():
            found_source = True
            for path in sorted(candidate.glob("*.json")):
                payload = _load_json_safe(path, problems)
                for item in _as_list(payload):
                    if isinstance(item, dict):
                        copy = dict(item)
                        copy.setdefault("_source", str(path))
                        records.append(copy)
            continue

        if candidate.is_file():
            found_source = True
            payload = _load_json_safe(candidate, problems)
            if isinstance(payload, dict):
                maybe = (
                    payload.get("dyspozycje")
                    or payload.get("dispatches")
                    or payload.get("items")
                    or payload.get("records")
                )
                if isinstance(maybe, list):
                    iterable = maybe
                else:
                    iterable = [payload]
            elif isinstance(payload, list):
                iterable = payload
            else:
                iterable = []

            for item in iterable:
                if isinstance(item, dict):
                    copy = dict(item)
                    copy.setdefault("_source", str(candidate))
                    records.append(copy)

    if not found_source:
        _problem(
            problems,
            level="info",
            code="dispatch_source_not_found",
            message="Nie znaleziono źródła dyspozycji.",
        )

    return records


def _dispatch_status(record: Mapping[str, Any]) -> str:
    return _norm_key(record.get("status") or record.get("state") or record.get("stan"))


def _is_closed_status(status: str) -> bool:
    return status in {
        "done",
        "closed",
        "zamkniete",
        "zamknięte",
        "wykonane",
        "zakończone",
        "zakonczone",
    }


def _collect_dispatches(data_root: Path, problems: list[dict[str, Any]]) -> dict[str, Any]:
    records = _iter_dispatch_records(data_root, problems)
    per_status: Counter[str] = Counter()
    per_priority: Counter[str] = Counter()
    per_assigned_to: Counter[str] = Counter()
    open_count = 0
    closed_count = 0
    overdue_count = 0
    missing_object_count = 0
    today = datetime.now().date()

    for record in records:
        status = _dispatch_status(record)
        priority = _norm_key(record.get("priorytet") or record.get("priority"), "brak")
        assigned = _norm_text(
            record.get("assigned_to")
            or record.get("osoba")
            or record.get("pracownik")
            or record.get("user")
        )
        obj = _norm_text(
            record.get("object_id")
            or record.get("obiekt")
            or record.get("narzedzie")
            or record.get("narzędzie")
            or record.get("tool_id")
            or record.get("maszyna")
            or record.get("zlecenie")
        )

        per_status[status] += 1
        per_priority[priority] += 1
        if assigned:
            per_assigned_to[assigned] += 1

        if _is_closed_status(status):
            closed_count += 1
        else:
            open_count += 1

        if not obj:
            missing_object_count += 1
            _problem(
                problems,
                level="warning",
                code="dispatch_missing_object",
                message="Dyspozycja bez obiektu.",
                path=record.get("_source"),
            )

        deadline = _parse_dt(record.get("termin") or record.get("deadline"))
        if deadline and not _is_closed_status(status) and deadline.date() < today:
            overdue_count += 1

    return {
        "count": len(records),
        "open_count": open_count,
        "closed_count": closed_count,
        "per_status": dict(per_status),
        "per_priority": dict(per_priority),
        "per_assigned_to": dict(per_assigned_to),
        "overdue_count": overdue_count,
        "missing_object_count": missing_object_count,
    }


def _collect_machines(data_root: Path, problems: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    try:
        from config_manager import ConfigManager, resolve_rel
        from utils_maszyny import load_machines_rows_with_fallback

        cfg = ConfigManager()
        cfg_dict = getattr(cfg, "global_cfg", {}) if cfg else {}
        loaded, _ = load_machines_rows_with_fallback(cfg_dict, resolve_rel)
        if isinstance(loaded, list):
            rows = [item for item in loaded if isinstance(item, dict)]
    except Exception:
        rows = []

    if not rows:
        path = data_root / "maszyny" / "maszyny.json"
        payload = _load_json_safe(path, problems) if path.exists() else None
        if isinstance(payload, dict):
            rows = [item for item in payload.get("maszyny", []) if isinstance(item, dict)]
        elif isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]

    per_status: Counter[str] = Counter()
    missing_id_count = 0
    alert_count = 0
    alert_statuses = {"awaria", "serwis", "uszkodzone", "stop"}

    for row in rows:
        machine_id = _norm_text(row.get("id") or row.get("nr") or row.get("nr_ewid"))
        status = _norm_key(row.get("status"))
        if not machine_id:
            missing_id_count += 1
        if status in alert_statuses:
            alert_count += 1
        per_status[status] += 1

    return {
        "count": len(rows),
        "per_status": dict(per_status),
        "alert_count": alert_count,
        "missing_id_count": missing_id_count,
    }


def _iter_order_files(data_root: Path) -> Iterable[Path]:
    orders_dir = data_root / "zlecenia"
    if orders_dir.is_dir():
        return sorted(
            path
            for path in orders_dir.glob("*.json")
            if not path.name.startswith("_")
        )
    return []


def _collect_orders(data_root: Path, problems: list[dict[str, Any]]) -> dict[str, Any]:
    orders: list[dict[str, Any]] = []

    for path in _iter_order_files(data_root):
        payload = _load_json_safe(path, problems)
        if isinstance(payload, dict):
            item = dict(payload)
            item.setdefault("_source", str(path))
            orders.append(item)

    if not orders:
        path = data_root / "zlecenia.json"
        if path.exists():
            payload = _load_json_safe(path, problems)
            if isinstance(payload, list):
                orders = [item for item in payload if isinstance(item, dict)]

    per_status: Counter[str] = Counter()
    missing_id_count = 0
    overdue_count = 0
    today = datetime.now().date()

    for order in orders:
        order_id = _norm_text(order.get("id") or order.get("nr") or order.get("numer"))
        status = _norm_key(order.get("status"))
        if not order_id:
            missing_id_count += 1
        per_status[status] += 1

        deadline = _parse_dt(order.get("termin") or order.get("deadline"))
        if deadline and not _is_closed_status(status) and deadline.date() < today:
            overdue_count += 1

    return {
        "count": len(orders),
        "per_status": dict(per_status),
        "overdue_count": overdue_count,
        "missing_id_count": missing_id_count,
    }


def _load_profiles_payload(data_root: Path, problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from config_manager import ConfigManager
        from profile_utils import load_profiles

        payload = load_profiles(ConfigManager())
        if isinstance(payload, dict):
            raw = payload.get("users") or payload.get("profiles") or []
            if isinstance(raw, list):
                return [item for item in raw if isinstance(item, dict)]
        elif isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    except Exception:
        pass

    path = data_root / "profiles.json"
    if not path.exists():
        _problem(
            problems,
            level="warning",
            code="profiles_missing",
            message="Nie znaleziono profiles.json.",
            path=path,
        )
        return []

    payload = _load_json_safe(path, problems)
    if isinstance(payload, dict):
        raw = payload.get("users") or payload.get("profiles") or []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    elif isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _collect_profiles(
    data_root: Path,
    problems: list[dict[str, Any]],
    tasks_summary: Mapping[str, Any],
) -> dict[str, Any]:
    profiles = _load_profiles_payload(data_root, problems)
    per_role: Counter[str] = Counter()
    active_count = 0
    disabled_count = 0

    for profile in profiles:
        role = _norm_key(profile.get("rola") or profile.get("role"), "brak")
        per_role[role] += 1
        active = profile.get("active")
        if active in (False, 0, "0", "false", "False", "nie"):
            disabled_count += 1
        else:
            active_count += 1

    workload = dict(tasks_summary.get("per_assigned_to") or {})

    return {
        "count": len(profiles),
        "active_count": active_count,
        "disabled_count": disabled_count,
        "per_role": dict(per_role),
        "workload_open_tasks": workload,
    }


def collect_statistics() -> dict[str, Any]:
    """Collect all available WM statistics without modifying any data."""

    problems: list[dict[str, Any]] = []
    data_root = _data_root()
    root_exists = data_root.exists()

    if not root_exists:
        _problem(
            problems,
            level="error",
            code="data_root_missing",
            message="Katalog danych WM nie istnieje.",
            path=data_root,
        )

    tools, tools_summary = _collect_tools(data_root, problems)
    tasks_summary = _collect_tasks_from_tools(tools, problems)
    visits_summary = _collect_visits_from_tools(tools, problems)
    dispatches_summary = _collect_dispatches(data_root, problems)
    machines_summary = _collect_machines(data_root, problems)
    orders_summary = _collect_orders(data_root, problems)
    profiles_summary = _collect_profiles(data_root, problems, tasks_summary)

    diagnostics = {
        "problem_count": len(problems),
        "problems": problems,
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": {
            "data_root": str(data_root),
            "exists": root_exists,
        },
        "narzedzia": tools_summary,
        "zadania": tasks_summary,
        "wizyty": visits_summary,
        "dyspozycje": dispatches_summary,
        "maszyny": machines_summary,
        "zlecenia": orders_summary,
        "operatorzy": profiles_summary,
        "diagnostyka": diagnostics,
    }


if __name__ == "__main__":
    print(json.dumps(collect_statistics(), ensure_ascii=False, indent=2))
