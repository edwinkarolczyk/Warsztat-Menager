# version: 1.0
# Moduł: narzedzia_ui.editor_polish_runtime
# Końcowe dopracowanie nowego edytora Narzędzi bez zmiany modelu danych:
# - wskaźnik niezapisanych zmian jest niewidoczny do pierwszej realnej zmiany,
# - Zapisz jest aktywny tylko przy zmianach,
# - Podgląd jest prostszy i ma przewijalny środek,
# - zadania mają jeden pasek postępu zamiast czterech dużych liczników,
# - etapy są widoczne i klikalne bezpośrednio w Podglądzie,
# - Pliki i zdjęcia pokazują siatkę miniatur zamiast nawigacji strzałkami,
# - okresowy pełny refresh 450 ms jest wyłączony; odświeżanie jest zdarzeniowe.

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from . import editor_variant_runtime as _variant
from . import editor_lazy_media_runtime as _lazy
from . import editor_close_guard_runtime as _close
from . import multistage_runtime as _multistage


def _alive(widget: tk.Misc | None) -> bool:
    try:
        return widget is not None and bool(int(widget.winfo_exists()))
    except Exception:
        return False


def _walk(widget: tk.Misc):
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _walk(child)


def _find_save_button(window: tk.Toplevel) -> ttk.Button | None:
    for widget in _walk(window):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text") or "").strip() == "Zapisz":
                return widget
        except Exception:
            continue
    return None


