# version: 1.0
# Moduł: narzedzia_ui.editor_variant_tuning_runtime
# Korekty nowego dashboardu NN/SN bez zmiany starego edytora i modelu danych.
# - usuwa fioletowe akcenty (używa głównego akcentu motywu),
# - wyłącza ciężkie odświeżanie co 450 ms,
# - buforuje miniatury,
# - kliknięcie pustej miniatury otwiera wybór zdjęcia,
# - wzmacnia wyszukiwanie starego przycisku Wybierz… / Wybierz....

from __future__ import annotations

import os
from typing import Any
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant


def _norm_button_text(value: object) -> str:
    return str(value or "").strip().lower().replace("…", "...")


def install_editor_variant_tuning_runtime() -> None:
    if getattr(_variant, "_wm_editor_variant_tuning_installed", False):
        return

    # 1) Bez osobnego fioletowego akcentu. Karty SN/wizyt korzystają z akcentu motywu.
    original_palette = _variant._palette

    def _palette_without_purple() -> dict[str, str]:
        colors = dict(original_palette())
        colors["purple"] = colors.get("accent", colors.get("blue", "#d43c3c"))
        return colors

    _variant._palette = _palette_without_purple

    # 2) W starszym formularzu spotykamy zarówno trzy kropki, jak i znak wielokropka.
    original_find_button = _variant._find_button

    def _find_button_flexible(holder: tk.Misc | None, text: str) -> ttk.Button | None:
        found = original_find_button(holder, text)
        if found is not None:
            return found
        if holder is None:
            return None
        wanted = _norm_button_text(text)
        for widget in [holder, *_variant._all_descendants(holder)]:
            if not isinstance(widget, ttk.Button):
                continue
            try:
                actual = _norm_button_text(widget.cget("text"))
            except Exception:
                continue
            if actual == wanted:
                return widget
            if wanted.startswith("wybierz") and actual.startswith("wybierz"):
                return widget
        return None

    _variant._find_button = _find_button_flexible

    # 3) Nie dekoduj tego samego zdjęcia przy każdym drobnym odświeżeniu dashboardu.
    original_refresh_thumbnail = _variant._refresh_thumbnail

    def _refresh_thumbnail_cached(
        window: tk.Toplevel,
        label: tk.Label | ttk.Label,
        size: tuple[int, int] = (240, 180),
    ) -> None:
        try:
            path = _variant._preview_path(window)
        except Exception:
            path = None

        if path is None:
            token = (None, size)
        else:
            try:
                stat = os.stat(path)
                token = (str(path), int(stat.st_mtime_ns), int(stat.st_size), size)
            except OSError:
                token = (str(path), 0, 0, size)

        if getattr(label, "_wm_editor_thumb_token", object()) == token:
            return

        original_refresh_thumbnail(window, label, size)
        try:
            label._wm_editor_thumb_token = token  # type: ignore[attr-defined]
        except Exception:
            pass

    _variant._refresh_thumbnail = _refresh_thumbnail_cached

    # 4) Oryginalna wersja 2.0 uruchamiała pełny sync co 450 ms.
    #    Po zbudowaniu widoku kasujemy ten timer i zostawiamy tylko sync po akcjach.
    original_decorate = _variant._decorate_editor

    def _decorate_tuned(window: tk.Toplevel) -> bool:
        result = original_decorate(window)
        if not result:
            return result
        if not getattr(window, "_wm_editor_variant_ready", False):
            return result
        if getattr(window, "_wm_editor_variant_tuned", False):
            return result

        refresh_job = getattr(window, "_wm_editor_variant_refresh_job", None)
        if isinstance(refresh_job, dict):
            job_id = refresh_job.get("id")
            if job_id:
                try:
                    window.after_cancel(job_id)
                except Exception:
                    pass
            refresh_job["id"] = None

        _main, header, notebook = _variant._editor_parts(window)
        if header is None or notebook is None:
            window._wm_editor_variant_tuned = True  # type: ignore[attr-defined]
            return result

        dashboard = _variant._tab_by_text(notebook, "Podgląd")
        media_tab = _variant._tab_by_text(notebook, "Pliki i zdjęcia")
        colors = _variant._palette()
        sync_job: dict[str, Any] = {"id": None}

        def _sync_now() -> None:
            sync_job["id"] = None
            try:
                if not window.winfo_exists():
                    return
            except Exception:
                return
            if dashboard is None or media_tab is None:
                return
            try:
                _variant._sync_new_view(window, header, dashboard, media_tab, colors)
            except Exception:
                pass

        def _schedule_sync(_event: Any = None, delay: int = 80) -> None:
            previous = sync_job.get("id")
            if previous:
                try:
                    window.after_cancel(previous)
                except Exception:
                    pass
            try:
                sync_job["id"] = window.after(delay, _sync_now)
            except Exception:
                sync_job["id"] = None

        # Odświeżaj wtedy, kiedy użytkownik realnie coś zrobił / wrócił z dialogu.
        try:
            notebook.bind("<<NotebookTabChanged>>", _schedule_sync, add="+")
            window.bind("<FocusIn>", _schedule_sync, add="+")
        except Exception:
            pass

        image_holder = _variant._field_value_widget(window, "Obraz")
        source_choose = _variant._find_button(image_holder, "Wybierz...")

        def _choose_image() -> None:
            if source_choose is None:
                return
            try:
                source_choose.invoke()
            finally:
                _schedule_sync(delay=40)

        # W zakładce Pliki i zdjęcia korzystaj wprost z istniejącej logiki select_img().
        if media_tab is not None and source_choose is not None:
            new_choose = _variant._find_button(media_tab, "Dodaj / zmień zdjęcie")
            if new_choose is not None:
                try:
                    new_choose.configure(command=_choose_image)
                    new_choose.state(["!disabled"])
                except Exception:
                    pass

        def _thumbnail_action(_event: Any = None) -> None:
            try:
                has_image = _variant._preview_path(window) is not None
            except Exception:
                has_image = False
            if has_image:
                try:
                    _variant._open_full_preview(window)
                except Exception:
                    pass
            else:
                _choose_image()

        # Pusta miniatura = dodaj zdjęcie; istniejąca miniatura = duży podgląd.
        for thumb in (
            getattr(header, "_wm_thumb", None),
            getattr(media_tab, "_wm_thumb", None) if media_tab is not None else None,
        ):
            if thumb is None:
                continue
            try:
                thumb.bind("<Button-1>", _thumbnail_action)
            except Exception:
                pass

        _schedule_sync(delay=10)
        window._wm_editor_variant_sync_job = sync_job  # type: ignore[attr-defined]
        window._wm_editor_variant_tuned = True  # type: ignore[attr-defined]
        return result

    _variant._decorate_editor = _decorate_tuned
    _variant._wm_editor_variant_tuning_installed = True


__all__ = ["install_editor_variant_tuning_runtime"]
