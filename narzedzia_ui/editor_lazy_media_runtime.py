# version: 1.0
# Moduł: narzedzia_ui.editor_lazy_media_runtime
# Nowy edytor Narzędzi:
# - cięższe dane zakładek są odświeżane dopiero po wejściu w daną zakładkę,
# - nagłówek pokazuje jedno stałe zdjęcie główne zamiast karuzeli,
# - pełna lista zdjęć jest rozwiązywana dopiero w zakładce "Pliki i zdjęcia",
# - lista rozwiązań ścieżek zdjęć jest buforowana per okno i kolejność zdjęć.

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant


_PRIMARY_SIZE = (360, 230)
_PRIMARY_BOX = (380, 250)


def _selected_tab_title(window: tk.Toplevel) -> str:
    try:
        _main, _header, notebook = _variant._editor_parts(window)
        if notebook is None:
            return ""
        selected = notebook.select()
        return str(notebook.tab(selected, "text") or "").strip()
    except Exception:
        return ""


def _invalidate_media_cache(window: tk.Toplevel) -> None:
    for attr in (
        "_wm_lazy_preview_key",
        "_wm_lazy_preview_items",
        "_wm_lazy_primary_key",
    ):
        try:
            delattr(window, attr)
        except Exception:
            pass


def _install_preview_items_cache() -> None:
    current = getattr(_variant, "_preview_items", None)
    if not callable(current) or getattr(current, "_wm_lazy_cached", False):
        return
    original = current

    def _preview_items_cached(window: tk.Toplevel):
        try:
            raw_images = tuple(_variant._image_values(window))
        except Exception:
            raw_images = ()

        dxf = ""
        if not raw_images:
            getter = getattr(window, "_wm_tool_dxf_preview_get", None)
            if callable(getter):
                try:
                    dxf = str(getter() or "").strip()
                except Exception:
                    dxf = ""

        key = (raw_images, dxf)
        if getattr(window, "_wm_lazy_preview_key", None) == key:
            cached = getattr(window, "_wm_lazy_preview_items", None)
            if isinstance(cached, list):
                return cached

        items = original(window)
        try:
            window._wm_lazy_preview_key = key  # type: ignore[attr-defined]
            window._wm_lazy_preview_items = items  # type: ignore[attr-defined]
        except Exception:
            pass
        return items

    _preview_items_cached._wm_lazy_cached = True  # type: ignore[attr-defined]
    _preview_items_cached._wm_lazy_original = original  # type: ignore[attr-defined]
    _variant._preview_items = _preview_items_cached


def _primary_preview_path(window: tk.Toplevel) -> Path | None:
    try:
        values = _variant._image_values(window)
    except Exception:
        values = []

    raw = str(values[0]).strip() if values else ""
    dxf = ""
    if not raw:
        getter = getattr(window, "_wm_tool_dxf_preview_get", None)
        if callable(getter):
            try:
                dxf = str(getter() or "").strip()
            except Exception:
                dxf = ""

    key = (raw, dxf)
    if getattr(window, "_wm_lazy_primary_key", None) == key:
        cached = getattr(window, "_wm_lazy_primary_path", None)
        return Path(cached) if cached else None

    base = _variant._media_base()
    resolved: Path | None = None
    candidate_raw = raw or dxf
    if base is not None and candidate_raw:
        resolved = _variant._candidate_path(base, candidate_raw)
        if resolved is None and raw:
            candidate = Path(
                candidate_raw.replace("\\", os.sep).replace("/", os.sep)
            )
            resolved = candidate if candidate.is_absolute() else base / candidate

    try:
        window._wm_lazy_primary_key = key  # type: ignore[attr-defined]
        window._wm_lazy_primary_path = str(resolved) if resolved is not None else ""  # type: ignore[attr-defined]
    except Exception:
        pass
    return resolved


def _refresh_primary_photo(window: tk.Toplevel, header: tk.Misc | None) -> None:
    if header is None:
        return
    thumb = getattr(header, "_wm_thumb", None)
    if thumb is None:
        return

    path = _primary_preview_path(window)
    token = str(path) if path is not None else ""
    if getattr(thumb, "_wm_lazy_primary_token", None) == token:
        return

    if path is None:
        try:
            thumb.configure(
                image="",
                text="Brak zdjęcia głównego\nKliknij, aby dodać",
                justify="center",
            )
            thumb._wm_editor_photo = None  # type: ignore[attr-defined]
            thumb._wm_lazy_primary_token = ""  # type: ignore[attr-defined]
        except Exception:
            pass
        return

    photo = _variant._load_photo(path, thumb, _PRIMARY_SIZE)
    try:
        if photo is None:
            thumb.configure(
                image="",
                text="Nie można wyświetlić\nzdjęcia głównego",
                justify="center",
            )
            thumb._wm_editor_photo = None  # type: ignore[attr-defined]
        else:
            thumb.configure(image=photo, text="")
            thumb._wm_editor_photo = photo  # type: ignore[attr-defined]
        thumb._wm_editor_path = str(path)  # type: ignore[attr-defined]
        thumb._wm_lazy_primary_token = token  # type: ignore[attr-defined]
    except Exception:
        pass


