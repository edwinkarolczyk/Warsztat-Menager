# version: 1.0
# Moduł: narzedzia_ui.editor_stability_runtime
# Stabilność nowego edytora NN/SN bez zmiany modelu danych.
# - utrzymuje przy życiu współdzielone zmienne Tk używane przez klony pól,
# - blokuje przypadkowe drugie otwarcie edycji tego samego narzędzia,
# - dodaje lekkie logi czasu budowy i diagnostykę galerii zdjęć.

from __future__ import annotations

import os
import time
import weakref
from pathlib import Path
from typing import Any
import tkinter as tk

from . import editor_variant_runtime as _variant


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}
_OPEN_EDITORS: dict[str, weakref.ReferenceType[tk.Toplevel]] = {}


def _alive(widget: tk.Misc | None) -> bool:
    try:
        return widget is not None and bool(int(widget.winfo_exists()))
    except Exception:
        return False


def _editor_key(window: tk.Toplevel) -> str:
    """Klucz tylko dla edycji istniejącego narzędzia; dodawania nie blokujemy."""
    try:
        title = str(window.title() or "").strip()
    except Exception:
        return ""
    if title not in _EDITOR_TITLES or not title.startswith("Edytuj"):
        return ""
    try:
        nr = str(
            _variant._entry_value_from_field(window, "Numer (3 cyfry)") or ""
        ).strip()
    except Exception:
        nr = ""
    if nr.isdigit() and len(nr) <= 3:
        nr = nr.zfill(3)
    if not nr:
        return ""
    mode = "NN" if "NOWE" in title.upper() else "SN"
    return f"{mode}:{nr}"


def _keep_named_var_alive(
    window: tk.Toplevel, name: str, variable: tk.Variable | None
) -> tk.Variable | None:
    """Zachowaj Pythonowy wrapper zmiennej Tcl do końca życia danego okna."""
    if variable is None or not name:
        return variable
    registry = getattr(window, "_wm_editor_named_var_refs", None)
    if not isinstance(registry, dict):
        registry = {}
        try:
            window._wm_editor_named_var_refs = registry  # type: ignore[attr-defined]
        except Exception:
            return variable
    existing = registry.get(name)
    if isinstance(existing, tk.Variable):
        return existing
    registry[name] = variable
    return variable


def _install_shared_variable_guard() -> None:
    """Nie pozwól, by tymczasowy StringVar skasował oryginalny PY_VARxx."""
    current = getattr(_variant, "_shared_var", None)
    if not callable(current) or getattr(current, "_wm_stability_guard", False):
        return
    original = current

    def _shared_var_retained(
        window: tk.Toplevel, widget: tk.Misc | None
    ) -> tk.StringVar | None:
        if widget is None:
            return None
        try:
            name = str(widget.cget("textvariable") or "").strip()
        except Exception:
            name = ""
        if not name:
            return original(window, widget)

        registry = getattr(window, "_wm_editor_named_var_refs", None)
        if isinstance(registry, dict):
            existing = registry.get(name)
            if isinstance(existing, tk.StringVar):
                return existing

        variable = original(window, widget)
        kept = _keep_named_var_alive(window, name, variable)
        return kept if isinstance(kept, tk.StringVar) else variable

    _shared_var_retained._wm_stability_guard = True  # type: ignore[attr-defined]
    _shared_var_retained._wm_stability_original = original  # type: ignore[attr-defined]
    _variant._shared_var = _shared_var_retained


