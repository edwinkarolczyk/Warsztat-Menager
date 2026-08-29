# version: 3.0
# Moduł: narzedzia_ui.editor_variant_runtime
# Nowy widok edytora NN/SN. Klasyczny edytor pozostaje bez zmian.
# 3.0: galeria wielu zdjęć z automatyczną karuzelą, nawigacją i podglądem pełnym.
# 2.0: pełna karta narzędzia: miniatura, kolorowe statusy, dashboard,
#      edycja danych podstawowych, statystyki zadań/wizyt, historia i pliki.

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable
import tkinter as tk
from tkinter import messagebox, ttk


_LOGGER = logging.getLogger(__name__)


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}

_FALLBACK_PALETTE = {
    "bg": "#111214",
    "card": "#202226",
    "panel": "#1a1c1f",
    "text": "#e6e6e6",
    "muted": "#a9abb3",
    "line": "#34373d",
    "accent": "#d43c3c",
    "success": "#29a36a",
    "warning": "#d69d2b",
    "error": "#e05555",
    "blue": "#3b82f6",
    "purple": "#8b5cf6",
}


def _palette() -> dict[str, str]:
    out = dict(_FALLBACK_PALETTE)
    try:
        from ui_theme import _ACTIVE_PALETTE  # type: ignore

        active = dict(_ACTIVE_PALETTE or {})
        out.update(
            {
                "bg": active.get("bg", out["bg"]),
                "card": active.get("card", out["card"]),
                "panel": active.get("bg_alt", out["panel"]),
                "text": active.get("fg", out["text"]),
                "muted": active.get("fg_dim", out["muted"]),
                "line": active.get("border", out["line"]),
                "accent": active.get("accent", out["accent"]),
                "success": active.get("success", out["success"]),
                "warning": active.get("warning", out["warning"]),
                "error": active.get("error", out["error"]),
            }
        )
    except Exception:
        pass
    return out


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _widget_text(widget: tk.Misc) -> str:
    try:
        text = widget.cget("text")
        if text:
            return str(text).strip()
    except Exception:
        pass
    try:
        variable = str(widget.cget("textvariable") or "").strip()
        if variable:
            return str(widget.getvar(variable) or "").strip()
    except Exception:
        pass
    return ""


def _new_variant_enabled() -> bool:
    try:
        from config_manager import ConfigManager

        raw = str(ConfigManager().get("tools.editor_variant", "classic") or "classic")
    except Exception:
        raw = "classic"
    return raw.strip().lower() in {"card", "new", "nowy", "nowa"}


def _editor_parts(window: tk.Toplevel):
    notebook = next(
        (item for item in _all_descendants(window) if isinstance(item, ttk.Notebook)),
        None,
    )
    if notebook is None:
        return None, None, None
    main = getattr(notebook, "master", None)
    header = None
    if main is not None:
        try:
            for child in main.winfo_children():
                if child is notebook:
                    continue
                if isinstance(child, ttk.Frame):
                    header = child
                    break
        except Exception:
            pass
    return main, header, notebook


def _tab_by_text(notebook: ttk.Notebook, title: str) -> tk.Misc | None:
    wanted = title.strip().lower()
    try:
        for tab_id in notebook.tabs():
            if str(notebook.tab(tab_id, "text") or "").strip().lower() == wanted:
                return notebook.nametowidget(tab_id)
    except Exception:
        pass
    return None


def _field_row(window: tk.Toplevel, label_text: str):
    wanted = label_text.strip().lower()
    for label in _all_descendants(window):
        if not isinstance(label, ttk.Label):
            continue
        if _widget_text(label).strip().lower() != wanted:
            continue
        parent = getattr(label, "master", None)
        if parent is None:
            continue
        try:
            info = label.grid_info()
            row = int(info.get("row", -1))
        except Exception:
            continue
        for sibling in parent.winfo_children():
            if sibling is label:
                continue
            try:
                sinfo = sibling.grid_info()
                if int(sinfo.get("row", -2)) == row and int(sinfo.get("column", -1)) == 1:
                    return label, sibling
            except Exception:
                continue
        return label, None
    return None, None


def _field_value_widget(window: tk.Toplevel, label_text: str) -> tk.Misc | None:
    _label, holder = _field_row(window, label_text)
    return holder


def _first_entry(holder: tk.Misc | None):
    if holder is None:
        return None
    widgets = [holder, *_all_descendants(holder)]
    return next(
        (
            item
            for item in widgets
            if isinstance(item, (ttk.Entry, ttk.Combobox, tk.Entry))
        ),
        None,
    )


def _first_combo(holder: tk.Misc | None):
    if holder is None:
        return None
    widgets = [holder, *_all_descendants(holder)]
    return next((item for item in widgets if isinstance(item, ttk.Combobox)), None)


def _entry_value_from_field(window: tk.Toplevel, label_text: str) -> str:
    widget = _first_entry(_field_value_widget(window, label_text))
    if widget is None:
        return ""
    try:
        return str(widget.get() or "").strip()
    except Exception:
        return ""


def _holder_label_value(holder: tk.Misc | None) -> str:
    if holder is None:
        return ""
    for widget in _all_descendants(holder):
        if isinstance(widget, ttk.Label):
            text = _widget_text(widget)
            if text:
                return text
    return ""


def _images_summary(values: list[str]) -> str:
    names = [
        Path(str(value).replace("\\", "/")).name
        for value in values
        if str(value or "").strip()
    ]
    if not names:
        return "—"
    if len(names) <= 3:
        return ", ".join(names)
    return f"{len(names)} plików"


def _added_date(doc: dict[str, Any] | None) -> str:
    if not isinstance(doc, dict):
        return "—"
    return str(
        doc.get("data_dodania")
        or doc.get("data")
        or doc.get("date_added")
        or "—"
    )


def _hide_grid(widget: tk.Misc | None) -> None:
    if widget is None:
        return
    try:
        widget.grid_remove()
    except Exception:
        pass


def _hide_field_row(window: tk.Toplevel, label_text: str) -> None:
    label, holder = _field_row(window, label_text)
    _hide_grid(label)
    _hide_grid(holder)


def _find_checkbutton(window: tk.Toplevel, text: str) -> ttk.Checkbutton | None:
    wanted = text.strip().lower()
    for widget in _all_descendants(window):
        if not isinstance(widget, ttk.Checkbutton):
            continue
        try:
            if str(widget.cget("text") or "").strip().lower() == wanted:
                return widget
        except Exception:
            continue
    return None


