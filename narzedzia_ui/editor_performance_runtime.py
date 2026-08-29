# version: 1.1
# Moduł: narzedzia_ui.editor_performance_runtime
# Wydajność nowego edytora NN/SN bez zmiany modelu danych ani starego widoku.
# - blokuje ciężkie pełne odświeżanie po każdym kliknięciu i FocusIn,
# - pozwala na pojedynczy sync przy zmianie zakładki, aby dashboard nie był nieaktualny,
# - krótkotrwale buforuje dokument narzędzia, aby jeden sync nie czytał go kilka razy,
# - nagłówek Numer/Nazwa/Typ/Status aktualizuje lekkimi trace zmiennych Tk.

from __future__ import annotations

import time
from typing import Any
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant


_CACHE_TTL_SEC = 1.5
_HEAVY_WINDOW_EVENTS = {"<FocusIn>", "<ButtonRelease-1>"}
_HEAVY_NOTEBOOK_EVENTS: set[str] = set()


def _norm_nr(value: object) -> str:
    raw = str(value or "").strip()
    if raw.isdigit() and len(raw) <= 3:
        return raw.zfill(3)
    return raw


def _shared_text_var(window: tk.Toplevel, field_label: str) -> tk.StringVar | None:
    try:
        holder = _variant._field_value_widget(window, field_label)
        widget = _variant._first_entry(holder)
        if widget is None:
            return None
        name = str(widget.cget("textvariable") or "").strip()
        if not name:
            return None
        return tk.StringVar(master=window, name=name)
    except Exception:
        return None


def _install_light_header_traces(window: tk.Toplevel, header: tk.Misc) -> None:
    if getattr(window, "_wm_perf_header_traces", False):
        return

    nr_var = _shared_text_var(window, "Numer (3 cyfry)")
    name_var = _shared_text_var(window, "Nazwa")
    type_var = _shared_text_var(window, "Typ")
    status_var = _shared_text_var(window, "Status")

    try:
        title = str(window.title() or "")
    except Exception:
        title = ""
    mode = "NN" if "NOWE" in title.upper() else "SN"
    colors = _variant._palette()

    def _paint(*_args: Any) -> None:
        try:
            nr = _norm_nr(nr_var.get()) if nr_var is not None else "---"
            name = str(name_var.get() or "").strip() if name_var is not None else ""
            tool_type = str(type_var.get() or "").strip() if type_var is not None else ""
            status = str(status_var.get() or "").strip() if status_var is not None else ""

            number_badge = getattr(header, "_wm_number_badge", None)
            if number_badge is not None:
                number_badge.configure(text=f"#{nr or '---'}")

            mode_badge = getattr(header, "_wm_mode_badge", None)
            if mode_badge is not None:
                mode_badge.configure(text=mode)

            name_label = getattr(header, "_wm_name_label", None)
            if name_label is not None:
                name_label.configure(text=name or "Bez nazwy")

            type_label = getattr(header, "_wm_type_label", None)
            if type_label is not None:
                type_label.configure(text=f"Typ: {tool_type or '—'}")

            status_badge = getattr(header, "_wm_status_badge", None)
            if status_badge is not None:
                status_badge.configure(
                    text=status or "—",
                    bg=_variant._status_color(status, colors),
                )
        except Exception:
            pass

    traces: list[tuple[tk.StringVar, str]] = []
    for var in (nr_var, name_var, type_var, status_var):
        if var is None:
            continue
        try:
            trace_id = var.trace_add("write", _paint)
            traces.append((var, trace_id))
        except Exception:
            pass

    _paint()
    window._wm_perf_header_trace_refs = traces  # type: ignore[attr-defined]
    window._wm_perf_header_traces = True  # type: ignore[attr-defined]


def install_editor_performance_runtime() -> None:
    if getattr(_variant, "_wm_editor_performance_installed", False):
        return

    # Jeden pełny sync potrafił wywołać _current_doc kilka razy (dashboard + miniatury).
    # Trzymamy krótki cache per okno/numer; po 1.5 s kolejny jawny sync może odczytać świeży plik.
    original_current_doc = _variant._current_doc

    def _current_doc_cached(window: tk.Toplevel) -> dict[str, Any]:
        try:
            nr = _norm_nr(_variant._entry_value_from_field(window, "Numer (3 cyfry)"))
        except Exception:
            nr = ""
        now = time.monotonic()
        cached_nr = getattr(window, "_wm_perf_doc_nr", None)
        cached_at = float(getattr(window, "_wm_perf_doc_at", 0.0) or 0.0)
        cached_doc = getattr(window, "_wm_perf_doc", None)
        if cached_nr == nr and isinstance(cached_doc, dict) and (now - cached_at) <= _CACHE_TTL_SEC:
            return cached_doc

        doc = original_current_doc(window)
        if not isinstance(doc, dict):
            doc = {}
        try:
            window._wm_perf_doc_nr = nr  # type: ignore[attr-defined]
            window._wm_perf_doc_at = now  # type: ignore[attr-defined]
            window._wm_perf_doc = doc  # type: ignore[attr-defined]
        except Exception:
            pass
        return doc

    _variant._current_doc = _current_doc_cached

    # Ten wrapper jest instalowany po tuning + multistage, więc obejmuje cały łańcuch dekoracji.
    original_decorate = _variant._decorate_editor

    def _decorate_fast(window: tk.Toplevel) -> bool:
        if getattr(window, "_wm_editor_performance_ready", False):
            return original_decorate(window)

        start = time.perf_counter()
        real_window_bind = window.bind
        notebook_before = None
        try:
            _main, _header, notebook_before = _variant._editor_parts(window)
        except Exception:
            notebook_before = None

        real_notebook_bind = notebook_before.bind if notebook_before is not None else None

        def _window_bind_filtered(sequence=None, func=None, add=None):
            if sequence in _HEAVY_WINDOW_EVENTS and func is not None:
                # Nie rejestrujemy pełnego dashboard-sync na każde kliknięcie / zmianę fokusu.
                return ""
            return real_window_bind(sequence, func, add)

        def _notebook_bind_filtered(sequence=None, func=None, add=None):
            if sequence in _HEAVY_NOTEBOOK_EVENTS and func is not None:
                # Rezerwa dla przyszłych ciężkich zdarzeń notebooka.
                return ""
            if real_notebook_bind is None:
                return ""
            return real_notebook_bind(sequence, func, add)

        try:
            window.bind = _window_bind_filtered  # type: ignore[method-assign]
            if notebook_before is not None:
                notebook_before.bind = _notebook_bind_filtered  # type: ignore[method-assign]
            result = original_decorate(window)
        finally:
            try:
                delattr(window, "bind")
            except Exception:
                pass
            if notebook_before is not None:
                try:
                    delattr(notebook_before, "bind")
                except Exception:
                    pass

        if not result:
            return result

        try:
            _main, header, _notebook = _variant._editor_parts(window)
            if header is not None:
                _install_light_header_traces(window, header)
        except Exception:
            pass

        try:
            window._wm_editor_performance_ready = True  # type: ignore[attr-defined]
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            print(f"[WM-PERF][TOOLS_EDITOR] nowy widok zbudowany bez click/focus sync: {elapsed_ms:.1f} ms")
        except Exception:
            pass
        return result

    _variant._decorate_editor = _decorate_fast
    _variant._wm_editor_performance_installed = True


__all__ = ["install_editor_performance_runtime"]