def _build_dashboard_polished(window, notebook, colors):
    """Podgląd z przewijalnym środkiem i bez czterech dużych liczników."""
    dash = ttk.Frame(notebook, padding=(10, 8), style="WM.Card.TFrame")
    notebook.insert(0, dash, text="Podgląd")
    dash.columnconfigure(0, weight=1)
    dash.rowconfigure(0, weight=1)

    canvas = tk.Canvas(dash, bg=colors["card"], highlightthickness=0, bd=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(dash, orient="vertical", command=canvas.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=scroll.set)

    content = ttk.Frame(canvas, padding=(2, 2, 8, 8), style="WM.Card.TFrame")
    content.columnconfigure(0, weight=3)
    content.columnconfigure(1, weight=2)
    canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

    def _content_changed(_event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    def _canvas_changed(event):
        try:
            canvas.itemconfigure(canvas_window, width=max(1, int(event.width)))
        except Exception:
            pass

    content.bind("<Configure>", _content_changed, add="+")
    canvas.bind("<Configure>", _canvas_changed, add="+")

    def _wheel(event):
        if not _alive(canvas):
            return
        try:
            px, py = window.winfo_pointerxy()
            x0, y0 = canvas.winfo_rootx(), canvas.winfo_rooty()
            x1, y1 = x0 + canvas.winfo_width(), y0 + canvas.winfo_height()
            if not (x0 <= px <= x1 and y0 <= py <= y1):
                return
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                canvas.yview_scroll(-1 if delta > 0 else 1, "units")
        except Exception:
            pass

    try:
        window.bind("<MouseWheel>", _wheel, add="+")
    except Exception:
        pass

    details = _variant._make_card(content, colors, accent=colors["blue"])
    details.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 7))
    details.columnconfigure(1, weight=1)
    tk.Label(
        details,
        text="EDYCJA DANYCH",
        bg=colors["card"],
        fg=colors["blue"],
        font=("Segoe UI", 10, "bold"),
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))

    nr_widget = _variant._clone_basic_field(
        window, details, 1, "Numer", "Numer (3 cyfry)", readonly=True
    )
    name_widget = _variant._clone_basic_field(window, details, 2, "Nazwa", "Nazwa")
    type_widget = _variant._clone_basic_field(window, details, 3, "Typ", "Typ")
    status_widget = _variant._clone_basic_field(window, details, 4, "Status", "Status")

    lifecycle = _variant._make_card(content, colors, accent=colors["blue"])
    lifecycle.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 7))
    tk.Label(
        lifecycle,
        text="WIZYTA / TRYB",
        bg=colors["card"],
        fg=colors["blue"],
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", padx=14, pady=(10, 7))

    # Tryb i status są już widoczne w stałym nagłówku. Widget zostaje tylko
    # dla zgodności z istniejącym mechanizmem synchronizacji.
    mode_line = tk.Label(
        lifecycle,
        text="—",
        bg=colors["card"],
        fg=colors["muted"],
        anchor="w",
    )
    visit_line = tk.Label(
        lifecycle,
        text="Wizyta: —",
        bg=colors["card"],
        fg=colors["muted"],
        justify="left",
        anchor="w",
        font=("Segoe UI", 10),
    )
    visit_line.pack(fill="x", padx=14, pady=(0, 8))

    conversion_source = _variant._find_checkbutton(window, "Przenieś do SN przy zapisie")
    conversion_clone = None
    conversion_var = None
    if conversion_source is not None:
        try:
            variable_name = str(conversion_source.cget("variable") or "").strip()
            conversion_var = (
                tk.BooleanVar(master=window, name=variable_name)
                if variable_name
                else None
            )
        except Exception:
            conversion_var = None
        if conversion_var is not None:
            conversion_clone = ttk.Checkbutton(
                lifecycle,
                text="Przenieś do SN przy zapisie",
                variable=conversion_var,
            )
            conversion_clone.pack(anchor="w", padx=12, pady=(2, 10))
            try:
                if "disabled" in conversion_source.state():
                    conversion_clone.state(["disabled"])
            except Exception:
                pass

    summary = _variant._make_card(content, colors, accent=colors["blue"])
    summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 7))
    summary.columnconfigure(0, weight=1)
    task_line = tk.Label(
        summary,
        text="Zadania: 0/0 wykonane",
        bg=colors["card"],
        fg=colors["text"],
        font=("Segoe UI", 11, "bold"),
        anchor="w",
    )
    task_line.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
    progress = ttk.Progressbar(summary, mode="determinate", maximum=100)
    progress.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
    compact = ttk.Frame(summary, style="WM.TFrame")
    compact.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
    pending_label = ttk.Label(compact, text="Do zrobienia: 0", style="WM.Muted.TLabel")
    pending_label.pack(side="left")
    visits_label = ttk.Label(compact, text="Wizyty: 0", style="WM.Muted.TLabel")
    visits_label.pack(side="left", padx=(22, 0))

    stages = _variant._make_card(content, colors)
    stages.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 7))
    tk.Label(
        stages,
        text="ETAPY NARZĘDZIA",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(9, 4))
    stage_frame = tk.Frame(stages, bg=colors["card"])
    stage_frame.pack(fill="x", padx=12, pady=(0, 10))

    history_card = _variant._make_card(content, colors)
    history_card.grid(row=3, column=0, sticky="nsew", padx=(0, 7), pady=(0, 2))
    tk.Label(
        history_card,
        text="OSTATNIA AKTYWNOŚĆ",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=12, pady=(10, 5))
    history_text = tk.Label(
        history_card,
        text="Brak historii",
        bg=colors["card"],
        fg=colors["text"],
        justify="left",
        anchor="nw",
        wraplength=560,
    )
    history_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    extra_card = _variant._make_card(content, colors)
    extra_card.grid(row=3, column=1, sticky="nsew", padx=(7, 0), pady=(0, 2))
    tk.Label(
        extra_card,
        text="INFORMACJE",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=12, pady=(10, 5))
    extra_text = tk.Label(
        extra_card,
        text="—",
        bg=colors["card"],
        fg=colors["text"],
        justify="left",
        anchor="nw",
        wraplength=480,
    )
    extra_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    dash._wm_nr_widget = nr_widget
    dash._wm_name_widget = name_widget
    dash._wm_type_widget = type_widget
    dash._wm_status_widget = status_widget
    dash._wm_mode_line = mode_line
    dash._wm_visit_line = visit_line
    dash._wm_stat_labels = []
    dash._wm_history_text = history_text
    dash._wm_extra_text = extra_text
    dash._wm_conversion_clone = conversion_clone
    dash._wm_conversion_var = conversion_var
    dash._wm_polish_canvas = canvas
    dash._wm_task_line = task_line
    dash._wm_task_progress = progress
    dash._wm_pending_label = pending_label
    dash._wm_visits_label = visits_label
    dash._wm_stage_frame = stage_frame
    return dash


