"""Korekta faktycznego stanu Magazynu wykonywana przez Brygadzistę."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.root_paths import get_data_root
from machine_file_guard import warehouse_transaction_lock


def _warehouse_dir() -> Path:
    return get_data_root() / "magazyn"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Nie można odczytać {path.name}: {exc}") from exc


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _number(value: Any, field_name: str) -> float:
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} musi być liczbą.") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} nie może być ujemny ani nieskończony.")
    return number


def overlay_actual_states(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Nałóż stan faktyczny na kartoteki używane przez widok Magazynu."""

    states = _read_json(_warehouse_dir() / "stany.json", {})
    if not isinstance(states, dict):
        raise RuntimeError("Nieprawidłowy plik stany.json.")
    for item_id, item in items.items():
        state = states.get(item_id)
        if isinstance(state, dict) and "stan" in state:
            item["stan"] = state["stan"]
        elif state is not None and not isinstance(state, dict):
            item["stan"] = state
    return items


def adjust_actual_stock(
    item_id: str,
    new_stock: Any,
    *,
    current_stock: Any,
    user: str,
    reason: str,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ustaw stan faktyczny i zachowaj pełny ślad korekty w ``stany.json``."""

    key = str(item_id or "").strip()
    actor = str(user or "").strip()
    comment = str(reason or "").strip()
    if not key:
        raise ValueError("Brak ID pozycji magazynowej.")
    if not actor:
        raise ValueError("Nie udało się ustalić użytkownika wykonującego korektę.")
    if not comment:
        raise ValueError("Podaj powód korekty stanu.")

    requested = _number(new_stock, "Nowy stan")
    fallback = _number(current_stock, "Aktualny stan")
    states_path = _warehouse_dir() / "stany.json"

    with warehouse_transaction_lock(states_path):
        states = _read_json(states_path, {})
        if not isinstance(states, dict):
            raise RuntimeError("Nieprawidłowy plik stany.json.")
        raw = states.get(key)
        state = dict(raw) if isinstance(raw, dict) else {}
        before = _number(
            state.get("stan", raw if raw is not None and not isinstance(raw, dict) else fallback),
            "Aktualny stan",
        )
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "typ": "KOREKTA_STANU",
            "op": "ADJUST",
            "item_id": key,
            "user": actor,
            "comment": comment,
            "stan_przed": before,
            "stan_po": requested,
            "roznica": requested - before,
        }
        state["stan"] = requested
        if "ilosc" in state:
            state["ilosc"] = requested
        source = item if isinstance(item, dict) else {}
        state.setdefault("nazwa", str(source.get("nazwa") or key))
        state.setdefault("jednostka", str(source.get("jednostka") or ""))
        history = state.get("historia")
        if not isinstance(history, list):
            history = []
        history.append(record)
        state["historia"] = history[-200:]
        states[key] = state
        _write_json_atomic(states_path, states)
        return record