def _install_boolean_variable_guard() -> None:
    """
    _build_dashboard() tworzy także BooleanVar po nazwie istniejącej zmiennej.
    Na czas synchronicznej budowy przechwytujemy taki wrapper i zachowujemy go
    przy oknie. Nie zmieniamy wartości ani działania checkboxa.
    """
    current = getattr(_variant, "_build_dashboard", None)
    if not callable(current) or getattr(current, "_wm_stability_bool_guard", False):
        return
    original = current
    original_boolean_var = tk.BooleanVar

    def _build_dashboard_guarded(
        window: tk.Toplevel, notebook: Any, colors: dict[str, str]
    ):
        retained: list[tk.BooleanVar] = getattr(
            window, "_wm_editor_named_bool_refs", None
        )
        if not isinstance(retained, list):
            retained = []
            try:
                window._wm_editor_named_bool_refs = retained  # type: ignore[attr-defined]
            except Exception:
                pass

        def _retained_boolean_var(*args: Any, **kwargs: Any):
            variable = original_boolean_var(*args, **kwargs)
            name = str(kwargs.get("name") or "").strip()
            master = kwargs.get("master")
            if name and master is window:
                retained.append(variable)
            return variable

        # editor_variant_runtime.tk to ten sam moduł tkinter; podmiana trwa
        # tylko przez synchroniczne wykonanie _build_dashboard().
        previous_factory = tk.BooleanVar
        tk.BooleanVar = _retained_boolean_var  # type: ignore[assignment]
        try:
            return original(window, notebook, colors)
        finally:
            tk.BooleanVar = previous_factory  # type: ignore[assignment]

    _build_dashboard_guarded._wm_stability_bool_guard = True  # type: ignore[attr-defined]
    _build_dashboard_guarded._wm_stability_original = original  # type: ignore[attr-defined]
    _variant._build_dashboard = _build_dashboard_guarded


def _install_phase_timing() -> None:
    """Czasy tylko dla etapów budowanych raz na okno; bez zalewania konsoli."""
    for attr, label in (
        ("_build_header", "header"),
        ("_build_dashboard", "dashboard"),
        ("_build_media_tab", "media"),
    ):
        current = getattr(_variant, attr, None)
        if not callable(current) or getattr(current, "_wm_stability_timed", False):
            continue

        def _timed(*args: Any, __fn=current, __label=label, **kwargs: Any):
            started = time.perf_counter()
            try:
                return __fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - started
                print(
                    f"[WM-PERF][TOOLS_EDITOR][PHASE] "
                    f"{__label}={elapsed:.3f}s ({elapsed * 1000.0:.1f} ms)"
                )

        _timed._wm_stability_timed = True  # type: ignore[attr-defined]
        _timed._wm_stability_original = current  # type: ignore[attr-defined]
        setattr(_variant, attr, _timed)


def _install_media_diagnostics() -> None:
    current_items = getattr(_variant, "_preview_items", None)
    if callable(current_items) and not getattr(
        current_items, "_wm_stability_media_log", False
    ):
        original_items = current_items

        def _preview_items_logged(window: tk.Toplevel):
            started = time.perf_counter()
            items = original_items(window)
            elapsed = time.perf_counter() - started
            signature: tuple[tuple[str, str, str, bool], ...] = tuple(
                (
                    str(raw),
                    str(path),
                    str(kind),
                    bool(Path(path).is_file()),
                )
                for raw, path, kind in items
            )
            previous = getattr(window, "_wm_editor_media_log_signature", None)
            if signature != previous:
                try:
                    window._wm_editor_media_log_signature = signature  # type: ignore[attr-defined]
                except Exception:
                    pass
                print(
                    f"[WM-DBG][TOOLS_EDITOR][MEDIA] "
                    f"count={len(items)} resolve={elapsed:.3f}s"
                )
                if not items:
                    print("[WM-DBG][TOOLS_EDITOR][MEDIA] brak plików do karuzeli")
                for index, (raw, path, kind, exists) in enumerate(signature, start=1):
                    print(
                        f"[WM-DBG][TOOLS_EDITOR][MEDIA] "
                        f"{index}/{len(signature)} kind={kind} exists={exists} "
                        f"stored={raw!r} path={path!r}"
                    )
            return items

        _preview_items_logged._wm_stability_media_log = True  # type: ignore[attr-defined]
        _preview_items_logged._wm_stability_original = original_items  # type: ignore[attr-defined]
        _variant._preview_items = _preview_items_logged

    current_photo = getattr(_variant, "_load_photo", None)
    if callable(current_photo) and not getattr(
        current_photo, "_wm_stability_image_log", False
    ):
        original_photo = current_photo

        def _load_photo_logged(
            path: Path, master: tk.Misc, max_size: tuple[int, int]
        ):
            started = time.perf_counter()
            photo = original_photo(path, master, max_size)
            elapsed = time.perf_counter() - started
            try:
                exists = Path(path).is_file()
                size = os.path.getsize(path) if exists else 0
            except OSError:
                exists = False
                size = 0
            print(
                f"[WM-PERF][TOOLS_EDITOR][IMAGE] "
                f"file={str(path)!r} exists={exists} bytes={size} "
                f"target={max_size[0]}x{max_size[1]} "
                f"ok={photo is not None} load={elapsed:.3f}s"
            )
            return photo

        _load_photo_logged._wm_stability_image_log = True  # type: ignore[attr-defined]
        _load_photo_logged._wm_stability_original = original_photo  # type: ignore[attr-defined]
        _variant._load_photo = _load_photo_logged