def _find_button(holder: tk.Misc | None, text: str) -> ttk.Button | None:
    if holder is None:
        return None
    wanted = text.strip().lower()
    for widget in [holder, *_all_descendants(holder)]:
        if not isinstance(widget, ttk.Button):
            continue
        try:
            if str(widget.cget("text") or "").strip().lower() == wanted:
                return widget
        except Exception:
            continue
    return None


def _shared_var(window: tk.Toplevel, widget: tk.Misc | None) -> tk.StringVar | None:
    if widget is None:
        return None
    try:
        name = str(widget.cget("textvariable") or "").strip()
    except Exception:
        name = ""
    if not name:
        return None
    try:
        return tk.StringVar(master=window, name=name)
    except Exception:
        return None


def _candidate_path(base: Path, raw: str) -> Path | None:
    cleaned = str(raw or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned.replace("\\", os.sep).replace("/", os.sep))
    if candidate.is_absolute() and candidate.is_file():
        return candidate
    for value in (base / candidate, base / "media" / candidate.name):
        try:
            if value.is_file():
                return value
        except Exception:
            continue
    return None


def _current_doc(window: tk.Toplevel) -> dict[str, Any]:
    nr = _entry_value_from_field(window, "Numer (3 cyfry)")
    if not nr:
        return {}
    try:
        import gui_narzedzia as tools_gui

        value = tools_gui._read_tool(nr) or {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _media_base() -> Path | None:
    try:
        import gui_narzedzia as tools_gui

        return Path(tools_gui._resolve_tools_dir())
    except Exception:
        return None


def _image_values(window: tk.Toplevel, doc: dict[str, Any] | None = None) -> list[str]:
    """Return the current form images; use JSON only outside the editor form."""

    live_getter = getattr(window, "_wm_tool_images_get", None)
    if callable(live_getter):
        try:
            live_values = live_getter()
        except Exception:
            _LOGGER.exception("[TOOLS_EDITOR] Nie udało się odczytać bieżącej listy zdjęć")
            live_values = []
        if not isinstance(live_values, (list, tuple)):
            return []
        return [str(item).strip() for item in live_values if str(item or "").strip()]

    if doc is None:
        doc = _current_doc(window)
    candidates: list[str] = []
    images = doc.get("obrazy")
    if isinstance(images, list):
        candidates.extend(str(item) for item in images if str(item or "").strip())
    elif isinstance(images, str) and images.strip():
        candidates.append(images.strip())
    legacy = doc.get("obraz")
    if isinstance(legacy, str) and legacy.strip() and legacy.strip() not in candidates:
        candidates.append(legacy.strip())
    return candidates


def _preview_items(window: tk.Toplevel) -> list[tuple[str, Path, str]]:
    """Return (stored value, resolved path, kind) for the live gallery."""

    base = _media_base()
    if base is None:
        return []
    live_getter = getattr(window, "_wm_tool_images_get", None)
    dxf_getter = getattr(window, "_wm_tool_dxf_preview_get", None)
    doc = (
        {}
        if callable(live_getter) and callable(dxf_getter)
        else _current_doc(window)
    )
    result: list[tuple[str, Path, str]] = []
    seen: set[str] = set()

    for raw in _image_values(window, doc):
        resolved = _candidate_path(base, raw)
        if resolved is None:
            candidate = Path(str(raw).replace("\\", os.sep).replace("/", os.sep))
            resolved = candidate if candidate.is_absolute() else base / candidate
            kind = "missing_image"
        else:
            kind = "image"
        token = os.path.normcase(os.path.abspath(str(resolved)))
        if token in seen:
            continue
        seen.add(token)
        result.append((raw, resolved, kind))

    # Zachowaj dotychczasowe zachowanie: gdy nie ma zdjęcia, pokaż miniaturę DXF.
    if not result:
        if callable(dxf_getter):
            try:
                dxf_png = str(dxf_getter() or "").strip()
            except Exception:
                dxf_png = ""
        else:
            dxf_png = str(doc.get("dxf_png") or "").strip()
        if dxf_png:
            resolved = _candidate_path(base, dxf_png)
            if resolved is not None:
                result.append((dxf_png, resolved, "dxf"))
    return result


def _gallery_index(window: tk.Toplevel, count: int | None = None) -> int:
    if count is None:
        count = len(_preview_items(window))
    if count <= 0:
        index = 0
    else:
        try:
            index = int(getattr(window, "_wm_editor_gallery_index", 0) or 0) % count
        except (TypeError, ValueError):
            index = 0
    try:
        window._wm_editor_gallery_index = index  # type: ignore[attr-defined]
    except Exception:
        pass
    return index


def _set_gallery_index(window: tk.Toplevel, index: int) -> int:
    count = len(_preview_items(window))
    value = int(index) % count if count else 0
    try:
        window._wm_editor_gallery_index = value  # type: ignore[attr-defined]
    except Exception:
        pass
    return value


def _step_gallery(window: tk.Toplevel, delta: int) -> int:
    count = len(_preview_items(window))
    return _set_gallery_index(window, _gallery_index(window, count) + int(delta))


def _current_preview_item(window: tk.Toplevel) -> tuple[str, Path, str] | None:
    items = _preview_items(window)
    if not items:
        return None
    return items[_gallery_index(window, len(items))]


def _preview_path(window: tk.Toplevel) -> Path | None:
    current = _current_preview_item(window)
    if current is not None:
        return current[1]
    return None


def _load_photo(path: Path, master: tk.Misc, max_size: tuple[int, int]):
    pil_error: Exception | None = None
    try:
        from PIL import Image, ImageOps, ImageTk

        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).copy()
        image.thumbnail(max_size)
        return ImageTk.PhotoImage(image, master=master)
    except Exception as exc:
        pil_error = exc

    try:
        photo = tk.PhotoImage(master=master, file=str(path))
        width = max(1, int(photo.width()))
        height = max(1, int(photo.height()))
        sx = max(1, (width + max_size[0] - 1) // max_size[0])
        sy = max(1, (height + max_size[1] - 1) // max_size[1])
        factor = max(sx, sy)
        return photo.subsample(factor, factor) if factor > 1 else photo
    except Exception as tk_error:
        _LOGGER.warning(
            "[TOOLS_EDITOR] Nie można wczytać obrazu %s (Pillow: %s; Tk: %s)",
            path,
            pil_error,
            tk_error,
        )
        return None


def _refresh_thumbnail(
    window: tk.Toplevel,
    label: tk.Label | ttk.Label,
    size: tuple[int, int] = (240, 180),
) -> None:
    try:
        if not window.winfo_exists() or not label.winfo_exists():
            return
    except Exception:
        return

    path = _preview_path(window)
    if path is None:
        try:
            label.configure(image="", text="Brak zdjęcia\nnarzędzia", justify="center")
            label._wm_editor_photo = None  # type: ignore[attr-defined]
            label._wm_editor_path = None  # type: ignore[attr-defined]
        except Exception:
            pass
        return

    photo = _load_photo(path, label, size)
    if photo is None:
        try:
            label.configure(image="", text="Nie można wyświetlić\nminiatury", justify="center")
            label._wm_editor_photo = None  # type: ignore[attr-defined]
            label._wm_editor_path = str(path)  # type: ignore[attr-defined]
        except Exception:
            pass
        return

    try:
        label.configure(image=photo, text="")
        label._wm_editor_photo = photo  # type: ignore[attr-defined]
        label._wm_editor_path = str(path)  # type: ignore[attr-defined]
    except Exception:
        pass


def _carousel_delay_ms() -> int:
    try:
        from config_manager import ConfigManager

        seconds = float(ConfigManager().get("tools.preview_delay_sec", 3) or 3)
    except (TypeError, ValueError, ImportError):
        seconds = 3.0
    return int(max(1.0, min(seconds, 10.0)) * 1000)


def _cancel_carousel(window: tk.Toplevel) -> None:
    job_id = getattr(window, "_wm_editor_carousel_job", None)
    if job_id:
        try:
            window.after_cancel(job_id)
        except Exception:
            pass
    try:
        window._wm_editor_carousel_job = None  # type: ignore[attr-defined]
    except Exception:
        pass


def _schedule_carousel(window: tk.Toplevel) -> None:
    _cancel_carousel(window)
    if getattr(window, "_wm_editor_carousel_paused", False):
        return
    if len(_preview_items(window)) <= 1:
        return

    def _tick() -> None:
        try:
            window._wm_editor_carousel_job = None  # type: ignore[attr-defined]
            if not window.winfo_exists():
                return
        except Exception:
            return
        _step_gallery(window, 1)
        refresh = getattr(window, "_wm_editor_gallery_refresh", None)
        if callable(refresh):
            refresh()
        _schedule_carousel(window)

    try:
        window._wm_editor_carousel_job = window.after(  # type: ignore[attr-defined]
            _carousel_delay_ms(), _tick
        )
    except Exception:
        window._wm_editor_carousel_job = None  # type: ignore[attr-defined]


def _refresh_gallery_views(
    window: tk.Toplevel,
    header: tk.Misc | None,
    media_tab: tk.Misc | None,
) -> None:
    items = _preview_items(window)
    count = len(items)
    index = _gallery_index(window, count)

    if header is not None:
        thumb = getattr(header, "_wm_thumb", None)
        if thumb is not None:
            _refresh_thumbnail(window, thumb, (180, 110))
    if media_tab is not None:
        thumb = getattr(media_tab, "_wm_thumb", None)
        if thumb is not None:
            _refresh_thumbnail(window, thumb, (460, 330))

        counter = getattr(media_tab, "_wm_gallery_counter", None)
        dots = getattr(media_tab, "_wm_gallery_dots", None)
        previous = getattr(media_tab, "_wm_gallery_previous", None)
        following = getattr(media_tab, "_wm_gallery_next", None)
        primary = getattr(media_tab, "_wm_gallery_primary", None)
        remove = getattr(media_tab, "_wm_gallery_remove", None)

        if count:
            raw, path, kind = items[index]
            title = "Podgląd DXF" if kind == "dxf" else f"{index + 1} / {count}"
            if counter is not None:
                counter.configure(text=f"{title}  •  {path.name}")
            if dots is not None:
                if count <= 10:
                    dots.configure(
                        text=" ".join("●" if pos == index else "○" for pos in range(count))
                    )
                else:
                    dots.configure(text=f"Zdjęcie {index + 1} z {count}")
            is_image = kind in {"image", "missing_image"}
            is_primary = is_image and index == 0
        else:
            raw = ""
            if counter is not None:
                counter.configure(text="Brak zdjęć")
            if dots is not None:
                dots.configure(text="")
            is_image = False
            is_primary = False

        for button in (previous, following):
            if button is not None:
                button.state(["!disabled"] if count > 1 else ["disabled"])
        if primary is not None:
            primary.state(
                ["!disabled"] if is_image and not is_primary else ["disabled"]
            )
        if remove is not None:
            remove.state(["!disabled"] if is_image else ["disabled"])


def _refresh_and_schedule_gallery(window: tk.Toplevel) -> None:
    refresh = getattr(window, "_wm_editor_gallery_refresh", None)
    if callable(refresh):
        refresh()
    _schedule_carousel(window)


def _manual_gallery_step(window: tk.Toplevel, delta: int) -> None:
    _step_gallery(window, delta)
    _refresh_and_schedule_gallery(window)


def _set_carousel_paused(window: tk.Toplevel, paused: bool) -> None:
    try:
        window._wm_editor_carousel_paused = bool(paused)  # type: ignore[attr-defined]
    except Exception:
        return
    if paused:
        _cancel_carousel(window)
    else:
        _schedule_carousel(window)


def _set_current_image_as_primary(window: tk.Toplevel) -> None:
    current = _current_preview_item(window)
    setter = getattr(window, "_wm_tool_image_set_primary", None)
    if current is None or current[2] not in {"image", "missing_image"} or not callable(setter):
        return
    if setter(current[0]):
        _set_gallery_index(window, 0)
        _refresh_and_schedule_gallery(window)


def _remove_current_image(window: tk.Toplevel) -> None:
    current = _current_preview_item(window)
    remover = getattr(window, "_wm_tool_image_remove", None)
    if current is None or current[2] not in {"image", "missing_image"} or not callable(remover):
        return
    if not messagebox.askyesno(
        "Usuń zdjęcie",
        f"Usunąć zdjęcie „{current[1].name}” z tego narzędzia?",
        parent=window,
    ):
        return
    if remover(current[0]):
        _set_gallery_index(window, _gallery_index(window))
        _refresh_and_schedule_gallery(window)


def _open_full_preview(window: tk.Toplevel) -> None:
    items = _preview_items(window)
    if not items:
        return

    was_paused = bool(getattr(window, "_wm_editor_carousel_paused", False))
    _set_carousel_paused(window, True)
    preview = tk.Toplevel(window)
    preview.title("Podgląd zdjęcia narzędzia")
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
    max_size = (min(1200, int(screen_w * 0.82)), min(820, int(screen_h * 0.78)))

    image_label = ttk.Label(frame, style="WM.Card.TLabel", anchor="center")
    image_label.pack(fill="both", expand=True)

    controls = ttk.Frame(frame, style="WM.TFrame")
    controls.pack(fill="x", pady=(10, 0))
    previous = ttk.Button(controls, text="‹ Poprzednie", style="WM.Side.TButton")
    previous.pack(side="left")
    counter = ttk.Label(controls, text="", style="WM.Muted.TLabel", anchor="center")
    counter.pack(side="left", fill="x", expand=True, padx=10)
    following = ttk.Button(controls, text="Następne ›", style="WM.Side.TButton")
    following.pack(side="left", padx=(0, 10))

    state = {"index": _gallery_index(window, len(items))}
    close_state = {"closed": False}

    def _close() -> None:
        if close_state["closed"]:
            return
        close_state["closed"] = True
        try:
            preview.destroy()
        finally:
            _set_carousel_paused(window, was_paused)

    ttk.Button(
        controls, text="Zamknij", command=_close, style="WM.Side.TButton"
    ).pack(side="right")

    def _render() -> None:
        index = int(state["index"]) % len(items)
        state["index"] = index
        _set_gallery_index(window, index)
        refresh = getattr(window, "_wm_editor_gallery_refresh", None)
        if callable(refresh):
            refresh()
        _raw, path, kind = items[index]
        photo = _load_photo(path, preview, max_size)
        if photo is not None:
            image_label.configure(image=photo, text="")
            image_label._wm_editor_photo = photo  # type: ignore[attr-defined]
        else:
            image_label.configure(
                image="", text=f"Nie można otworzyć obrazu:\n{path.name}"
            )
            image_label._wm_editor_photo = None  # type: ignore[attr-defined]
        label = "DXF" if kind == "dxf" else f"{index + 1} / {len(items)}"
        counter.configure(text=f"{label}  •  {path.name}")
        preview.title(f"Podgląd zdjęć narzędzia — {path.name}")

    def _move(delta: int) -> None:
        state["index"] = (int(state["index"]) + delta) % len(items)
        _render()

    previous.configure(command=lambda: _move(-1))
    following.configure(command=lambda: _move(1))
    if len(items) <= 1:
        previous.state(["disabled"])
        following.state(["disabled"])
    _render()

    preview.protocol("WM_DELETE_WINDOW", _close)
    preview.bind("<Escape>", lambda _event: _close())
    preview.bind("<Left>", lambda _event: _move(-1))
    preview.bind("<Right>", lambda _event: _move(1))

    try:
        preview.update_idletasks()
        width = min(max(620, int(preview.winfo_reqwidth())), screen_w - 80)
        height = min(max(420, int(preview.winfo_reqheight())), screen_h - 100)
        x = max(0, window.winfo_rootx() + (window.winfo_width() - width) // 2)
        y = max(0, window.winfo_rooty() + (window.winfo_height() - height) // 2)
        preview.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass

    try:
        from ui_utils import _ensure_topmost

        _ensure_topmost(preview, window)
    except Exception:
        try:
            preview.lift(window)
            preview.focus_force()
        except Exception:
            pass


def _status_color(status: str, colors: dict[str, str]) -> str:
    value = (status or "").strip().lower()
    if any(token in value for token in ("uszk", "awari", "zagub", "błąd", "blad")):
        return colors["error"]
    if any(token in value for token in ("ostr", "napraw", "serwis", "przegl", "w toku", "oczek")):
        return colors["warning"]
    if any(token in value for token in ("ok", "dostęp", "dostep", "gotow", "spraw", "zakoń", "zakon")):
        return colors["success"]
    if any(token in value for token in ("projekt", "now", "zamów", "zamow")):
        return colors["blue"]
    return colors["accent"]


def _make_card(parent: tk.Misc, colors: dict[str, str], *, accent: str | None = None):
    return tk.Frame(
        parent,
        bg=colors["card"],
        highlightthickness=1,
        highlightbackground=accent or colors["line"],
        bd=0,
    )


def _label(parent: tk.Misc, text: str = "", *, muted: bool = False, **kwargs):
    colors = kwargs.pop("colors")
    return tk.Label(
        parent,
        text=text,
        bg=colors["card"],
        fg=colors["muted"] if muted else colors["text"],
        font=kwargs.pop("font", ("Segoe UI", 10)),
        anchor=kwargs.pop("anchor", "w"),
        **kwargs,
    )


def _find_tasks_tree(window: tk.Toplevel) -> ttk.Treeview | None:
    for tree in _all_descendants(window):
        if not isinstance(tree, ttk.Treeview):
            continue
        try:
            columns = {str(x) for x in tree.cget("columns")}
        except Exception:
            continue
        if {"tytul", "done"}.issubset(columns):
            return tree
    return None


def _task_counts(window: tk.Toplevel, doc: dict[str, Any]) -> tuple[int, int, int]:
    tree = _find_tasks_tree(window)
    if tree is not None:
        try:
            rows = list(tree.get_children(""))
            total = len(rows)
            done = 0
            for iid in rows:
                try:
                    value = str(tree.set(iid, "done") or "").strip().lower()
                except Exception:
                    value = ""
                if value in {"✔", "✓", "tak", "true", "1", "zrobione"}:
                    done += 1
            return total, done, max(0, total - done)
        except Exception:
            pass

    tasks = doc.get("zadania") if isinstance(doc, dict) else []
    if not isinstance(tasks, list):
        tasks = []
    total = len(tasks)
    done = sum(1 for item in tasks if isinstance(item, dict) and item.get("done"))
    return total, done, max(0, total - done)


def _visit_stats(doc: dict[str, Any]) -> tuple[int, bool, str, str]:
    visits = doc.get("wizyty") if isinstance(doc, dict) else []
    if not isinstance(visits, list):
        visits = []
    open_visit = None
    for item in reversed(visits):
        if isinstance(item, dict) and item.get("start_ts") and not item.get("end_ts"):
            open_visit = item
            break
    if open_visit is None:
        return len(visits), False, "", ""
    return (
        len(visits),
        True,
        str(open_visit.get("start_ts") or ""),
        str(open_visit.get("start_by") or ""),
    )


def _history_lines(doc: dict[str, Any], limit: int = 5) -> list[str]:
    history = doc.get("historia") if isinstance(doc, dict) else []
    if not isinstance(history, list):
        return []
    lines: list[str] = []
    for item in history[-limit:]:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts") or "").strip()
        action = str(item.get("action") or item.get("typ") or "").strip()
        if action == "status_changed":
            desc = f"Status: {item.get('z') or '—'} → {item.get('na') or '—'}"
        elif action == "task_added":
            desc = f"Dodano zadanie: {item.get('title') or '—'}"
        elif action == "task_done":
            desc = f"Wykonano zadanie: {item.get('title') or '—'}"
        elif action in {"visit", "cycle_closed"}:
            desc = "Zakończono wizytę"
        elif action:
            desc = action.replace("_", " ")
        else:
            desc = "Zmiana"
        lines.append(f"{ts or '—'}   {desc}")
    return lines


def _clone_basic_field(
    window: tk.Toplevel,
    parent: tk.Misc,
    row: int,
    title: str,
    source_label: str,
    *,
    readonly: bool = False,
    width: int = 32,
):
    colors = _palette()
    tk.Label(
        parent,
        text=title,
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9),
        anchor="w",
    ).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=6)

    holder = _field_value_widget(window, source_label)
    source_combo = _first_combo(holder)
    source_widget = source_combo or _first_entry(holder)
    variable = _shared_var(window, source_widget)
    if variable is None:
        fallback = tk.StringVar(master=window, value=_entry_value_from_field(window, source_label))
        variable = fallback

    if source_combo is not None:
        try:
            values = list(source_combo.cget("values") or [])
        except Exception:
            values = []
        target = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            width=width,
        )
        target.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=6)

        def _forward(_event=None):
            try:
                source_combo.event_generate("<<ComboboxSelected>>")
            except Exception:
                pass

        target.bind("<<ComboboxSelected>>", _forward)
        target._wm_source_combo = source_combo  # type: ignore[attr-defined]
        return target

    state = "readonly" if readonly else "normal"
    target = ttk.Entry(parent, textvariable=variable, width=width, state=state)
    target.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=6)
    return target


