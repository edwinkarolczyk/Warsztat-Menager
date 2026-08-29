# version: 1.0
# Moduł: narzedzia_ui.editor_header_info_runtime
# - Nagłówek korzysta z tych samych żywych wartości co karta Podgląd.
# - Kanoniczny numer narzędzia ma pierwszeństwo przed placeholderem.
# - Zakładka "Opis" zmienia się na "Informacje" bez zmiany modelu danych.
# - Istniejące pole "opis" dostaje czytelniejszy układ i podpowiedź.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant
from . import editor_lazy_media_runtime as _lazy


def _widget_value(widget):
    if widget is None:
        return ""
    getter = getattr(widget, "get", None)
    if not callable(getter):
        return ""
    try:
        return str(getter() or "").strip()
    except Exception:
        return ""


def _dashboard(window):
    try:
        _main, _header, notebook = _variant._editor_parts(window)
    except Exception:
        return None
    if notebook is None:
        return None
    try:
        return _variant._tab_by_text(notebook, "Podgląd")
    except Exception:
        return None


def _dashboard_field(window, attr):
    dash = _dashboard(window)
    if dash is None:
        return ""
    return _widget_value(getattr(dash, attr, None))


def _norm_three(value):
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


def _install_live_header_source():
    current = getattr(_lazy, "_paint_light_header", None)
    if not callable(current) or getattr(current, "_wm_live_header_source", False):
        return
    original = current

    def _paint_light_header_live(window, header, colors):
        nr_old, name_old, type_old, status_old, mode = original(window, header, colors)

        nr = (
            _norm_three(getattr(window, "_wm_tool_number", ""))
            or _norm_three(_dashboard_field(window, "_wm_nr_widget"))
            or _norm_three(nr_old)
            or "---"
        )
        name = (
            _dashboard_field(window, "_wm_name_widget")
            or ("" if name_old == "Bez nazwy" else str(name_old or "").strip())
            or "Bez nazwy"
        )
        tool_type = (
            _dashboard_field(window, "_wm_type_widget")
            or ("" if type_old == "—" else str(type_old or "").strip())
            or "—"
        )
        status = (
            _dashboard_field(window, "_wm_status_widget")
            or ("" if status_old == "—" else str(status_old or "").strip())
            or "—"
        )

        if header is not None:
            try:
                header._wm_number_badge.configure(text=f"#{nr}")  # type: ignore[attr-defined]
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

        if nr != "---":
            try:
                window._wm_tool_number = nr  # type: ignore[attr-defined]
            except Exception:
                pass

        return nr, name, tool_type, status, mode

    _paint_light_header_live._wm_live_header_source = True  # type: ignore[attr-defined]
    _paint_light_header_live._wm_live_header_original = original  # type: ignore[attr-defined]
    _lazy._paint_light_header = _paint_light_header_live


def _find_text_widget(tab):
    try:
        descendants = _variant._all_descendants(tab)
    except Exception:
        descendants = []
    for widget in descendants:
        if isinstance(widget, tk.Text):
            return widget
    return None


def _find_heading(tab):
    try:
        descendants = _variant._all_descendants(tab)
    except Exception:
        descendants = []
    for widget in descendants:
        if not isinstance(widget, (tk.Label, ttk.Label)):
            continue
        try:
            text = str(widget.cget("text") or "").strip()
        except Exception:
            continue
        if text in {"Opis narzędzia", "Opis", "OPIS NARZĘDZIA"}:
            return widget
    return None


def _decorate_information_tab(window, notebook):
    tab = _variant._tab_by_text(notebook, "Informacje")
    if tab is None or getattr(tab, "_wm_information_ready", False):
        return

    text_widget = _find_text_widget(tab)
    heading = _find_heading(tab)
    colors = _variant._palette()

    if heading is not None:
        try:
            heading.configure(text="OPIS I UWAGI")
        except Exception:
            pass

    if text_widget is not None:
        try:
            text_widget.configure(
                font=("Segoe UI", 11),
                bg=colors["panel"],
                fg=colors["text"],
                insertbackground=colors["text"],
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=colors["line"],
                highlightcolor=colors["blue"],
                padx=12,
                pady=10,
            )
        except Exception:
            pass

        body = getattr(text_widget, "master", None)
        parent = getattr(body, "master", None)
        if isinstance(parent, tk.Misc) and isinstance(body, tk.Misc):
            helper = tk.Label(
                parent,
                text=(
                    "Zapisz tu zastosowanie narzędzia, ważne ustawienia, "
                    "ograniczenia i uwagi dla kolejnej osoby."
                ),
                bg=colors["card"],
                fg=colors["muted"],
                font=("Segoe UI", 9),
                justify="left",
                anchor="w",
            )
            try:
                helper.pack(fill="x", anchor="w", pady=(2, 8), before=body)
            except Exception:
                try:
                    helper.pack(fill="x", anchor="w", pady=(2, 8))
                except Exception:
                    pass

    try:
        tab._wm_information_ready = True  # type: ignore[attr-defined]
    except Exception:
        pass


def _install_information_tab():
    current = getattr(_variant, "_rename_tabs", None)
    if not callable(current) or getattr(current, "_wm_information_tab", False):
        return
    original = current

    def _rename_tabs_information(notebook):
        original(notebook)

        for tab_id in notebook.tabs():
            try:
                text = str(notebook.tab(tab_id, "text") or "").strip()
            except Exception:
                continue
            if text in {"Opis", "Opis narzędzia"}:
                try:
                    notebook.tab(tab_id, text="Informacje")
                except Exception:
                    pass
                break

        try:
            top = notebook.winfo_toplevel()
        except Exception:
            top = None
        if isinstance(top, tk.Toplevel):
            _decorate_information_tab(top, notebook)

    _rename_tabs_information._wm_information_tab = True  # type: ignore[attr-defined]
    _rename_tabs_information._wm_information_original = original  # type: ignore[attr-defined]
    _variant._rename_tabs = _rename_tabs_information


def install_editor_header_info_runtime():
    if getattr(_variant, "_wm_editor_header_info_installed", False):
        return

    _install_live_header_source()
    _install_information_tab()

    _variant._wm_editor_header_info_installed = True
    print("[WM-DBG][TOOLS_EDITOR] live header + Informacje aktywne")


__all__ = ["install_editor_header_info_runtime"]
