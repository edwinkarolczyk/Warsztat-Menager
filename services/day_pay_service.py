# version: 1.1
"""Model procentów płatnych dni dla Profili/Obecności WM.

To NIE jest moduł płacowy. Przechowuje wyłącznie neutralne dane źródłowe,
które później mogą zasilić kalkulator sugerowanej wypłaty.

Rozdzielamy:
- day_value       -> ewidencyjna dniówka pracy (0 / 0.5 / 1),
- pay_day_value   -> część dnia podlegająca rozliczeniu,
- pay_percent     -> procent płatności tej części dnia,
- pay_code        -> rodzaj dnia/nieobecności.

Wartości są domyślne i mogą zostać nadpisane przez config ``payroll.day_types``.
"""
from __future__ import annotations

from typing import Any

try:
    from config_manager import ConfigManager
except Exception:  # pragma: no cover
    ConfigManager = None  # type: ignore


DEFAULT_DAY_TYPES: dict[str, dict[str, Any]] = {
    "PRACA": {"label": "Praca", "pay_percent": 100.0},
    "UR": {"label": "Urlop wypoczynkowy", "pay_percent": 100.0},
    "UŻ": {"label": "Urlop na żądanie", "pay_percent": 100.0},
    "ŚW": {"label": "Siła wyższa", "pay_percent": 50.0},
    "L4": {"label": "L4", "pay_percent": 80.0},
    "NN": {"label": "Nieobecność nieusprawiedliwiona", "pay_percent": 0.0},
    "UB": {"label": "Urlop bezpłatny", "pay_percent": 0.0},
    "BRAK": {"label": "Brak dniówki", "pay_percent": 0.0},
}

_ALIASES = {
    "WORK": "PRACA",
    "PRESENT": "PRACA",
    "URL": "UR",
    "URLOP": "UR",
    "VACATION": "UR",
    "UZ": "UŻ",
    "UŻ": "UŻ",
    "SW": "ŚW",
    "ŚW": "ŚW",
    "SILA_WYZSZA": "ŚW",
    "SIŁA_WYŻSZA": "ŚW",
    "SILA WYZSZA": "ŚW",
    "SIŁA WYŻSZA": "ŚW",
    "FORCE_MAJEURE": "ŚW",
    "FORCE MAJEURE": "ŚW",
    "CHOROBOWE": "L4",
    "UNPAID": "UB",
    "URLOP_BEZPLATNY": "UB",
    "URLOP BEZPŁATNY": "UB",
    "MISSING_CONFIRMED": "BRAK",
}


def normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    return _ALIASES.get(text, text)


def _config_overrides() -> dict[str, dict[str, Any]]:
    if ConfigManager is None:
        return {}
    try:
        raw = ConfigManager().get("payroll.day_types", {})
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for code, data in raw.items():
        key = normalize_code(code)
        if not key or not isinstance(data, dict):
            continue
        out[key] = dict(data)
    return out


def definitions() -> dict[str, dict[str, Any]]:
    rows = {key: dict(value) for key, value in DEFAULT_DAY_TYPES.items()}
    for code, override in _config_overrides().items():
        current = rows.setdefault(code, {"label": code, "pay_percent": 0.0})
        if "label" in override:
            current["label"] = str(override.get("label") or code)
        if "pay_percent" in override:
            try:
                current["pay_percent"] = float(override.get("pay_percent"))
            except Exception:
                pass
    return rows


def compensation(
    code: Any,
    *,
    pay_day_value: float = 1.0,
    pay_percent: float | None = None,
) -> dict[str, Any]:
    key = normalize_code(code)
    rows = definitions()
    meta = rows.get(key, {"label": key or "Nieokreślone", "pay_percent": 0.0})
    configured = float(meta.get("pay_percent") or 0.0)
    percent = configured if pay_percent is None else float(pay_percent)
    percent = max(0.0, min(500.0, percent))
    day_value = max(0.0, float(pay_day_value))
    return {
        "pay_code": key,
        "pay_label": str(meta.get("label") or key),
        "pay_day_value": day_value,
        "pay_percent": percent,
        "pay_factor": percent / 100.0,
        "pay_equivalent_days": day_value * (percent / 100.0),
        "pay_source": "config" if key in _config_overrides() else "default",
    }


def apply_to_record(
    record: dict[str, Any],
    code: Any,
    *,
    pay_day_value: float = 1.0,
    pay_percent: float | None = None,
) -> dict[str, Any]:
    record.update(
        compensation(
            code,
            pay_day_value=pay_day_value,
            pay_percent=pay_percent,
        )
    )
    record["payroll_pending"] = False
    return record


def mark_pending(record: dict[str, Any]) -> dict[str, Any]:
    """Dzień nierozstrzygnięty nie może zostać automatycznie wyceniony."""
    record.update({
        "pay_code": "DO_DECYZJI",
        "pay_label": "Do decyzji Brygadzisty",
        "pay_day_value": 0.0,
        "pay_percent": None,
        "pay_factor": None,
        "pay_equivalent_days": None,
        "pay_source": "pending",
        "payroll_pending": True,
    })
    return record


__all__ = [
    "DEFAULT_DAY_TYPES",
    "normalize_code",
    "definitions",
    "compensation",
    "apply_to_record",
    "mark_pending",
]