def _install_duplicate_editor_guard() -> None:
    current = getattr(_variant, "_decorate_editor", None)
    if not callable(current) or getattr(current, "_wm_stability_editor_guard", False):
        return
    original = current

    def _decorate_stable(window: tk.Toplevel) -> bool:
        key = _editor_key(window)
        if key:
            previous_ref = _OPEN_EDITORS.get(key)
            previous = previous_ref() if previous_ref is not None else None
            if previous is not None and previous is not window and _alive(previous):
                print(
                    f"[WM-DBG][TOOLS_EDITOR][DUP] pominięto drugie okno {key}; "
                    "aktywuję już otwarty edytor"
                )
                try:
                    previous.lift()
                    previous.focus_force()
                except Exception:
                    pass
                try:
                    window.destroy()
                except Exception:
                    pass
                return True

            _OPEN_EDITORS[key] = weakref.ref(window)

            if not getattr(window, "_wm_stability_registry_bound", False):
                def _cleanup(event: tk.Event, *, expected_key=key, owner=window) -> None:
                    if getattr(event, "widget", None) is not owner:
                        return
                    ref = _OPEN_EDITORS.get(expected_key)
                    if ref is not None and ref() is owner:
                        _OPEN_EDITORS.pop(expected_key, None)

                try:
                    window.bind("<Destroy>", _cleanup, add="+")
                    window._wm_stability_registry_bound = True  # type: ignore[attr-defined]
                except Exception:
                    pass

        started = time.perf_counter()
        try:
            result = original(window)
        finally:
            elapsed = time.perf_counter() - started
            if key:
                print(
                    f"[WM-PERF][TOOLS_EDITOR][TOTAL] "
                    f"{key} decorate={elapsed:.3f}s ({elapsed * 1000.0:.1f} ms)"
                )
        return result

    _decorate_stable._wm_stability_editor_guard = True  # type: ignore[attr-defined]
    _decorate_stable._wm_stability_original = original  # type: ignore[attr-defined]
    _variant._decorate_editor = _decorate_stable


def install_editor_stability_runtime() -> None:
    if getattr(_variant, "_wm_editor_stability_installed", False):
        return

    # Kolejność ma znaczenie: guard zmiennych przed wrapperem czasowym dashboardu.
    _install_shared_variable_guard()
    _install_boolean_variable_guard()
    _install_phase_timing()
    _install_media_diagnostics()
    _install_duplicate_editor_guard()

    _variant._wm_editor_stability_installed = True
    print("[WM-DBG][TOOLS_EDITOR] stability runtime aktywny")


__all__ = ["install_editor_stability_runtime"]