def _refresh_stage_strip(window, dashboard):
    stage_frame = getattr(dashboard, "_wm_stage_frame", None)
    if stage_frame is None or not _alive(stage_frame):
        return
    nr = _multistage._current_nr(window)
    group = _multistage._group_for(_multistage._read_relations(), nr)
    tools = (
        tuple(_multistage._norm_nr(x) for x in group.get("tools", []))
        if group is not None
        else ()
    )
    signature = (nr, tools)
    if getattr(dashboard, "_wm_stage_signature", None) == signature:
        return

    for child in list(stage_frame.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    colors = _variant._palette()
    if not tools:
        tk.Label(
            stage_frame,
            text="Brak powiązań etapowych",
            bg=colors["card"],
            fg=colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side="left")
    else:
        for index, tool_nr in enumerate(tools):
            if index:
                tk.Label(
                    stage_frame,
                    text="→",
                    bg=colors["card"],
                    fg=colors["muted"],
                    font=("Segoe UI", 12, "bold"),
                ).pack(side="left", padx=5)
            if tool_nr == nr:
                tk.Label(
                    stage_frame,
                    text=tool_nr,
                    bg=colors["blue"],
                    fg="#ffffff",
                    font=("Segoe UI", 10, "bold"),
                    padx=8,
                    pady=3,
                ).pack(side="left")
            else:
                ttk.Button(
                    stage_frame,
                    text=tool_nr,
                    command=lambda value=tool_nr: _multistage._open_tool(value),
                    style="WM.Side.TButton",
                    width=5,
                ).pack(side="left")
    dashboard._wm_stage_signature = signature


def _install_dashboard_sync():
    current = getattr(_lazy, "_sync_dashboard", None)
    if not callable(current) or getattr(current, "_wm_polish_dashboard", False):
        return
    original = current

    def _sync_dashboard_polished(window, header, dashboard, colors, status, mode):
        original(window, header, dashboard, colors, status, mode)
        try:
            doc = _variant._current_doc(window)
            total, done, pending = _variant._task_counts(window, doc)
            visit_count, _open, _start, _by = _variant._visit_stats(doc)
            percent = (
                0
                if total <= 0
                else max(0, min(100, int(round(done * 100 / total))))
            )
            dashboard._wm_task_line.configure(
                text=(
                    "Zadania: brak"
                    if total <= 0
                    else f"Zadania: {done}/{total} wykonane  •  {percent}%"
                )
            )
            dashboard._wm_task_progress.configure(value=percent)
            dashboard._wm_pending_label.configure(text=f"Do zrobienia: {pending}")
            dashboard._wm_visits_label.configure(text=f"Wizyty: {visit_count}")
        except Exception:
            pass
        try:
            _refresh_stage_strip(window, dashboard)
        except Exception as exc:
            print(
                "[WM-ERR][TOOLS_EDITOR][POLISH][STAGES] "
                f"{type(exc).__name__}: {exc}"
            )

    _sync_dashboard_polished._wm_polish_dashboard = True
    _sync_dashboard_polished._wm_polish_original = original
    _lazy._sync_dashboard = _sync_dashboard_polished


def _hide_old_gallery_nav(media_tab):
    previous = getattr(media_tab, "_wm_gallery_previous", None)
    dots = getattr(media_tab, "_wm_gallery_dots", None)
    nav = getattr(previous, "master", None) if previous is not None else None
    try:
        if nav is not None:
            nav.pack_forget()
    except Exception:
        pass
    try:
        if dots is not None:
            dots.pack_forget()
    except Exception:
        pass


def _ensure_thumbnail_area(media_tab):
    existing = getattr(media_tab, "_wm_polish_thumb_inner", None)
    if existing is not None and _alive(existing):
        return existing
    large = getattr(media_tab, "_wm_thumb", None)
    left = getattr(large, "master", None) if large is not None else None
    if left is None:
        return None

    _hide_old_gallery_nav(media_tab)
    holder = ttk.Frame(left, style="WM.TFrame")
    try:
        holder.pack(fill="x", padx=14, pady=(0, 8), after=large)
    except Exception:
        holder.pack(fill="x", padx=14, pady=(0, 8))

    canvas = tk.Canvas(
        holder,
        height=145,
        bg=_variant._palette()["card"],
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    scroll.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scroll.set)
    inner = tk.Frame(canvas, bg=_variant._palette()["card"])
    item = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind(
        "<Configure>",
        lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        add="+",
    )
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfigure(item, width=max(1, int(e.width))),
        add="+",
    )
    media_tab._wm_polish_thumb_inner = inner
    media_tab._wm_polish_thumb_canvas = canvas
    return inner


