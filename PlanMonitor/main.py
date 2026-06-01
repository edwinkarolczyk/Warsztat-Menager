"""Independent Excel production plan monitoring engine.

This module deliberately does not import any Warsztat Menager code.  It can be
copied together with ``gui.py`` and packaged as a standalone application.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
CONFIG_PATH = APP_DIR / "config.json"
SNAPSHOT_PATH = APP_DIR / "snapshots" / "current_snapshot.json"
HISTORY_PATH = APP_DIR / "reports" / "history.jsonl"
DISPOSITIONS_PATH = APP_DIR / "data" / "pending_dispositions.json"
LOG_PATH = APP_DIR / "logs" / "plan_monitor.log"
SUPPORTED_EXTENSIONS = {".xls", ".xlsx", ".xlsm"}
DEFAULT_CONFIG: dict[str, Any] = {
    "plan_file": "",
    "check_interval_seconds": 60,
    "department_keywords": [],
    "column_mapping": {
        "order": "",
        "symbol": "",
        "quantity": "",
        "deadline": "",
    },
}
COLUMN_ALIASES = {
    "order": ("order", "nr zlecenia", "numer zlecenia", "nr zlec",
              "nr zlec.", "zlecenie"),
    "symbol": ("symbol", "opis", "nazwa", "pozycja", "wyrób", "detal",
               "produkt"),
    "quantity": ("quantity", "ilość", "ilosc", "szt", "szt."),
    "deadline": ("date", "termin", "data", "data wysyłki", "data wysylki",
                 "deadline"),
    "process": ("process", "proces", "status"),
}
REQUIRED_COLUMNS = ("order", "symbol", "quantity", "deadline")
OPTIONAL_COLUMNS = ("process",)
CHANGE_LABELS = {
    "new": "NOWE",
    "removed": "USUNIĘTE",
    "quantity_changed": "ILOŚĆ",
    "deadline_changed": "TERMIN",
    "description_changed": "OPIS",
}


def ensure_directories(base_dir: Path = APP_DIR) -> None:
    """Create all runtime directories required by Plan Monitor."""
    for name in ("snapshots", "reports", "logs", "data"):
        (base_dir / name).mkdir(parents=True, exist_ok=True)


def setup_logging(log_path: Path = LOG_PATH) -> None:
    """Configure rotating-unnecessary, simple UTF-8 file logging."""
    ensure_directories(log_path.parent.parent)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in logging.getLogger().handlers
    ):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load configuration, filling newly introduced options with defaults."""
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with path.open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config.update(loaded)
    config["column_mapping"].update(loaded.get("column_mapping", {}))
    return config


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    """Persist configuration as human-readable UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        file.write("\n")


def normalize_text(value: Any) -> str:
    """Convert spreadsheet values into stable, stripped text."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_quantity(value: Any) -> int | float | str:
    """Keep quantities comparable while preserving non-numeric spreadsheet data."""
    text = normalize_text(value).replace(" ", "").replace(",", ".")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return normalize_text(value)
    return int(number) if number.is_integer() else number


