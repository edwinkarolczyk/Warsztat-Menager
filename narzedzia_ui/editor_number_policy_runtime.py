# version: 1.1
# Moduł: narzedzia_ui.editor_number_policy_runtime
# Zasada numeracji Narzędzi:
# - numer zawsze ma dokładnie 3 cyfry (001–999),
# - po pierwszym zapisie numer jest stałą tożsamością narzędzia,
# - zapis nie może wykonać renumeracji istniejącego narzędzia,
# - generator wolnych numerów nigdy nie proponuje 1000.

from __future__ import annotations

from pathlib import Path
from typing import Any
import tkinter as tk

from . import editor_variant_runtime as _variant


def _normalize_number(value: object) -> str:
    raw = str(value or "").strip()
    if not raw.isdigit():
        return ""
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return ""
    if not (1 <= number <= 999):
        return ""
    return f"{number:03d}"


def _previous_number(data: dict[str, Any]) -> str:
    previous = _normalize_number(data.get("__prev_id__"))
    if previous:
        return previous

    previous_path = data.get("__prev_path__")
    if previous_path:
        try:
            return _normalize_number(Path(str(previous_path)).stem)
        except Exception:
            return ""
    return ""


def _install_generator_cap(tools_gui) -> None:
    current = getattr(tools_gui, "_next_free_in_range", None)
    if not callable(current) or getattr(current, "_wm_three_digit_cap", False):
        return
    original = current

    def _next_free_three_digits(start, end):
        try:
            capped_end = min(int(end), 999)
        except (TypeError, ValueError):
            capped_end = 999
        return original(start, capped_end)

    _next_free_three_digits._wm_three_digit_cap = True  # type: ignore[attr-defined]
    _next_free_three_digits._wm_three_digit_original = original  # type: ignore[attr-defined]
    tools_gui._next_free_in_range = _next_free_three_digits


def _install_save_guard() -> None:
    """Załóż blokadę na centralny zapis, gdy gui_narzedzia jest już zbudowane."""

    try:
        import gui_narzedzia as tools_gui
    except Exception:
        return

    _install_generator_cap(tools_gui)

    current = getattr(tools_gui, "_save_tool", None)
    if not callable(current) or getattr(current, "_wm_number_identity_guard", False):
        return
    original = current

    def _save_tool_guarded(data):
        if not isinstance(data, dict):
            raise ValueError("Niepoprawne dane narzędzia.")

        obj = dict(data)
        raw_number = (
            obj.get("numer")
            or obj.get("nr")
            or obj.get("id")
            or obj.get("number")
            or ""
        )
        number = _normalize_number(raw_number)
        if not number:
            raise ValueError(
                "Numer narzędzia musi mieć 3 cyfry i mieścić się w zakresie 001–999."
            )

        previous = _previous_number(obj)
        if previous and previous != number:
            print(
                "[WM-ERR][TOOLS_NUMBER] zablokowano renumerację "
                f"{previous} -> {number}"
            )
            raise ValueError(
                f"Numer narzędzia {previous} jest stały i po utworzeniu nie może być zmieniony."
            )

        obj["numer"] = number
        obj["nr"] = number
        obj["id"] = number
        if "number" in obj:
            obj["number"] = number
        return original(obj)

    _save_tool_guarded._wm_number_identity_guard = True  # type: ignore[attr-defined]
    _save_tool_guarded._wm_number_identity_original = original  # type: ignore[attr-defined]
    tools_gui._save_tool = _save_tool_guarded
    print("[WM-DBG][TOOLS_NUMBER] zapis 001–999 + blokada renumeracji aktywna")


def _lock_number_widget(window: tk.Toplevel) -> None:
    """Po pierwszym zapisie użytkownik nie może już edytować numeru w tym oknie."""

    try:
        holder = _variant._field_value_widget(window, "Numer (3 cyfry)")
        entry = _variant._first_entry(holder)
    except Exception:
        entry = None
    if entry is None:
        return

    try:
        value = _normalize_number(entry.get())
    except Exception:
        value = ""
    if not value:
        return

    try:
        window._wm_locked_tool_number = value  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        entry.state(["readonly"])
    except Exception:
        try:
            entry.configure(state="disabled")
        except Exception:
            pass


def _install_editor_lock_hook() -> None:
    current = getattr(_variant, "_build_header", None)
    if not callable(current) or getattr(current, "_wm_number_policy_hook", False):
        return
    original = current

    def _build_header_number_policy(window, header, colors):
        # Edytor powstaje dopiero po pełnym załadowaniu gui_narzedzia, więc tutaj
        # można już bezpiecznie podpiąć centralną blokadę zapisu i generatora.
        _install_save_guard()

        result = original(window, header, colors)

        # Istniejące narzędzie jest blokowane od razu. Dla nowego numer zostanie
        # zablokowany zdarzeniem <<ToolSaved>> po pierwszym poprawnym zapisie.
        title = ""
        try:
            title = str(window.title() or "")
        except Exception:
            pass
        if title.startswith("Edytuj"):
            _lock_number_widget(window)

        if not getattr(window, "_wm_number_saved_binding", False):
            try:
                window.bind(
                    "<<ToolSaved>>",
                    lambda _event: _lock_number_widget(window),
                    add="+",
                )
                window._wm_number_saved_binding = True  # type: ignore[attr-defined]
            except Exception:
                pass
        return result

    _build_header_number_policy._wm_number_policy_hook = True  # type: ignore[attr-defined]
    _build_header_number_policy._wm_number_policy_original = original  # type: ignore[attr-defined]
    _variant._build_header = _build_header_number_policy


def install_editor_number_policy_runtime() -> None:
    if getattr(_variant, "_wm_editor_number_policy_installed", False):
        return

    _install_editor_lock_hook()
    _variant._wm_editor_number_policy_installed = True


__all__ = ["install_editor_number_policy_runtime"]