def _install_static_primary_gallery() -> None:
    current_refresh = getattr(_variant, "_refresh_gallery_views", None)
    if callable(current_refresh) and not getattr(
        current_refresh, "_wm_lazy_static_primary", False
    ):
        original_refresh = current_refresh

        def _refresh_gallery_lazy(
            window: tk.Toplevel,
            header: tk.Misc | None,
            media_tab: tk.Misc | None,
        ) -> None:
            selected = _selected_tab_title(window)
            if selected == "Podgląd":
                _refresh_primary_photo(window, header)
                return
            if selected == "Pliki i zdjęcia":
                # W galerii użytkownik może ręcznie przechodzić po wszystkich zdjęciach.
                # Nagłówek pozostaje na zdjęciu głównym.
                original_refresh(window, None, media_tab)
                return

        _refresh_gallery_lazy._wm_lazy_static_primary = True  # type: ignore[attr-defined]
        _refresh_gallery_lazy._wm_lazy_original = original_refresh  # type: ignore[attr-defined]
        _variant._refresh_gallery_views = _refresh_gallery_lazy

    current_schedule = getattr(_variant, "_schedule_carousel", None)
    if callable(current_schedule) and not getattr(
        current_schedule, "_wm_lazy_carousel_disabled", False
    ):
        def _schedule_carousel_disabled(window: tk.Toplevel) -> None:
            _variant._cancel_carousel(window)

        _schedule_carousel_disabled._wm_lazy_carousel_disabled = True  # type: ignore[attr-defined]
        _schedule_carousel_disabled._wm_lazy_original = current_schedule  # type: ignore[attr-defined]
        _variant._schedule_carousel = _schedule_carousel_disabled


def _paint_light_header(
    window: tk.Toplevel,
    header: tk.Misc | None,
    colors: dict[str, str],
) -> tuple[str, str, str, str, str]:
    nr = _variant._entry_value_from_field(window, "Numer (3 cyfry)") or "---"
    name = _variant._entry_value_from_field(window, "Nazwa") or "Bez nazwy"
    tool_type = _variant._entry_value_from_field(window, "Typ") or "—"
    status = _variant._entry_value_from_field(window, "Status") or "—"
    try:
        title = str(window.title() or "")
    except Exception:
        title = ""
    upper_title = title.upper()
    if "NOWE" in upper_title or "[NN]" in upper_title:
        mode = "NN"
    elif "STARE" in upper_title or "[SN]" in upper_title:
        mode = "SN"
    else:
        mode = str(getattr(window, "_wm_lazy_mode", "SN") or "SN")
    try:
        window._wm_lazy_mode = mode  # type: ignore[attr-defined]
    except Exception:
        pass

    if header is not None:
        try:
            header._wm_number_badge.configure(text=f"#{nr}")  # type: ignore[attr-defined]
            header._wm_mode_badge.configure(  # type: ignore[attr-defined]
                text=mode,
                bg=colors["blue"] if mode == "NN" else colors["purple"],
            )
            header._wm_name_label.configure(text=name)  # type: ignore[attr-defined]
            header._wm_type_label.configure(text=f"Typ: {tool_type}")  # type: ignore[attr-defined]
            header._wm_status_badge.configure(  # type: ignore[attr-defined]
                text=status,
                bg=_variant._status_color(status, colors),
            )
        except Exception:
            pass

    try:
        window.title(f"Narzędzie {nr} — {name} [{mode}]")
    except Exception:
        pass
    return nr, name, tool_type, status, mode