def _refresh_thumbnail_grid(window, media_tab):
    if not _alive(media_tab):
        return
    inner = _ensure_thumbnail_area(media_tab)
    if inner is None:
        return
    try:
        items = list(_variant._preview_items(window))
    except Exception:
        items = []

    image_items = [
        (all_index, raw, Path(path))
        for all_index, (raw, path, kind) in enumerate(items)
        if kind == "image"
    ]
    try:
        selected = _variant._gallery_index(window, len(items)) if items else 0
    except Exception:
        selected = 0

    signature = tuple((idx, str(path)) for idx, _raw, path in image_items)
    render_key = (signature, selected)
    if getattr(media_tab, "_wm_polish_thumb_key", None) == render_key:
        return

    for child in list(inner.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    colors = _variant._palette()
    if not image_items:
        tk.Label(
            inner,
            text="Brak zdjęć. Użyj „Dodaj zdjęcia”.",
            bg=colors["card"],
            fg=colors["muted"],
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=8)
        media_tab._wm_polish_thumb_key = render_key
        return

    columns = 4
    for col in range(columns):
        inner.columnconfigure(col, weight=1, uniform="thumbs")

    def _select(index):
        try:
            _variant._set_gallery_index(window, index)
            _variant._refresh_gallery_views(window, None, media_tab)
        except Exception:
            pass
        media_tab._wm_polish_thumb_key = None
        _refresh_thumbnail_grid(window, media_tab)

    def _set_primary(index):
        _select(index)
        try:
            _variant._set_current_image_as_primary(window)
        finally:
            media_tab._wm_polish_thumb_key = None
            window.after_idle(lambda: _refresh_thumbnail_grid(window, media_tab))
            _schedule_dirty(window)

    def _remove(index):
        _select(index)
        try:
            _variant._remove_current_image(window)
        finally:
            media_tab._wm_polish_thumb_key = None
            window.after_idle(lambda: _refresh_thumbnail_grid(window, media_tab))
            _schedule_dirty(window)

    def _open(index):
        _select(index)
        try:
            _variant._open_full_preview(window)
        except Exception:
            pass

    def _menu(event, index):
        menu = tk.Menu(window, tearoff=False)
        menu.add_command(
            label="Ustaw jako główne", command=lambda: _set_primary(index)
        )
        menu.add_command(label="Usuń zdjęcie", command=lambda: _remove(index))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    for pos, (all_index, _raw, path) in enumerate(image_items):
        chosen = all_index == selected
        card = tk.Frame(
            inner,
            bg=colors["panel"],
            highlightthickness=2 if chosen else 1,
            highlightbackground=colors["blue"] if chosen else colors["line"],
            bd=0,
            cursor="hand2",
        )
        card.grid(
            row=pos // columns,
            column=pos % columns,
            sticky="nsew",
            padx=4,
            pady=4,
        )
        photo = _variant._load_photo(path, card, (105, 70))
        image = tk.Label(
            card,
            image=photo if photo is not None else "",
            text="" if photo is not None else "Brak\npodglądu",
            bg=colors["panel"],
            fg=colors["muted"],
            justify="center",
            width=0 if photo is not None else 14,
            height=0 if photo is not None else 4,
            cursor="hand2",
        )
        image.pack(fill="both", expand=True, padx=3, pady=(3, 1))
        image._wm_polish_photo = photo
        caption = tk.Label(
            card,
            text="★ GŁÓWNE" if pos == 0 else f"Zdjęcie {pos + 1}",
            bg=colors["panel"],
            fg=colors["blue"] if pos == 0 else colors["muted"],
            font=("Segoe UI", 8, "bold" if pos == 0 else "normal"),
            cursor="hand2",
        )
        caption.pack(fill="x", padx=3, pady=(0, 3))
        for target in (card, image, caption):
            target.bind(
                "<Button-1>", lambda _e, index=all_index: _select(index)
            )
            target.bind(
                "<Double-Button-1>", lambda _e, index=all_index: _open(index)
            )
            target.bind(
                "<Button-3>", lambda e, index=all_index: _menu(e, index)
            )

    media_tab._wm_polish_thumb_key = render_key


def _install_media_sync():
    current = getattr(_lazy, "_sync_media", None)
    if not callable(current) or getattr(current, "_wm_polish_media", False):
        return
    original = current

    def _sync_media_polished(window, media_tab):
        original(window, media_tab)
        _refresh_thumbnail_grid(window, media_tab)

    _sync_media_polished._wm_polish_media = True
    _sync_media_polished._wm_polish_original = original
    _lazy._sync_media = _sync_media_polished


def _dirty_now(window):
    baseline = getattr(window, "_wm_close_saved_snapshot", None)
    if baseline is None:
        return False
    try:
        return _close._snapshot(window) != baseline
    except Exception:
        return True


def _paint_dirty(window):
    if not _alive(window):
        return
    label = getattr(window, "_wm_polish_dirty_label", None)
    save = getattr(window, "_wm_polish_save_button", None)
    if label is None or save is None:
        return

    dirty = _dirty_now(window)
    previous = bool(getattr(window, "_wm_polish_dirty", False))
    if dirty == previous and getattr(window, "_wm_polish_dirty_painted", False):
        return

    try:
        if dirty:
            if not label.winfo_manager():
                label.pack(side="left", padx=(8, 0), pady=2)
            save.state(["!disabled"])
        else:
            label.pack_forget()
            save.state(["disabled"])
        window._wm_polish_dirty = dirty
        window._wm_polish_dirty_painted = True
    except Exception:
        pass


def _schedule_dirty(window, delay_ms=90):
    if not _alive(window):
        return
    old = getattr(window, "_wm_polish_dirty_job", None)
    if old:
        try:
            window.after_cancel(old)
        except Exception:
            pass

    def _run():
        window._wm_polish_dirty_job = None
        _paint_dirty(window)

    try:
        window._wm_polish_dirty_job = window.after(delay_ms, _run)
    except Exception:
        pass


def _setup_dirty_indicator(window):
    if getattr(window, "_wm_polish_dirty_ready", False):
        return
    footer = _close._find_footer(window)
    save = _find_save_button(window)
    if footer is None or save is None:
        return

    colors = _variant._palette()
    label = tk.Label(
        footer,
        text="● Niezapisane zmiany",
        bg=colors.get("panel", colors["card"]),
        fg=colors["warning"],
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    )

    try:
        window._wm_close_saved_snapshot = _close._snapshot(window)
        window._wm_polish_dirty_label = label
        window._wm_polish_save_button = save
        window._wm_polish_dirty = False
        window._wm_polish_dirty_painted = False
        window._wm_polish_dirty_ready = True
    except Exception:
        return

    _paint_dirty(window)

    def _dirty_only(_event=None):
        _schedule_dirty(window)

    for sequence in (
        "<KeyRelease>",
        "<ButtonRelease-1>",
        "<<ComboboxSelected>>",
        "<<ToolMediaChanged>>",
        "<<ToolSaved>>",
    ):
        try:
            window.bind(sequence, _dirty_only, add="+")
        except Exception:
            pass


def _install_save_dirty_reset():
    current = getattr(_close, "_wrap_save_button", None)
    if not callable(current) or getattr(current, "_wm_polish_save_reset", False):
        return
    original = current

    def _wrap_save_button_polished(dlg):
        original(dlg)
        button = _find_save_button(dlg)
        if button is None or getattr(button, "_wm_polish_save_wrapped", False):
            return
        try:
            command_name = str(button.cget("command") or "").strip()
        except Exception:
            command_name = ""
        if not command_name:
            return

        def _invoke(btn=button, command=command_name, window=dlg):
            try:
                return btn.tk.call(command)
            finally:
                try:
                    window.after(25, lambda: _paint_dirty(window))
                except Exception:
                    pass

        try:
            button.configure(command=_invoke)
            button._wm_polish_save_wrapped = True
        except Exception:
            pass

    _wrap_save_button_polished._wm_polish_save_reset = True
    _wrap_save_button_polished._wm_polish_original = original
    _close._wrap_save_button = _wrap_save_button_polished


def _cancel_periodic_refresh(window):
    refresh = getattr(window, "_wm_editor_variant_refresh_job", None)
    if not isinstance(refresh, dict):
        return
    job = refresh.get("id")
    if job:
        try:
            window.after_cancel(job)
        except Exception:
            pass
    refresh["id"] = None


def _selected_refresh(window):
    if not _alive(window):
        return
    try:
        _main, header, notebook = _variant._editor_parts(window)
        if header is None or notebook is None:
            return
        dashboard = _variant._tab_by_text(notebook, "Podgląd")
        media = _variant._tab_by_text(notebook, "Pliki i zdjęcia")
        if dashboard is None or media is None:
            return
        _variant._sync_new_view(
            window,
            header,
            dashboard,
            media,
            _variant._palette(),
        )
    except Exception as exc:
        print(
            "[WM-ERR][TOOLS_EDITOR][POLISH][REFRESH] "
            f"{type(exc).__name__}: {exc}"
        )


def _install_event_refresh(window):
    if getattr(window, "_wm_polish_events_ready", False):
        return
    try:
        _main, _header, notebook = _variant._editor_parts(window)
    except Exception:
        notebook = None
    if notebook is None:
        return

    state = {"job": None}

    def _schedule(_event=None, delay=0):
        old = state.get("job")
        if old:
            try:
                window.after_cancel(old)
            except Exception:
                pass

        def _run():
            state["job"] = None
            _selected_refresh(window)

        try:
            state["job"] = window.after(delay, _run)
        except Exception:
            state["job"] = None

    try:
        notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _e: _schedule(delay=0),
            add="+",
        )
    except Exception:
        pass

    for sequence in (
        "<<ToolMediaChanged>>",
        "<<ToolSaved>>",
        "<<ComboboxSelected>>",
    ):
        try:
            window.bind(sequence, lambda _e, s=_schedule: s(delay=0), add="+")
        except Exception:
            pass

    # Nie wracamy do pełnego sync na każde kliknięcie okna. Reagujemy tylko
    # na przyciski, które mogą realnie zmienić dane/zadania.
    for widget in list(_walk(window)):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            widget.bind(
                "<ButtonRelease-1>",
                lambda _e, s=_schedule: s(delay=0),
                add="+",
            )
        except Exception:
            pass

    window._wm_polish_events_ready = True


