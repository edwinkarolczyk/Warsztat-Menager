# version: 1.2
"""Adaptacyjny rozmiar, przewijanie i podgląd obiektu kreatora Dyspozycji."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

try:  # Pillow jest już używany przez moduły Narzędzi/Maszyn, ale runtime ma fallback.
    from PIL import Image, ImageOps, ImageTk
except Exception:  # pragma: no cover - środowisko bez Pillow
    Image = ImageOps = ImageTk = None  # type: ignore

_TITLES = {
    "Kreator – Dodaj Dyspozycję",
    "Kreator – Edytuj Dyspozycję",
}


def _is_creator(window) -> bool:
    try:
        return str(window.title() or "") in _TITLES
    except Exception:
        return False


def _creator_frames(window):
    """Zwróć główną zawartość i dolny pasek przycisków kreatora."""
    try:
        children = list(window.winfo_children())
    except Exception:
        return None, None
    frames = [w for w in children if isinstance(w, ttk.Frame)]
    if len(frames) < 2:
        return None, None
    return frames[0], frames[-1]


def _normalize_object_id(value) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw, raw.lower()}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return {item for item in out if item}


def _type_key(display: str) -> str:
    raw = str(display or "").strip().casefold()
    aliases = {
        "narzędzie": "narzedzie",
        "narzedzie": "narzedzie",
        "maszyna": "maszyna",
        "magazyn": "magazyn",
        "wykonanie produkcji": "zlecenie_wykonania",
        "zlecenie_wykonania": "zlecenie_wykonania",
    }
    return aliases.get(raw, raw)


def _object_id_for_label(typ: str, label: str) -> str:
    try:
        from dyspozycje_sources import load_machine_choices, load_tool_choices
    except Exception:
        return ""

    try:
        if typ == "narzedzie":
            rows = load_tool_choices()
        elif typ == "maszyna":
            rows = load_machine_choices()
        else:
            rows = []
    except Exception:
        rows = []

    wanted = str(label or "").strip()
    for object_id, object_label in rows or []:
        if str(object_label or "").strip() == wanted:
            return str(object_id or "").strip()
    return ""


def _row_for_object(typ: str, object_id: str) -> dict:
    variants = _normalize_object_id(object_id)
    if not variants:
        return {}

    if typ == "narzedzie":
        try:
            import gui_narzedzia as gn

            rows = gn._external_load_tools_rows()
        except Exception:
            rows = []
        keys = ("id", "nr", "numer")
    elif typ == "maszyna":
        try:
            import gui_maszyny as gm

            rows = gm.load_machines_rows()
        except Exception:
            rows = []
        keys = ("id", "nr_ewid", "nr", "numer")
    else:
        return {}

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = ""
        for key in keys:
            rid = str(row.get(key) or "").strip()
            if rid:
                break
        if variants.intersection(_normalize_object_id(rid)):
            return dict(row)
    return {}


def _flatten_image_values(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _image_candidates(typ: str, row: dict) -> list[str]:
    out: list[str] = []

    def _add(value) -> None:
        for item in _flatten_image_values(value):
            if item and item not in out:
                out.append(item)

    if typ == "narzedzie":
        _add(row.get("obrazy"))
        _add(row.get("obraz"))
        # Jeżeli narzędzie nie ma fotografii, istniejący PNG z DXF jest nadal
        # lepszym podglądem identyfikacyjnym niż puste pole.
        _add(row.get("dxf_png"))
    elif typ == "maszyna":
        media = row.get("media")
        if isinstance(media, dict):
            for key in (
                "preview_url",
                "preview",
                "thumbnail",
                "miniatura",
                "image",
                "photo",
                "obraz",
                "zdjecie",
                "zdjęcie",
            ):
                _add(media.get(key))
        for key in (
            "miniatura",
            "obraz",
            "obrazy",
            "image",
            "photo",
            "foto",
            "zdjecie",
            "zdjęcie",
        ):
            _add(row.get(key))
    return out


def _base_dirs_for_object(typ: str) -> list[Path]:
    bases: list[Path] = [Path.cwd()]

    try:
        from config_manager import ConfigManager

        cfg = ConfigManager()
        data_dir = Path(cfg.path_data())
        bases.extend([data_dir, data_dir / "maszyny", data_dir / "narzedzia"])
        for method_name in ("path_anchor", "path_root"):
            method = getattr(cfg, method_name, None)
            if callable(method):
                try:
                    bases.append(Path(method()))
                except Exception:
                    pass
    except Exception:
        pass

    if typ == "narzedzie":
        try:
            import gui_narzedzia as gn

            resolver = getattr(gn, "_resolve_tools_dir", None)
            if callable(resolver):
                bases.insert(0, Path(resolver()))
        except Exception:
            pass

    unique: list[Path] = []
    seen: set[str] = set()
    for base in bases:
        try:
            key = os.path.normcase(os.path.abspath(str(base)))
        except Exception:
            key = str(base)
        if key in seen:
            continue
        seen.add(key)
        unique.append(base)
    return unique


def _resolve_image_path(typ: str, row: dict) -> Path | None:
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    bases = _base_dirs_for_object(typ)

    for raw in _image_candidates(typ, row):
        value = os.path.expandvars(os.path.expanduser(str(raw or "").strip()))
        if not value or value.lower().startswith(("http://", "https://")):
            continue

        direct = Path(value)
        candidates = [direct] if direct.is_absolute() else [base / direct for base in bases]
        if not direct.is_absolute():
            candidates.insert(0, direct)

        for candidate in candidates:
            try:
                if candidate.is_file() and candidate.suffix.lower() in allowed:
                    return candidate
            except Exception:
                continue
    return None


def _object_name_status(typ: str, object_id: str, row: dict) -> tuple[str, str, str | None]:
    name = str(row.get("nazwa") or row.get("name") or object_id or "—").strip()
    status = str(row.get("status") or "—").strip()
    color = None

    if typ == "maszyna":
        try:
            import gui_maszyny as gm

            status = gm._machine_status_label(row.get("status"))
            key = gm._normalize_machine_status(row.get("status"))
            color = gm.MACHINE_STATUS_COLORS.get(key)
        except Exception:
            pass
    return name or "—", status or "—", color


def _find_grid_combobox(content, row: int, column: int):
    try:
        children = list(content.winfo_children())
    except Exception:
        return None
    for widget in children:
        if not isinstance(widget, ttk.Combobox):
            continue
        try:
            info = widget.grid_info()
            if int(info.get("row", -1)) == row and int(info.get("column", -1)) == column:
                return widget
        except Exception:
            continue
    return None


def _install_object_preview(window) -> None:
    """Dodaj prawy podgląd zdjęcia bez ingerencji w zapis Dyspozycji."""
    if not _is_creator(window):
        return
    if getattr(window, "_wm_dysp_object_preview", False):
        return

    content, _buttons = _creator_frames(window)
    if content is None:
        return

    type_combo = _find_grid_combobox(content, 1, 1)
    object_combo = _find_grid_combobox(content, 3, 1)
    if type_combo is None or object_combo is None:
        return

    window._wm_dysp_object_preview = True

    panel = ttk.LabelFrame(content, text="Podgląd obiektu", padding=8)
    panel.grid(row=1, column=3, rowspan=8, sticky="n", padx=(18, 0), pady=(0, 8))
    try:
        content.columnconfigure(3, minsize=270)
    except Exception:
        pass

    try:
        from ui_theme import get_theme_color

        canvas_bg = get_theme_color("card", fallback="#202226")
        canvas_fg = get_theme_color("fg_dim", fallback="#a9abb3")
        border = get_theme_color("border", fallback="#2a2d33")
    except Exception:
        canvas_bg, canvas_fg, border = "#202226", "#a9abb3", "#2a2d33"

    canvas = tk.Canvas(
        panel,
        width=250,
        height=180,
        bg=canvas_bg,
        highlightthickness=1,
        highlightbackground=border,
        bd=0,
        cursor="arrow",
    )
    canvas.pack()

    name_var = tk.StringVar(master=panel, value="")
    status_var = tk.StringVar(master=panel, value="")
    ttk.Label(
        panel,
        textvariable=name_var,
        font=("Segoe UI", 10, "bold"),
        anchor="center",
        justify="center",
        wraplength=250,
    ).pack(fill="x", pady=(8, 2))
    status_label = ttk.Label(
        panel,
        textvariable=status_var,
        anchor="center",
        justify="center",
    )
    status_label.pack(fill="x")
    hint_var = tk.StringVar(master=panel, value="")
    ttk.Label(
        panel,
        textvariable=hint_var,
        style="WM.Muted.TLabel",
        anchor="center",
        justify="center",
        wraplength=250,
    ).pack(fill="x", pady=(5, 0))

    current = {"path": None, "key": None}

    def _placeholder(text: str) -> None:
        window._wm_dysp_preview_photo = None
        canvas.delete("all")
        canvas.create_text(
            125,
            90,
            text=text,
            fill=canvas_fg,
            width=220,
            justify="center",
            font=("Segoe UI", 10),
        )
        canvas.configure(cursor="arrow")

    def _render_preview(path: Path | None) -> None:
        current["path"] = path
        if path is None:
            _placeholder("Brak zdjęcia")
            hint_var.set("Brak zdjęcia dla wybranego obiektu")
            return
        if Image is None or ImageTk is None:
            _placeholder("Podgląd zdjęcia wymaga Pillow")
            hint_var.set(str(path.name))
            return

        try:
            image = Image.open(path)
            if ImageOps is not None:
                image = ImageOps.exif_transpose(image)
            image.thumbnail((246, 176))
            photo = ImageTk.PhotoImage(image)
            window._wm_dysp_preview_photo = photo
            canvas.delete("all")
            canvas.create_image(125, 90, image=photo, anchor="center")
            canvas.configure(cursor="hand2")
            hint_var.set("Kliknij zdjęcie, aby powiększyć")
        except Exception:
            logger.exception("[DYSP][PREVIEW] Nie udało się wczytać miniatury: %s", path)
            _placeholder("Nie można wczytać zdjęcia")
            hint_var.set(str(path.name))
            current["path"] = None

    def _open_full(_event=None) -> None:
        path = current.get("path")
        if path is None or Image is None or ImageTk is None:
            return
        try:
            viewer = tk.Toplevel(window)
            viewer.title(f"Podgląd zdjęcia – {path.name}")
            viewer.configure(bg=canvas_bg)
            screen_w = int(viewer.winfo_screenwidth())
            screen_h = int(viewer.winfo_screenheight())
            width = max(720, int(screen_w * 0.88))
            height = max(520, int(screen_h * 0.88))
            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2)
            viewer.geometry(f"{width}x{height}+{x}+{y}")
            viewer.transient(window)

            image = Image.open(path)
            if ImageOps is not None:
                image = ImageOps.exif_transpose(image)
            image.thumbnail((width - 40, height - 70))
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(viewer, image=photo, bg=canvas_bg, bd=0)
            label.image = photo
            label.pack(fill="both", expand=True, padx=12, pady=12)
            ttk.Label(
                viewer,
                text="Esc – zamknij",
                style="WM.Muted.TLabel",
            ).pack(pady=(0, 8))
            viewer.bind("<Escape>", lambda _e: viewer.destroy(), add="+")
            viewer.focus_set()
        except Exception:
            logger.exception("[DYSP][PREVIEW] Nie udało się otworzyć pełnego zdjęcia: %s", path)

    canvas.bind("<Button-1>", _open_full, add="+")

    def _refresh() -> None:
        typ = _type_key(type_combo.get())
        label = str(object_combo.get() or "").strip()
        signature = (typ, label)
        if current.get("key") == signature:
            return
        current["key"] = signature

        if typ not in {"narzedzie", "maszyna"}:
            try:
                panel.grid_remove()
            except Exception:
                pass
            current["path"] = None
            window._wm_dysp_preview_photo = None
            return

        try:
            panel.grid()
        except Exception:
            pass

        object_id = _object_id_for_label(typ, label)
        row = _row_for_object(typ, object_id)
        name, status, status_color = _object_name_status(typ, object_id, row)
        prefix = "Narzędzie" if typ == "narzedzie" else "Maszyna"
        display_id = object_id or "—"
        name_var.set(f"{prefix} {display_id}\n{name}")
        status_var.set(f"Status: {status}")
        try:
            if status_color:
                status_label.configure(foreground=status_color)
            else:
                status_label.configure(foreground="")
        except Exception:
            pass

        _render_preview(_resolve_image_path(typ, row))

    def _event_refresh(_event=None) -> None:
        try:
            window.after_idle(_refresh)
        except Exception:
            pass

    type_combo.bind("<<ComboboxSelected>>", _event_refresh, add="+")
    object_combo.bind("<<ComboboxSelected>>", _event_refresh, add="+")

    def _poll() -> None:
        try:
            if not window.winfo_exists():
                return
            _refresh()
            window._wm_dysp_preview_job = window.after(450, _poll)
        except Exception:
            pass

    def _cleanup(event=None) -> None:
        if event is not None and getattr(event, "widget", None) is not window:
            return
        job = getattr(window, "_wm_dysp_preview_job", None)
        if job:
            try:
                window.after_cancel(job)
            except Exception:
                pass
            window._wm_dysp_preview_job = None

    window.bind("<Destroy>", _cleanup, add="+")
    _placeholder("Wybierz Narzędzie lub Maszynę")
    _refresh()
    try:
        window._wm_dysp_preview_job = window.after(450, _poll)
    except Exception:
        pass


def _install_adaptive_layout(window) -> None:
    if not _is_creator(window):
        return
    if getattr(window, "_wm_dysp_adaptive_layout", False):
        return

    content, buttons = _creator_frames(window)
    if content is None or buttons is None or content is buttons:
        return

    window._wm_dysp_adaptive_layout = True
    window._wm_dysp_scroll_offset = 0
    window._wm_dysp_reflow_job = None

    try:
        window.state("normal")
    except Exception:
        pass
    try:
        window.attributes("-zoomed", False)
    except Exception:
        pass

    try:
        content.pack_forget()
    except Exception:
        pass
    try:
        buttons.pack_forget()
    except Exception:
        pass

    scrollbar = ttk.Scrollbar(window, orient="vertical")
    window._wm_dysp_scrollbar = scrollbar

    def _limits() -> tuple[int, int, int, int]:
        try:
            win_w = max(1, int(window.winfo_width()))
            win_h = max(1, int(window.winfo_height()))
            button_h = max(48, int(buttons.winfo_reqheight()) + 10)
            viewport_h = max(1, win_h - button_h)
            content_h = max(viewport_h, int(content.winfo_reqheight()))
            max_offset = max(0, content_h - viewport_h)
            return win_w, win_h, viewport_h, max_offset
        except Exception:
            return 900, 600, 540, 0

    def _apply_positions() -> None:
        win_w, win_h, viewport_h, max_offset = _limits()
        offset = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        offset = max(0, min(offset, max_offset))
        window._wm_dysp_scroll_offset = offset

        button_h = max(48, win_h - viewport_h)
        scroll_w = 18 if max_offset > 0 else 0
        content_w = max(1, win_w - scroll_w)
        content_h = viewport_h + max_offset

        try:
            content.place(x=0, y=-offset, width=content_w, height=content_h)
            buttons.place(x=0, y=viewport_h, width=win_w, height=button_h)
        except Exception:
            return

        if max_offset > 0:
            try:
                scrollbar.place(x=win_w - 18, y=0, width=18, height=viewport_h)
                first = offset / max(1, content_h)
                last = min(1.0, (offset + viewport_h) / max(1, content_h))
                scrollbar.set(first, last)
            except Exception:
                pass
        else:
            try:
                scrollbar.place_forget()
            except Exception:
                pass

    def _scroll_to_fraction(fraction: float) -> None:
        _win_w, _win_h, _viewport_h, max_offset = _limits()
        fraction = max(0.0, min(1.0, float(fraction)))
        window._wm_dysp_scroll_offset = int(round(max_offset * fraction))
        _apply_positions()

    def _scroll_command(*args) -> None:
        if not args:
            return
        kind = str(args[0])
        _win_w, _win_h, viewport_h, max_offset = _limits()
        current = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        if kind == "moveto" and len(args) >= 2:
            _scroll_to_fraction(float(args[1]))
            return
        if kind == "scroll" and len(args) >= 3:
            amount = int(args[1])
            unit = str(args[2])
            step = max(30, viewport_h // 10)
            if unit == "pages":
                step = max(60, int(viewport_h * 0.8))
            window._wm_dysp_scroll_offset = max(
                0,
                min(max_offset, current + amount * step),
            )
            _apply_positions()

    scrollbar.configure(command=_scroll_command)

    def _wheel(event) -> None:
        _win_w, _win_h, viewport_h, max_offset = _limits()
        if max_offset <= 0:
            return
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return
        direction = -1 if delta > 0 else 1
        current = int(getattr(window, "_wm_dysp_scroll_offset", 0) or 0)
        step = max(36, viewport_h // 12)
        window._wm_dysp_scroll_offset = max(
            0,
            min(max_offset, current + direction * step),
        )
        _apply_positions()
        return "break"

    def _schedule_reflow(_event=None) -> None:
        old = getattr(window, "_wm_dysp_reflow_job", None)
        if old:
            try:
                window.after_cancel(old)
            except Exception:
                pass
        try:
            window._wm_dysp_reflow_job = window.after_idle(_apply_positions)
        except Exception:
            pass

    try:
        window.bind("<Configure>", _schedule_reflow, add="+")
        content.bind("<Configure>", _schedule_reflow, add="+")
        window.bind("<MouseWheel>", _wheel, add="+")
    except Exception:
        pass

    # Po zbudowaniu wszystkich kontrolek dobierz początkowy rozmiar do treści,
    # ale nigdy nie zajmuj całego ekranu.
    try:
        window.update_idletasks()
        screen_w = int(window.winfo_screenwidth())
        screen_h = int(window.winfo_screenheight())
    except Exception:
        screen_w, screen_h = 1366, 768

    try:
        req_w = max(int(content.winfo_reqwidth()), int(buttons.winfo_reqwidth())) + 36
        req_h = int(content.winfo_reqheight()) + max(48, int(buttons.winfo_reqheight()) + 10)
    except Exception:
        req_w, req_h = 1080, 680

    max_w = max(760, int(screen_w * 0.90))
    max_h = max(560, int(screen_h * 0.90))
    width = min(max_w, max(900, req_w))
    height = min(max_h, max(560, req_h))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)

    try:
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.resizable(True, True)
        window.update_idletasks()
        _apply_positions()
    except Exception:
        logger.exception("[DYSP][WINDOW] Nie udało się ustawić adaptacyjnego układu.")


def install_dysp_creator_window_behavior() -> bool:
    """Dostosuj wyłącznie kreator Dodaj/Edytuj Dyspozycję."""

    if getattr(tk, "_wm_dysp_creator_window_proxy", False):
        return True

    real_toplevel = getattr(tk, "Toplevel", None)
    if real_toplevel is None:
        return False

    class _DyspCreatorAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def _apply() -> None:
                try:
                    _install_object_preview(self)
                    _install_adaptive_layout(self)
                except Exception:
                    logger.exception("[DYSP][WINDOW] Błąd adaptacji okna kreatora.")

            try:
                self.after_idle(_apply)
            except Exception:
                pass

    tk.Toplevel = _DyspCreatorAwareToplevel
    tk._wm_dysp_creator_window_proxy = True
    return True


__all__ = ["install_dysp_creator_window_behavior"]