def _proxy_button(parent: tk.Misc, text: str, source: ttk.Button | None, *, style: str = "WM.Side.TButton"):
    def _invoke() -> None:
        if source is None:
            return
        try:
            source.invoke()
        except Exception:
            pass

    button = ttk.Button(parent, text=text, command=_invoke, style=style)
    if source is None:
        try:
            button.state(["disabled"])
        except Exception:
            pass
    return button


def _build_media_tab(
    window: tk.Toplevel,
    notebook: ttk.Notebook,
    image_holder: tk.Misc | None,
    dxf_holder: tk.Misc | None,
    colors: dict[str, str],
):
    media = ttk.Frame(notebook, padding=12, style="WM.Card.TFrame")

    delete_tab = _tab_by_text(notebook, "Usuń narzędzie")
    if delete_tab is not None:
        try:
            index = notebook.index(delete_tab)
            notebook.insert(index, media, text="Pliki i zdjęcia")
        except Exception:
            notebook.add(media, text="Pliki i zdjęcia")
    else:
        notebook.add(media, text="Pliki i zdjęcia")

    media.columnconfigure(0, weight=2)
    media.columnconfigure(1, weight=3)
    media.rowconfigure(0, weight=1)

    left = _make_card(media, colors, accent=colors["blue"])
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=2)
    tk.Label(
        left,
        text="ZDJĘCIE NARZĘDZIA",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=14, pady=(12, 6))
    thumb = tk.Label(
        left,
        text="Brak zdjęcia\nnarzędzia",
        bg=colors["panel"],
        fg=colors["muted"],
        font=("Segoe UI", 11),
        cursor="hand2",
        justify="center",
        width=34,
        height=15,
    )
    thumb.pack(fill="both", expand=True, padx=14, pady=(0, 10))
    thumb.bind("<Button-1>", lambda _event: _open_full_preview(window))
    thumb.bind("<Enter>", lambda _event: _set_carousel_paused(window, True))
    thumb.bind("<Leave>", lambda _event: _set_carousel_paused(window, False))

    gallery_nav = ttk.Frame(left, style="WM.TFrame")
    gallery_nav.pack(fill="x", padx=14, pady=(0, 6))
    previous = ttk.Button(
        gallery_nav,
        text="‹",
        command=lambda: _manual_gallery_step(window, -1),
        style="WM.Side.TButton",
        width=3,
    )
    previous.pack(side="left")
    gallery_counter = ttk.Label(
        gallery_nav,
        text="Brak zdjęć",
        style="WM.Muted.TLabel",
        anchor="center",
    )
    gallery_counter.pack(side="left", fill="x", expand=True, padx=8)
    following = ttk.Button(
        gallery_nav,
        text="›",
        command=lambda: _manual_gallery_step(window, 1),
        style="WM.Side.TButton",
        width=3,
    )
    following.pack(side="right")
    gallery_dots = ttk.Label(left, text="", style="WM.Muted.TLabel", anchor="center")
    gallery_dots.pack(fill="x", padx=14, pady=(0, 8))

    img_choose = _find_button(image_holder, "Wybierz...")
    img_clear = _find_button(image_holder, "Wyczyść")
    buttons = ttk.Frame(left, style="WM.TFrame")
    buttons.pack(fill="x", padx=14, pady=(0, 12))
    file_actions = ttk.Frame(buttons, style="WM.TFrame")
    file_actions.pack(fill="x")
    edit_actions = ttk.Frame(buttons, style="WM.TFrame")
    edit_actions.pack(fill="x", pady=(6, 0))
    _proxy_button(file_actions, "Dodaj zdjęcia", img_choose).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(
        file_actions,
        text="Pełny podgląd",
        command=lambda: _open_full_preview(window),
        style="WM.Side.TButton",
    ).pack(side="left", padx=(0, 6))
    primary = ttk.Button(
        edit_actions,
        text="Ustaw jako główne",
        command=lambda: _set_current_image_as_primary(window),
        style="WM.Side.TButton",
    )
    primary.pack(side="left", padx=(0, 6))
    remove = ttk.Button(
        edit_actions,
        text="Usuń bieżące",
        command=lambda: _remove_current_image(window),
        style="WM.Danger.TButton",
    )
    remove.pack(side="left", padx=(0, 6))
    _proxy_button(edit_actions, "Usuń wszystkie", img_clear).pack(side="left")

    right = _make_card(media, colors, accent=colors["purple"])
    right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=2)
    right.columnconfigure(1, weight=1)

    tk.Label(
        right,
        text="PLIKI POWIĄZANE",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 12))

    tk.Label(right, text="Zdjęcia", bg=colors["card"], fg=colors["muted"]).grid(
        row=1, column=0, sticky="nw", padx=(16, 10), pady=8
    )
    images_text = tk.Label(
        right,
        text="—",
        bg=colors["card"],
        fg=colors["text"],
        justify="left",
        anchor="nw",
        wraplength=520,
    )
    images_text.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=8)

    tk.Label(right, text="Plik DXF", bg=colors["card"], fg=colors["muted"]).grid(
        row=2, column=0, sticky="w", padx=(16, 10), pady=8
    )
    dxf_text = tk.Label(right, text="—", bg=colors["card"], fg=colors["text"], anchor="w")
    dxf_text.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=8)

    dxf_choose = _find_button(dxf_holder, "Wybierz...")
    _proxy_button(right, "Wybierz / zmień DXF", dxf_choose).grid(
        row=3, column=1, sticky="w", padx=(0, 16), pady=(4, 12)
    )

    info = tk.Label(
        right,
        text=(
            "Zdjęcia i DXF są nadal zapisywane przez istniejącą logikę Narzędzi. "
            "Ten widok zmienia tylko sposób ich prezentacji."
        ),
        bg=colors["card"],
        fg=colors["muted"],
        justify="left",
        wraplength=560,
    )
    info.grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 16))

    media._wm_thumb = thumb  # type: ignore[attr-defined]
    media._wm_gallery_previous = previous  # type: ignore[attr-defined]
    media._wm_gallery_next = following  # type: ignore[attr-defined]
    media._wm_gallery_counter = gallery_counter  # type: ignore[attr-defined]
    media._wm_gallery_dots = gallery_dots  # type: ignore[attr-defined]
    media._wm_gallery_primary = primary  # type: ignore[attr-defined]
    media._wm_gallery_remove = remove  # type: ignore[attr-defined]
    media._wm_images_text = images_text  # type: ignore[attr-defined]
    media._wm_dxf_text = dxf_text  # type: ignore[attr-defined]
    return media