def _sync_dashboard(
    window: tk.Toplevel,
    header: tk.Misc | None,
    dashboard: tk.Misc,
    colors: dict[str, str],
    status: str,
    mode: str,
) -> None:
    doc = _variant._current_doc(window)
    total, done, open_tasks = _variant._task_counts(window, doc)
    visit_count, visit_open, visit_start, visit_by = _variant._visit_stats(doc)

    try:
        if header is not None:
            header._wm_summary_label.configure(  # type: ignore[attr-defined]
                text=f"Zadania: {done}/{total}  •  Wizyty: {visit_count}"
            )

        dashboard._wm_mode_line.configure(  # type: ignore[attr-defined]
            text=f"{mode}  •  {status}",
            fg=_variant._status_color(status, colors),
        )
        if visit_open:
            text = f"Wizyta: W TOKU\nStart: {visit_start or '—'}"
            if visit_by:
                text += f"\nRozpoczął: {visit_by}"
            dashboard._wm_visit_line.configure(  # type: ignore[attr-defined]
                text=text,
                fg=colors["warning"],
            )
        else:
            dashboard._wm_visit_line.configure(  # type: ignore[attr-defined]
                text="Wizyta: brak otwartej",
                fg=colors["muted"],
            )

        for label, value in zip(
            dashboard._wm_stat_labels,  # type: ignore[attr-defined]
            (total, done, open_tasks, visit_count),
        ):
            label.configure(text=str(value))

        recent = _variant._history_lines(doc)
        dashboard._wm_history_text.configure(  # type: ignore[attr-defined]
            text="\n".join(recent) if recent else "Brak zapisanej historii"
        )

        current_images = _variant._image_values(window, doc)
        archived = doc.get("zadania_archiwalne") if isinstance(doc, dict) else []
        archived_count = len(archived) if isinstance(archived, list) else 0
        employee = str(doc.get("pracownik") or "—") if isinstance(doc, dict) else "—"
        date_value = _variant._added_date(doc)
        dxf = str(doc.get("dxf") or "") if isinstance(doc, dict) else ""
        desc = str(doc.get("opis") or "").strip() if isinstance(doc, dict) else ""
        if len(desc) > 220:
            desc = desc[:217].rstrip() + "..."
        dashboard._wm_extra_text.configure(  # type: ignore[attr-defined]
            text=(
                f"Pracownik: {employee}\n"
                f"Data: {date_value}\n"
                f"Zdjęcia: {len(current_images)}\n"
                f"DXF: {'tak' if dxf else 'nie'}\n"
                f"Zadania archiwalne: {archived_count}\n\n"
                f"Opis: {desc or '—'}"
            )
        )

        for attr in ("_wm_type_widget", "_wm_status_widget"):
            target = getattr(dashboard, attr, None)
            source = getattr(target, "_wm_source_combo", None)
            if target is not None and source is not None:
                try:
                    target.configure(values=source.cget("values"))
                except Exception:
                    pass
    except Exception:
        pass

    _refresh_primary_photo(window, header)


def _sync_media(
    window: tk.Toplevel,
    media_tab: tk.Misc,
) -> None:
    try:
        current_images = _variant._image_values(window)
        media_tab._wm_images_text.configure(  # type: ignore[attr-defined]
            text=_variant._images_summary(current_images)
        )
        dxf_label = (
            _variant._holder_label_value(
                _variant._field_value_widget(window, "Plik DXF")
            )
            or "—"
        )
        media_tab._wm_dxf_text.configure(text=dxf_label)  # type: ignore[attr-defined]
    except Exception:
        pass

    _variant._refresh_gallery_views(window, None, media_tab)


def _install_lazy_tab_sync() -> None:
    current = getattr(_variant, "_sync_new_view", None)
    if not callable(current) or getattr(current, "_wm_lazy_tabs", False):
        return

    def _sync_new_view_lazy(
        window: tk.Toplevel,
        header: tk.Misc,
        dashboard: tk.Misc,
        media_tab: tk.Misc,
        colors: dict[str, str],
    ) -> None:
        started = time.perf_counter()
        selected = _selected_tab_title(window) or "Podgląd"
        _nr, _name, _tool_type, status, mode = _paint_light_header(
            window, header, colors
        )

        if selected == "Podgląd":
            _sync_dashboard(window, header, dashboard, colors, status, mode)
        elif selected == "Pliki i zdjęcia":
            _sync_media(window, media_tab)
        else:
            # Inne zakładki mają własne widgety i dane. Nie odświeżamy dashboardu
            # ani galerii, dopóki użytkownik do nich nie wróci.
            pass

        loaded = getattr(window, "_wm_lazy_loaded_tabs", None)
        if not isinstance(loaded, set):
            loaded = set()
            try:
                window._wm_lazy_loaded_tabs = loaded  # type: ignore[attr-defined]
            except Exception:
                pass
        if selected not in loaded:
            loaded.add(selected)
            elapsed = (time.perf_counter() - started) * 1000.0
            print(
                "[WM-PERF][TOOLS_EDITOR][LAZY] "
                f"tab={selected!r} first_load={elapsed:.1f}ms"
            )

    _sync_new_view_lazy._wm_lazy_tabs = True  # type: ignore[attr-defined]
    _sync_new_view_lazy._wm_lazy_original = current  # type: ignore[attr-defined]
    _variant._sync_new_view = _sync_new_view_lazy