def normalize_deadline(value: Any) -> str:
    """Represent dates consistently in ISO format when possible."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")
    text = normalize_text(value)
    if not text:
        return ""
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    return parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else text


def normalize_header(value: Any) -> str:
    """Normalize a column title for alias matching."""
    return re.sub(r"\s+", " ", normalize_text(value).lower()).strip()


def excel_column_index(reference: Any) -> int | None:
    """Convert an Excel column reference such as ``B`` or ``AA`` to an index."""
    normalized = normalize_text(reference).upper()
    if not re.fullmatch(r"[A-Z]+", normalized):
        return None
    index = 0
    for character in normalized:
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def resolve_mapping(
    columns: Iterable[Any], configured: dict[str, str]
) -> dict[str, str]:
    """Resolve configured columns or infer common Polish/English titles."""
    columns = [str(column) for column in columns]
    available = {normalize_header(column): column for column in columns}
    mapping: dict[str, str] = {}
    for field in REQUIRED_COLUMNS:
        aliases = COLUMN_ALIASES[field]
        selected = configured.get(field, "")
        if field == "deadline":
            selected = selected or configured.get("date", "")
        selected_header = normalize_header(selected)
        if selected_header in available:
            mapping[field] = available[selected_header]
            continue
        selected_index = excel_column_index(selected)
        if selected_index is not None and selected_index < len(columns):
            mapping[field] = columns[selected_index]
            continue
        match = next(
            (original for normalized, original in available.items()
             if normalized in aliases),
            "",
        )
        if not match:
            raise ValueError(
                f"Nie znaleziono kolumny: {field}. Ustaw mapowanie kolumn."
            )
        mapping[field] = match
    for field in OPTIONAL_COLUMNS:
        match = next(
            (original for normalized, original in available.items()
             if normalized in COLUMN_ALIASES[field]),
            "",
        )
        if match:
            mapping[field] = match
    return mapping


def read_plan(
    path: str | Path, mapping: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Read the first worksheet and return normalized production positions."""
    plan_path = Path(path)
    if plan_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Obsługiwane formaty planu: xls, xlsx, xlsm.")
    frame = pd.read_excel(plan_path)
    resolved = resolve_mapping(frame.columns, mapping or {})
    rows: list[dict[str, Any]] = []
    for _, source in frame.iterrows():
        row = {
            "order": normalize_text(source[resolved["order"]]),
            "symbol": normalize_text(source[resolved["symbol"]]),
            "quantity": normalize_quantity(source[resolved["quantity"]]),
            "deadline": normalize_deadline(source[resolved["deadline"]]),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def position_key(row: dict[str, Any]) -> str:
    """Build the requested order+symbol key, falling back to symbol+deadline."""
    if row.get("order"):
        return f'{row["order"]}|{row.get("symbol", "")}'
    return f'{row.get("symbol", "")}|{row.get("deadline", "")}'


def concerns_department(row: dict[str, Any], keywords: Iterable[str]) -> bool:
    """Check symbol/description against configured department keywords."""
    haystack = f'{row.get("symbol", "")} {row.get("order", "")}'.upper()
    return any(keyword.strip().upper() in haystack for keyword in keywords
               if keyword.strip())


def _change(
    change_type: str,
    row: dict[str, Any],
    old: Any,
    new: Any,
    keywords: Iterable[str],
    timestamp: str,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "type": change_type,
        "order": row.get("order", ""),
        "symbol": row.get("symbol", ""),
        "old": old,
        "new": new,
        "department_related": concerns_department(row, keywords),
    }


def compare_plans(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    keywords: Iterable[str] = (),
    timestamp: str | None = None,
) -> list[dict[str, Any]]:
    """Return granular changes between two snapshots.

    Description changes are reconciled by a unique order number before the
    requested order+symbol key is used, so renames are not reported as a
    misleading remove/add pair.
    """
    timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
    old_by_key = {position_key(row): row for row in previous}
    new_by_key = {position_key(row): row for row in current}
    removed = {key: row for key, row in old_by_key.items()
               if key not in new_by_key}
    added = {key: row for key, row in new_by_key.items()
             if key not in old_by_key}
    changes: list[dict[str, Any]] = []

    old_orders = {row["order"]: (key, row) for key, row in removed.items()
                  if row.get("order")}
    new_orders = {row["order"]: (key, row) for key, row in added.items()
                  if row.get("order")}
    for order in sorted(old_orders.keys() & new_orders.keys()):
        old_key, old_row = old_orders[order]
        new_key, new_row = new_orders[order]
        changes.append(_change("description_changed", new_row,
                               old_row["symbol"], new_row["symbol"],
                               keywords, timestamp))
        removed.pop(old_key)
        added.pop(new_key)
        _append_field_changes(changes, old_row, new_row, keywords, timestamp)

    for key in sorted(old_by_key.keys() & new_by_key.keys()):
        _append_field_changes(changes, old_by_key[key], new_by_key[key],
                              keywords, timestamp)
    for row in added.values():
        changes.append(_change("new", row, "", row, keywords, timestamp))
    for row in removed.values():
        changes.append(_change("removed", row, row, "", keywords, timestamp))
    return changes


def _append_field_changes(
    changes: list[dict[str, Any]],
    old_row: dict[str, Any],
    new_row: dict[str, Any],
    keywords: Iterable[str],
    timestamp: str,
) -> None:
    for field, change_type in (("quantity", "quantity_changed"),
                               ("deadline", "deadline_changed")):
        if old_row.get(field) != new_row.get(field):
            changes.append(_change(change_type, new_row, old_row.get(field),
                                   new_row.get(field), keywords, timestamp))


def load_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any] | None:
    """Read the previous snapshot, if one exists."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_snapshot(
    rows: list[dict[str, Any]], metadata: dict[str, Any],
    path: Path = SNAPSHOT_PATH,
) -> None:
    """Persist the complete normalized plan and source file metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": metadata, "rows": rows}
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def append_history(changes: Iterable[dict[str, Any]],
                   path: Path = HISTORY_PATH) -> None:
    """Append one JSON object per detected change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for change in changes:
            file.write(json.dumps(change, ensure_ascii=False) + "\n")


def load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    """Load the JSONL report history."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def disposition_for(row: dict[str, Any]) -> dict[str, Any]:
    """Create the future WM-compatible execution order payload."""
    return {
        "typ": "zlecenie_wykonania",
        "nr_zlecenia": row.get("order", ""),
        "symbol": row.get("symbol", ""),
        "ilosc": row.get("quantity", 0),
        "termin": row.get("deadline", ""),
    }


def append_dispositions(changes: Iterable[dict[str, Any]],
                        path: Path = DISPOSITIONS_PATH) -> None:
    """Save pending future dispositions generated from every new position."""
    existing: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            existing = json.load(file)
    existing.extend(disposition_for(change["new"]) for change in changes
                    if change["type"] == "new")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(existing, file, ensure_ascii=False, indent=2)
        file.write("\n")