def _build_dashboard(
    window: tk.Toplevel,
    notebook: ttk.Notebook,
    colors: dict[str, str],
):
    dash = ttk.Frame(notebook, padding=12, style="WM.Card.TFrame")
    notebook.insert(0, dash, text="Podgląd")
    dash.columnconfigure(0, weight=3)
    dash.columnconfigure(1, weight=2)
    dash.rowconfigure(1, weight=1)

    details = _make_card(dash, colors, accent=colors["blue"])
    details.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
    details.columnconfigure(1, weight=1)
    tk.Label(
        details,
        text="DANE NARZĘDZIA",
        bg=colors["card"],
        fg=colors["blue"],
        font=("Segoe UI", 10, "bold"),
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))

    nr_widget = _clone_basic_field(window, details, 1, "Numer", "Numer (3 cyfry)", readonly=True)
    name_widget = _clone_basic_field(window, details, 2, "Nazwa", "Nazwa")
    type_widget = _clone_basic_field(window, details, 3, "Typ", "Typ")
    status_widget = _clone_basic_field(window, details, 4, "Status", "Status")

    lifecycle = _make_card(dash, colors, accent=colors["purple"])
    lifecycle.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
    tk.Label(
        lifecycle,
        text="CYKL ŻYCIA",
        bg=colors["card"],
        fg=colors["purple"],
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w", padx=14, pady=(12, 8))

    mode_line = tk.Label(
        lifecycle,
        text="—",
        bg=colors["card"],
        fg=colors["text"],
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    )
    mode_line.pack(fill="x", padx=14, pady=(0, 8))

    visit_line = tk.Label(
        lifecycle,
        text="Wizyta: —",
        bg=colors["card"],
        fg=colors["muted"],
        justify="left",
        anchor="w",
    )
    visit_line.pack(fill="x", padx=14, pady=(0, 8))

    conversion_source = _find_checkbutton(window, "Przenieś do SN przy zapisie")
    conversion_clone = None
    if conversion_source is not None:
        try:
            variable_name = str(conversion_source.cget("variable") or "").strip()
            variable = tk.BooleanVar(master=window, name=variable_name) if variable_name else None
        except Exception:
            variable = None
        if variable is not None:
            conversion_clone = ttk.Checkbutton(
                lifecycle,
                text="Przenieś do SN przy zapisie",
                variable=variable,
            )
            conversion_clone.pack(anchor="w", padx=12, pady=(4, 12))
            try:
                if "disabled" in conversion_source.state():
                    conversion_clone.state(["disabled"])
            except Exception:
                pass

    stats = ttk.Frame(dash, style="WM.TFrame")
    stats.grid(row=1, column=0, columnspan=2, sticky="nsew")
    stats.columnconfigure(0, weight=1)
    stats.columnconfigure(1, weight=1)
    stats.columnconfigure(2, weight=1)
    stats.columnconfigure(3, weight=1)

    stat_labels = []
    stat_specs = [
        ("ZADANIA", colors["blue"]),
        ("WYKONANE", colors["success"]),
        ("DO ZROBIENIA", colors["warning"]),
        ("WIZYTY", colors["purple"]),
    ]
    for col, (title, accent) in enumerate(stat_specs):
        card = _make_card(stats, colors, accent=accent)
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5), pady=(0, 8))
        tk.Label(
            card,
            text=title,
            bg=colors["card"],
            fg=colors["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 0))
        value = tk.Label(
            card,
            text="0",
            bg=colors["card"],
            fg=accent,
            font=("Segoe UI", 22, "bold"),
        )
        value.pack(anchor="w", padx=12, pady=(0, 10))
        stat_labels.append(value)

    lower_left = _make_card(stats, colors)
    lower_left.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(0, 5), pady=(0, 2))
    tk.Label(
        lower_left,
        text="OSTATNIA AKTYWNOŚĆ",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=12, pady=(12, 6))
    history_text = tk.Label(
        lower_left,
        text="Brak historii",
        bg=colors["card"],
        fg=colors["text"],
        justify="left",
        anchor="nw",
        wraplength=560,
    )
    history_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    lower_right = _make_card(stats, colors)
    lower_right.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(5, 0), pady=(0, 2))
    tk.Label(
        lower_right,
        text="INFORMACJE DODATKOWE",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9, "bold"),
    ).pack(anchor="w", padx=12, pady=(12, 6))
    extra_text = tk.Label(
        lower_right,
        text="—",
        bg=colors["card"],
        fg=colors["text"],
        justify="left",
        anchor="nw",
        wraplength=560,
    )
    extra_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    dash._wm_nr_widget = nr_widget  # type: ignore[attr-defined]
    dash._wm_name_widget = name_widget  # type: ignore[attr-defined]
    dash._wm_type_widget = type_widget  # type: ignore[attr-defined]
    dash._wm_status_widget = status_widget  # type: ignore[attr-defined]
    dash._wm_mode_line = mode_line  # type: ignore[attr-defined]
    dash._wm_visit_line = visit_line  # type: ignore[attr-defined]
    dash._wm_stat_labels = stat_labels  # type: ignore[attr-defined]
    dash._wm_history_text = history_text  # type: ignore[attr-defined]
    dash._wm_extra_text = extra_text  # type: ignore[attr-defined]
    dash._wm_conversion_clone = conversion_clone  # type: ignore[attr-defined]
    return dash


