# version: 1.1
# Moduł: narzedzia_ui.editor_variant_runtime
# Opcjonalny nowy widok edytora NN/SN. Klasyczny edytor pozostaje bez zmian.
# 1.1: pierwsza zawersjonowana wersja po integracji z Ustawieniami i podglądem miniatury.

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import ttk


_EDITOR_TITLES = {
    "Edytuj – NOWE",
    "Edytuj – STARE",
    "Dodaj – NOWE",
    "Dodaj – STARE",
}


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


def _find_editor_header(window: tk.Toplevel) -> ttk.Frame | None:
    for child in window.winfo_children():
        if not isinstance(child, ttk.Frame):
            continue
        direct = child.winfo_children()
        if not any(isinstance(item, ttk.Notebook) for item in direct):
            continue
        for item in direct:
            if isinstance(item, ttk.Frame):
                return item
    return None


def _field_value_widget(window: tk.Toplevel, label_text: str) -> tk.Misc | None:
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
            label_info = label.grid_info()
            row = int(label_info.get("row", -1))
        except Exception:
            continue
        for sibling in parent.winfo_children():
            if sibling is label:
                continue
            try:
                info = sibling.grid_info()
                if int(info.get("row", -2)) == row and int(info.get("column", -1)) == 1:
                    return sibling
            except Exception:
                continue
    return None


def _entry_value_from_field(window: tk.Toplevel, label_text: str) -> str:
    holder = _field_value_widget(window, label_text)
    if holder is None:
        return ""
    widgets = [holder, *_all_descendants(holder)]
    for widget in widgets:
        if isinstance(widget, (ttk.Entry, ttk.Combobox, tk.Entry)):
            try:
                return str(widget.get() or "").strip()
            except Exception:
                continue
    return ""


def _image_label_value(window: tk.Toplevel) -> str:
    holder = _field_value_widget(window, "Obraz")
    if holder is None:
        return ""
    for widget in _all_descendants(holder):
        if not isinstance(widget, ttk.Label):
            continue
        text = _widget_text(widget)
        if text:
            return text
    return ""


