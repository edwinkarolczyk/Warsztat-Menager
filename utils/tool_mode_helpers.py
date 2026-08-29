# version: 1.1
"""
Helpery do trybu narzędzi (NN/SN) i walidacji numerów.
Nie zmieniają istniejącej bazy – tylko pomagają w GUI.
"""
from __future__ import annotations

from typing import Optional, Tuple


def infer_mode_from_id(tool_id: str | int) -> str:
    """
    Ustala tryb na podstawie numeru, gdy brak pola 'mode'.
    Zasada: <500 → 'NN', >=500 → 'SN'
    """
    try:
        n = int(str(tool_id).lstrip("0") or "0")
    except Exception:
        n = 0
    return "NN" if 1 <= n <= 499 else "SN"


def get_tool_mode(tool: dict) -> str:
    """
    Zwraca tryb narzędzia, preferując pola jawne (mode/tryb) nad inferencją.
    """
    candidates = (
        tool.get("mode"),
        tool.get("tryb"),
        tool.get("class"),
        tool.get("kategoria"),
    )
    for raw in candidates:
        val = str(raw or "").strip().upper()
        if val in {"NN", "SN"}:
            return val
        if val in {"NOWE", "STARE"}:
            return "NN" if val == "NOWE" else "SN"
    return infer_mode_from_id(
        tool.get("id")
        or tool.get("nr")
        or tool.get("numer")
        or tool.get("number")
        or 0
    )


def validate_number(
    nr: int,
    mode: str,
    *,
    is_new: bool,
    keep_number: bool,
) -> Tuple[bool, Optional[str]]:
    """
    Walidacja numeru przy tworzeniu/edycji z zachowaniem stałego numeru.
    Zasady:
      - numer narzędzia ma zawsze dokładnie 3 cyfry, więc zakres kończy się na 999;
      - nowe NN: 001–499, nowe SN: 500–999;
      - przy edycji zachowany numer może należeć do dowolnego zakresu 001–999;
      - funkcja nie zezwala na numer 000 ani 1000+.
    """
    mode = (mode or "").upper()
    if is_new:
        if mode == "NN" and not (1 <= nr <= 499):
            return False, "NN: dozwolone numery 001–499."
        if mode == "SN" and not (500 <= nr <= 999):
            return False, "SN: dozwolone numery 500–999."
        return True, None
    if keep_number:
        if not (1 <= nr <= 999):
            return False, "Dozwolone numery 001–999."
        return True, None
    # Stara ścieżka zgodności: jeśli wywołujący sprawdza zmianę numeru,
    # nadal pilnujemy wyłącznie poprawnego, trzycyfrowego zakresu.
    if mode == "NN" and not (1 <= nr <= 499):
        return False, "NN: dozwolone numery 001–499."
    if mode == "SN" and not (500 <= nr <= 999):
        return False, "SN: dozwolone numery 500–999."
    return True, None