def _build_header(window: tk.Toplevel, header: ttk.Frame, colors: dict[str, str]):
    for child in list(header.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    image_box = tk.Frame(header, bg=colors["panel"], highlightthickness=1, highlightbackground=colors["line"])
    image_box.pack(side="left", padx=(0, 14))
    thumb = tk.Label(
        image_box,
        text="Brak zdjęcia",
        bg=colors["panel"],
        fg=colors["muted"],
        width=22,
        height=7,
        cursor="hand2",
        justify="center",
    )
    thumb.pack(padx=6, pady=6)
    thumb.bind("<Button-1>", lambda _event: _open_full_preview(window))
    thumb.bind("<Enter>", lambda _event: _set_carousel_paused(window, True))
    thumb.bind("<Leave>", lambda _event: _set_carousel_paused(window, False))

    identity = ttk.Frame(header, style="WM.Card.TFrame")
    identity.pack(side="left", fill="both", expand=True, padx=(0, 14))

    badges = ttk.Frame(identity, style="WM.Card.TFrame")
    badges.pack(anchor="w", fill="x")
    number_badge = tk.Label(
        badges,
        text="#---",
        bg=colors["blue"],
        fg="#ffffff",
        font=("Segoe UI", 10, "bold"),
        padx=9,
        pady=3,
    )
    number_badge.pack(side="left", padx=(0, 6))
    mode_badge = tk.Label(
        badges,
        text="NN",
        bg=colors["blue"],
        fg="#ffffff",
        font=("Segoe UI", 9, "bold"),
        padx=9,
        pady=3,
    )
    mode_badge.pack(side="left")

    name_label = tk.Label(
        identity,
        text="Narzędzie",
        bg=colors["card"],
        fg=colors["text"],
        font=("Segoe UI", 20, "bold"),
        anchor="w",
    )
    name_label.pack(anchor="w", fill="x", pady=(8, 2))
    type_label = tk.Label(
        identity,
        text="Typ: —",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 10),
        anchor="w",
    )
    type_label.pack(anchor="w", fill="x")

    right = ttk.Frame(header, style="WM.Card.TFrame")
    right.pack(side="right", anchor="ne")
    tk.Label(
        right,
        text="STATUS",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 8, "bold"),
    ).pack(anchor="e")
    status_badge = tk.Label(
        right,
        text="—",
        bg=colors["accent"],
        fg="#ffffff",
        font=("Segoe UI", 11, "bold"),
        padx=12,
        pady=5,
    )
    status_badge.pack(anchor="e", pady=(3, 8))
    summary_label = tk.Label(
        right,
        text="Zadania: 0  •  Wizyty: 0",
        bg=colors["card"],
        fg=colors["muted"],
        font=("Segoe UI", 9),
        anchor="e",
    )
    summary_label.pack(anchor="e")

    header._wm_thumb = thumb  # type: ignore[attr-defined]
    header._wm_number_badge = number_badge  # type: ignore[attr-defined]
    header._wm_mode_badge = mode_badge  # type: ignore[attr-defined]
    header._wm_name_label = name_label  # type: ignore[attr-defined]
    header._wm_type_label = type_label  # type: ignore[attr-defined]
    header._wm_status_badge = status_badge  # type: ignore[attr-defined]
    header._wm_summary_label = summary_label  # type: ignore[attr-defined]