def _install_relation_refresh_event():
    current = getattr(_multistage, "_relation_editor", None)
    if not callable(current) or getattr(current, "_wm_polish_relation_refresh", False):
        return
    original = current

    def _relation_editor_polished(window, on_saved):
        def _saved():
            on_saved()
            try:
                _main, _header, notebook = _variant._editor_parts(window)
                dashboard = (
                    _variant._tab_by_text(notebook, "Podgląd")
                    if notebook is not None
                    else None
                )
                if dashboard is not None:
                    dashboard._wm_stage_signature = None
                    _refresh_stage_strip(window, dashboard)
            except Exception:
                pass

        return original(window, _saved)

    _relation_editor_polished._wm_polish_relation_refresh = True
    _relation_editor_polished._wm_polish_original = original
    _multistage._relation_editor = _relation_editor_polished


def _install_responsive_fit():
    current = getattr(_variant, "_fit_window", None)
    if not callable(current) or getattr(current, "_wm_polish_responsive", False):
        return

    def _fit_responsive(window):
        try:
            sw = max(800, int(window.winfo_screenwidth()))
            sh = max(600, int(window.winfo_screenheight()))
            width = min(1420, max(760, sw - 40))
            height = min(920, max(560, sh - 70))
            x = max(0, (sw - width) // 2)
            y = max(0, (sh - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
            window.minsize(min(980, width), min(560, height))
        except Exception:
            pass

    _fit_responsive._wm_polish_responsive = True
    _fit_responsive._wm_polish_original = current
    _variant._fit_window = _fit_responsive


def _install_editor_postprocess():
    current = getattr(_variant, "_decorate_editor", None)
    if not callable(current) or getattr(current, "_wm_polish_decorator", False):
        return
    original = current

    def _decorate_polished(window):
        result = original(window)
        if not result or getattr(window, "_wm_editor_polish_ready", False):
            return result

        _cancel_periodic_refresh(window)
        try:
            _main, _header, notebook = _variant._editor_parts(window)
            media = (
                _variant._tab_by_text(notebook, "Pliki i zdjęcia")
                if notebook is not None
                else None
            )
            if media is not None:
                _ensure_thumbnail_area(media)
        except Exception:
            pass

        _install_event_refresh(window)
        _setup_dirty_indicator(window)
        window._wm_editor_polish_ready = True
        print(
            "[WM-DBG][TOOLS_EDITOR] polish: dirty-on-demand + progress + stages "
            "+ thumbnails + event refresh aktywne"
        )
        return result

    _decorate_polished._wm_polish_decorator = True
    _decorate_polished._wm_polish_original = original
    _variant._decorate_editor = _decorate_polished


def install_editor_polish_runtime():
    if getattr(_variant, "_wm_editor_polish_installed", False):
        return

    _variant._build_dashboard = _build_dashboard_polished
    _install_dashboard_sync()
    _install_media_sync()
    _install_save_dirty_reset()
    _install_relation_refresh_event()
    _install_responsive_fit()
    _install_editor_postprocess()

    _variant._wm_editor_polish_installed = True
    print("[WM-DBG][TOOLS_EDITOR] końcowe dopracowanie edytora aktywne")


__all__ = ["install_editor_polish_runtime"]