def _candidate_path(base: Path, raw: str) -> Path | None:
    cleaned = str(raw or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if candidate.is_absolute() and candidate.is_file():
        return candidate
    for value in (base / cleaned, base / "media" / candidate.name):
        try:
            if value.is_file():
                return value
        except Exception:
            continue
    return None


def _preview_path(window: tk.Toplevel) -> Path | None:
    """Resolve the image currently selected in the active editor."""

    try:
        import gui_narzedzia as tools_gui

        base = Path(tools_gui._resolve_tools_dir())
    except Exception:
        return None

    current_label = _image_label_value(window)
    if current_label == "—":
        return None
    if current_label and not current_label.lower().endswith(" pliki"):
        first_name = current_label.split(",", 1)[0].strip()
        resolved = _candidate_path(base, first_name)
        if resolved is not None:
            return resolved

    nr = _entry_value_from_field(window, "Numer (3 cyfry)")
    if not nr:
        return None
    try:
        doc = tools_gui._read_tool(nr)
    except Exception:
        doc = None
    if not isinstance(doc, dict):
        return None

    candidates: list[str] = []
    images = doc.get("obrazy")
    if isinstance(images, list):
        candidates.extend(str(item) for item in images if str(item or "").strip())
    elif isinstance(images, str) and images.strip():
        candidates.append(images.strip())
    legacy = doc.get("obraz")
    if isinstance(legacy, str) and legacy.strip() and legacy.strip() not in candidates:
        candidates.append(legacy.strip())
    dxf_png = doc.get("dxf_png")
    if isinstance(dxf_png, str) and dxf_png.strip():
        candidates.append(dxf_png.strip())

    for candidate in candidates:
        resolved = _candidate_path(base, candidate)
        if resolved is not None:
            return resolved
    return None


def _load_photo(path: Path, master: tk.Misc, max_size: tuple[int, int]):
    try:
        from PIL import Image, ImageTk

        with Image.open(path) as source:
            image = source.copy()
        image.thumbnail(max_size)
        return ImageTk.PhotoImage(image, master=master)
    except Exception:
        pass

    try:
        photo = tk.PhotoImage(master=master, file=str(path))
        width = max(1, int(photo.width()))
        height = max(1, int(photo.height()))
        sx = max(1, (width + max_size[0] - 1) // max_size[0])
        sy = max(1, (height + max_size[1] - 1) // max_size[1])
        factor = max(sx, sy)
        return photo.subsample(factor, factor) if factor > 1 else photo
    except Exception:
        return None


def _refresh_thumbnail(window: tk.Toplevel, label: ttk.Label) -> None:
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

    photo = _load_photo(path, label, (220, 150))
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


def _open_full_preview(window: tk.Toplevel, thumb: ttk.Label) -> None:
    path = _preview_path(window)
    if path is None:
        return

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
    photo = _load_photo(path, preview, max_size)

    image_label = ttk.Label(frame, style="WM.Card.TLabel")
    image_label.pack(fill="both", expand=True)
    if photo is not None:
        image_label.configure(image=photo)
        image_label._wm_editor_photo = photo  # type: ignore[attr-defined]
    else:
        image_label.configure(text=f"Nie można otworzyć obrazu:\n{os.path.basename(path)}")

    ttk.Button(
        frame,
        text="Zamknij",
        command=preview.destroy,
        style="WM.Side.TButton",
    ).pack(anchor="e", pady=(10, 0))
    preview.bind("<Escape>", lambda _event: preview.destroy())

    try:
        preview.update_idletasks()
        width = max(520, int(preview.winfo_reqwidth()))
        height = max(360, int(preview.winfo_reqheight()))
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

    header = _find_editor_header(window)
    if header is None:
        return False

    holder = ttk.Frame(header, style="WM.Card.TFrame", padding=(8, 2))
    holder.pack(side="right", padx=(12, 12), fill="y")
    ttk.Label(
        holder,
        text="Podgląd narzędzia",
        style="WM.Muted.TLabel",
    ).pack(anchor="center")
    thumb = ttk.Label(
        holder,
        text="Brak zdjęcia\nnarzędzia",
        style="WM.Card.TLabel",
        anchor="center",
        justify="center",
        cursor="hand2",
        width=28,
    )
    thumb.pack(fill="both", expand=True, pady=(4, 2))
    ttk.Label(
        holder,
        text="Kliknij, aby powiększyć",
        style="WM.Muted.TLabel",
    ).pack(anchor="center")

    thumb.bind("<Button-1>", lambda _event: _open_full_preview(window, thumb))

    refresh_job: dict[str, Any] = {"id": None}

    def _schedule_refresh(_event: Any = None) -> None:
        try:
            previous = refresh_job.get("id")
            if previous:
                window.after_cancel(previous)
        except Exception:
            pass
        try:
            refresh_job["id"] = window.after(180, lambda: _refresh_thumbnail(window, thumb))
        except Exception:
            refresh_job["id"] = None

    window.bind("<FocusIn>", _schedule_refresh, add="+")
    window.bind("<ButtonRelease-1>", _schedule_refresh, add="+")
    _schedule_refresh()

    try:
        current_w = max(980, int(window.winfo_reqwidth()))
        current_h = max(700, int(window.winfo_reqheight()))
        window.minsize(current_w, current_h)
    except Exception:
        pass

    window._wm_editor_variant_ready = True  # type: ignore[attr-defined]
    return True


def install_tools_editor_variant_runtime() -> None:
    """Install optional card/thumbnail decoration for the shared NN/SN editor."""

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
            if attempt < 4:
                try:
                    self.after(80, lambda: _try(attempt + 1))
                except Exception:
                    pass

        try:
            self.after(80, _try)
        except Exception:
            pass

    tk.Toplevel.__init__ = _init_with_editor_variant
    tk.Toplevel._wm_tools_editor_variant_runtime = True  # type: ignore[attr-defined]