def _sync_new_view(
    window: tk.Toplevel,
    header: ttk.Frame,
    dashboard: tk.Misc,
    media_tab: tk.Misc,
    colors: dict[str, str],
) -> None:
    nr = _entry_value_from_field(window, "Numer (3 cyfry)") or "---"
    name = _entry_value_from_field(window, "Nazwa") or "Bez nazwy"
    tool_type = _entry_value_from_field(window, "Typ") or "—"
    status = _entry_value_from_field(window, "Status") or "—"
    try:
        title = str(window.title() or "")
    except Exception:
        title = ""
    mode = "NN" if "NOWE" in title.upper() else "SN"

    doc = _current_doc(window)
    total, done, open_tasks = _task_counts(window, doc)
    visit_count, visit_open, visit_start, visit_by = _visit_stats(doc)

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
            bg=_status_color(status, colors),
        )
        header._wm_summary_label.configure(  # type: ignore[attr-defined]
            text=f"Zadania: {done}/{total}  •  Wizyty: {visit_count}"
        )
    except Exception:
        pass

    try:
        dashboard._wm_mode_line.configure(  # type: ignore[attr-defined]
            text=f"{mode}  •  {status}",
            fg=_status_color(status, colors),
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

        stat_labels = dashboard._wm_stat_labels  # type: ignore[attr-defined]
        for label, value in zip(stat_labels, (total, done, open_tasks, visit_count)):
            label.configure(text=str(value))

        recent = _history_lines(doc)
        dashboard._wm_history_text.configure(  # type: ignore[attr-defined]
            text="\n".join(recent) if recent else "Brak zapisanej historii"
        )

        current_images = _image_values(window, doc)
        image_count = len(current_images)
        archived = doc.get("zadania_archiwalne") if isinstance(doc, dict) else []
        archived_count = len(archived) if isinstance(archived, list) else 0
        employee = str(doc.get("pracownik") or "—") if isinstance(doc, dict) else "—"
        date_value = _added_date(doc)
        dxf = str(doc.get("dxf") or "") if isinstance(doc, dict) else ""
        desc = str(doc.get("opis") or "").strip() if isinstance(doc, dict) else ""
        if len(desc) > 220:
            desc = desc[:217].rstrip() + "..."
        dashboard._wm_extra_text.configure(  # type: ignore[attr-defined]
            text=(
                f"Pracownik: {employee}\n"
                f"Data: {date_value}\n"
                f"Zdjęcia: {image_count}\n"
                f"DXF: {'tak' if dxf else 'nie'}\n"
                f"Zadania archiwalne: {archived_count}\n\n"
                f"Opis: {desc or '—'}"
            )
        )

        # Gdy typ zmieni wartości statusów w starym formularzu, odśwież je również tutaj.
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

    try:
        current_images = _image_values(window, doc)
        images_label = _images_summary(current_images)
        media_tab._wm_images_text.configure(text=images_label)  # type: ignore[attr-defined]
        dxf_label = _holder_label_value(_field_value_widget(window, "Plik DXF")) or "—"
        media_tab._wm_dxf_text.configure(text=dxf_label)  # type: ignore[attr-defined]
    except Exception:
        pass

    _refresh_gallery_views(window, header, media_tab)
    _schedule_carousel(window)

    try:
        window.title(f"Narzędzie {nr} — {name} [{mode}]")
    except Exception:
        pass


def _hide_legacy_identity_rows(window: tk.Toplevel) -> None:
    for label in (
        "Numer (3 cyfry)",
        "Nazwa",
        "Typ",
        "Status",
        "Obraz",
        "Plik DXF",
        "Konwersja NN→SN",
    ):
        _hide_field_row(window, label)

    keep = _find_checkbutton(window, "Numer stały – nie zmienia się przy NN → SN")
    if keep is None:
        keep = _find_checkbutton(window, "Zachowaj numer przy zmianie trybu")
    _hide_grid(keep)


def _rename_tabs(notebook: ttk.Notebook) -> None:
    mapping = {
        "Opis narzędzia": "Opis",
        "Usuń narzędzie": "Usuń",
    }
    for tab_id in notebook.tabs():
        try:
            text = str(notebook.tab(tab_id, "text") or "").strip()
            if text in mapping:
                notebook.tab(tab_id, text=mapping[text])
        except Exception:
            continue


def _fit_window(window: tk.Toplevel) -> None:
    try:
        window.update_idletasks()
        sw = max(800, int(window.winfo_screenwidth()))
        sh = max(600, int(window.winfo_screenheight()))
        width = min(1420, max(760, sw - 60))
        height = min(900, max(560, sh - 100))
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(min(1120, width), min(680, height))
    except Exception:
        pass


def _decorate_editor(window: tk.Toplevel) -> bool:
    try:
        title = str(window.title() or "")
    except Exception:
        return False
    if title not in _EDITOR_TITLES:
        return False
    if getattr(window, "_wm_editor_variant_ready", False):
        return True
    if not _new_variant_enabled():
        return True

    _main, header, notebook = _editor_parts(window)
    if header is None or notebook is None:
        return False

    colors = _palette()
    image_holder = _field_value_widget(window, "Obraz")
    dxf_holder = _field_value_widget(window, "Plik DXF")

    _build_header(window, header, colors)
    dashboard = _build_dashboard(window, notebook, colors)
    media_tab = _build_media_tab(window, notebook, image_holder, dxf_holder, colors)
    window._wm_editor_gallery_refresh = (  # type: ignore[attr-defined]
        lambda: _refresh_gallery_views(window, header, media_tab)
    )
    def _on_window_destroy(event: tk.Event) -> None:
        if getattr(event, "widget", None) is window:
            _cancel_carousel(window)

    try:
        window.bind("<Destroy>", _on_window_destroy, add="+")
    except Exception:
        pass
    _rename_tabs(notebook)
    _hide_legacy_identity_rows(window)
    _fit_window(window)

    refresh_job: dict[str, Any] = {"id": None}

    def _refresh() -> None:
        try:
            if not window.winfo_exists():
                return
        except Exception:
            return
        _sync_new_view(window, header, dashboard, media_tab, colors)
        try:
            refresh_job["id"] = window.after(450, _refresh)
        except Exception:
            refresh_job["id"] = None

    window.bind("<FocusIn>", lambda _event: _sync_new_view(window, header, dashboard, media_tab, colors), add="+")
    window.bind("<ButtonRelease-1>", lambda _event: _sync_new_view(window, header, dashboard, media_tab, colors), add="+")
    try:
        notebook.select(dashboard)
    except Exception:
        pass
    _refresh()

    window._wm_editor_variant_ready = True  # type: ignore[attr-defined]
    window._wm_editor_variant_refresh_job = refresh_job  # type: ignore[attr-defined]
    return True


def install_tools_editor_variant_runtime() -> None:
    """Install optional full card/dashboard view for the shared NN/SN editor."""

    if getattr(tk.Toplevel, "_wm_tools_editor_variant_runtime", False):
        return

    original_init = tk.Toplevel.__init__

    def _init_with_editor_variant(self, *args: Any, **kwargs: Any):
        original_init(self, *args, **kwargs)

        def _try(attempt: int = 0) -> None:
            try:
                if not self.winfo_exists():
                    return
                title = str(self.title() or "")
            except Exception:
                return
            if title not in _EDITOR_TITLES:
                return
            if _decorate_editor(self):
                return
            if attempt < 8:
                try:
                    self.after(80, lambda: _try(attempt + 1))
                except Exception:
                    pass

        try:
            self.after(100, _try)
        except Exception:
            pass

    tk.Toplevel.__init__ = _init_with_editor_variant
    tk.Toplevel._wm_tools_editor_variant_runtime = True  # type: ignore[attr-defined]


__all__ = ["install_tools_editor_variant_runtime"]