def _open_primary_only(window: tk.Toplevel) -> None:
    path = _primary_preview_path(window)
    if path is None:
        return

    preview = tk.Toplevel(window)
    preview.title(f"Zdjęcie główne — {path.name}")
    try:
        preview.transient(window)
    except Exception:
        pass
    try:
        from ui_theme import ensure_theme_applied

        ensure_theme_applied(preview)
    except Exception:
        pass

    frame = ttk.Frame(preview, padding=12, style="WM.TFrame")
    frame.pack(fill="both", expand=True)

    try:
        screen_w = max(640, int(preview.winfo_screenwidth()))
        screen_h = max(480, int(preview.winfo_screenheight()))
    except Exception:
        screen_w, screen_h = 1280, 800
    max_size = (
        min(1200, int(screen_w * 0.82)),
        min(820, int(screen_h * 0.78)),
    )
    photo = _variant._load_photo(path, preview, max_size)

    label = ttk.Label(
        frame,
        style="WM.Card.TLabel",
        text="" if photo is not None else f"Nie można otworzyć obrazu:\n{path.name}",
        image=photo if photo is not None else "",
        justify="center",
        anchor="center",
    )
    label.pack(fill="both", expand=True)
    label._wm_editor_photo = photo  # type: ignore[attr-defined]

    close = ttk.Button(
        frame,
        text="Zamknij",
        command=preview.destroy,
        style="WM.Side.TButton",
    )
    close.pack(anchor="e", pady=(10, 0))
    preview.bind("<Escape>", lambda _event: preview.destroy())

    try:
        width = min(1240, max(760, int(screen_w * 0.86)))
        height = min(900, max(560, int(screen_h * 0.84)))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        preview.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _install_editor_postprocess() -> None:
    current = getattr(_variant, "_decorate_editor", None)
    if not callable(current) or getattr(current, "_wm_lazy_decorator", False):
        return
    original = current

    def _decorate_lazy_media(window: tk.Toplevel) -> bool:
        result = original(window)
        if not result or getattr(window, "_wm_lazy_media_ready", False):
            return result

        _main, header, notebook = _variant._editor_parts(window)
        if header is None or notebook is None:
            return result

        thumb = getattr(header, "_wm_thumb", None)
        if thumb is not None:
            try:
                box = getattr(thumb, "master", None)
                if box is not None:
                    box.configure(width=_PRIMARY_BOX[0], height=_PRIMARY_BOX[1])
                    box.pack_propagate(False)
                thumb.configure(width=1, height=1)
                thumb.pack_configure(fill="both", expand=True, padx=6, pady=6)
            except Exception:
                pass

            def _open_primary(_event: Any = None) -> None:
                try:
                    window._wm_editor_gallery_index = 0  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    _open_primary_only(window)
                except Exception:
                    pass

            try:
                thumb.bind("<Button-1>", _open_primary)
            except Exception:
                pass

        def _invalidate(_event: Any = None) -> None:
            _invalidate_media_cache(window)
            thumb_local = getattr(header, "_wm_thumb", None)
            if thumb_local is not None:
                try:
                    thumb_local._wm_lazy_primary_token = object()  # type: ignore[attr-defined]
                except Exception:
                    pass

        try:
            window.bind("<<ToolMediaChanged>>", _invalidate, add="+")
            window.bind("<<ToolSaved>>", _invalidate, add="+")
        except Exception:
            pass

        try:
            selected = _selected_tab_title(window)
            if selected == "Podgląd":
                _refresh_primary_photo(window, header)
        except Exception:
            pass

        window._wm_lazy_media_ready = True  # type: ignore[attr-defined]
        return result

    _decorate_lazy_media._wm_lazy_decorator = True  # type: ignore[attr-defined]
    _decorate_lazy_media._wm_lazy_original = original  # type: ignore[attr-defined]
    _variant._decorate_editor = _decorate_lazy_media


def install_editor_lazy_media_runtime() -> None:
    if getattr(_variant, "_wm_editor_lazy_media_installed", False):
        return

    _install_preview_items_cache()
    _install_static_primary_gallery()
    _install_lazy_tab_sync()
    _install_editor_postprocess()

    _variant._wm_editor_lazy_media_installed = True
    print(
        "[WM-DBG][TOOLS_EDITOR] lazy tabs + static primary photo aktywne"
    )


__all__ = ["install_editor_lazy_media_runtime"]