def export_changes(changes: list[dict[str, Any]], path: str | Path) -> None:
    """Export visible changes to TXT or CSV according to the selected suffix."""
    export_path = Path(path)
    rows = [display_row(change) for change in changes]
    headers = ["Data", "Typ zmiany", "Nr zlecenia", "Symbol",
               "Stara wartość", "Nowa wartość", "Dotyczy działu"]
    if export_path.suffix.lower() == ".csv":
        with export_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)
    elif export_path.suffix.lower() == ".txt":
        with export_path.open("w", encoding="utf-8") as file:
            file.write(" | ".join(headers) + "\n")
            file.write("-" * 120 + "\n")
            for row in rows:
                file.write(" | ".join(map(str, row)) + "\n")
    else:
        raise ValueError("Raport można eksportować wyłącznie do TXT lub CSV.")


def display_row(change: dict[str, Any]) -> tuple[Any, ...]:
    """Convert a history entry into GUI/export table columns."""
    old = change.get("old", "")
    new = change.get("new", "")
    if isinstance(old, dict):
        old = old.get("quantity", "")
    if isinstance(new, dict):
        new = new.get("quantity", "")
    return (
        change.get("timestamp", ""),
        CHANGE_LABELS.get(change.get("type", ""), change.get("type", "")),
        change.get("order", ""),
        change.get("symbol", ""),
        old,
        new,
        "DOTYCZY DZIAŁU" if change.get("department_related")
        else "POZA DZIAŁEM",
    )


@dataclass
class CheckResult:
    """Result passed safely from the worker thread to the GUI thread."""

    status: str
    checked_at: str
    file_modified_at: str = ""
    changes: list[dict[str, Any]] | None = None
    message: str = ""


class PlanMonitor:
    """Stateful, GUI-independent production plan checker."""

    def __init__(
        self,
        config_path: Path = CONFIG_PATH,
        snapshot_path: Path = SNAPSHOT_PATH,
        history_path: Path = HISTORY_PATH,
        dispositions_path: Path = DISPOSITIONS_PATH,
        reader: Callable[[str | Path, dict[str, str]],
                         list[dict[str, Any]]] = read_plan,
    ) -> None:
        self.config_path = config_path
        self.snapshot_path = snapshot_path
        self.history_path = history_path
        self.dispositions_path = dispositions_path
        self.reader = reader
        self.config = load_config(config_path)
        self.last_signature: tuple[float, int] | None = None

    def reload_config(self) -> None:
        """Reload settings edited in the GUI."""
        self.config = load_config(self.config_path)

    def check(self, force: bool = False) -> CheckResult:
        """Check metadata and process a changed source file without raising."""
        checked_at = datetime.now().strftime("%H:%M:%S")
        plan_file = self.config.get("plan_file", "")
        if not plan_file:
            return CheckResult("error", checked_at,
                               message="Nie wybrano pliku planu.")
        try:
            stat = os.stat(plan_file)
            signature = (stat.st_mtime, stat.st_size)
            modified_at = datetime.fromtimestamp(stat.st_mtime).strftime(
                "%H:%M:%S"
            )
            snapshot = load_snapshot(self.snapshot_path)
            if not force and snapshot and signature == self.last_signature:
                return CheckResult("unchanged", checked_at, modified_at, [],
                                   "Plik nie zmienił się od ostatniego odczytu.")
            rows = self.reader(plan_file, self.config["column_mapping"])
            previous = snapshot.get("rows", []) if snapshot else []
            changes = compare_plans(previous, rows,
                                    self.config["department_keywords"])
            metadata = {
                "plan_file": plan_file,
                "modified_at": stat.st_mtime,
                "size": stat.st_size,
                "read_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_snapshot(rows, metadata, self.snapshot_path)
            if changes:
                append_history(changes, self.history_path)
                append_dispositions(changes, self.dispositions_path)
            self.last_signature = signature
            logging.info("Odczytano plan: %s; wykryto zmian: %s",
                         plan_file, len(changes))
            return CheckResult("changed" if changes else "unchanged",
                               checked_at, modified_at, changes,
                               notification_message(changes))
        except Exception as error:  # Keep network failures away from the GUI.
            logging.exception("Nie udało się odczytać planu: %s", plan_file)
            return CheckResult("error", checked_at,
                               message=f"Błąd odczytu pliku: {error}")


def notification_message(changes: list[dict[str, Any]]) -> str:
    """Build the requested summary notification."""
    if not changes:
        return "Brak zmian w planie"
    related = sum(bool(change.get("department_related")) for change in changes)
    return (f"Wykryto {len(changes)} zmiany. "
            f"{related} dotyczą Twojego działu.")


def main() -> None:
    """Start the Tk GUI lazily, keeping backend imports headless-friendly."""
    setup_logging()
    try:
        from .gui import run
    except ImportError:
        from gui import run
    run()


if __name__ == "__main__":
    main()
