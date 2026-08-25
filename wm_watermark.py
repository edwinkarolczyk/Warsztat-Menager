"""Globalny znak wodny Warsztat Menager: PROGRAM W TRAKCIE ROZWOJU.

Moduł jest celowo samodzielny, aby można było go dołączyć bez ingerencji
w istniejące moduły GUI. Ustawienie jest przechowywane jako
``ui.show_development_watermark`` w config.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:  # PIL jest opcjonalne
    Image = ImageDraw = ImageFont = ImageTk = None  # type: ignore

KEY = "ui.show_development_watermark"
DEFAULT_ENABLED = True
TEXT = "PROGRAM W TRAKCIE ROZWOJU"
ANGLE = 25


def _config_path() -> Path | None:
    env = os.environ.get("WM_CONFIG_FILE")
    if env:
        return Path(env).expanduser()
    try:
        import start
        manager = getattr(start, "CONFIG_MANAGER", None)
        path = getattr(manager, "config_path", None)
        if path:
            return Path(path)
        path = getattr(start, "CONFIG_PATH", None)
        if path:
            return Path(path)
    except Exception:
        pass
    return Path("config.json")


def _read_enabled() -> bool:
    path = _config_path()
    try:
        if path and path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            ui = data.get("ui", {})
            value = ui.get("show_development_watermark", DEFAULT_ENABLED)
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
    except Exception:
        pass
    return DEFAULT_ENABLED


def set_enabled(enabled: bool) -> bool:
    """Zapisz stan znaku wodnego do config.json."""
    path = _config_path()
    if path is None:
        return False
    try:
        data = {}
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        ui = data.setdefault("ui", {})
        if not isinstance(ui, dict):
            ui = {}
            data["ui"] = ui
        ui["show_development_watermark"] = bool(enabled)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _font(size: int):
    if ImageFont is None:
        return None
    candidates = [
        r"C:\\Windows\\Fonts\\segoeuib.ttf",
        r"C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _make_image(root: tk.Misc):
    if Image is None or ImageDraw is None or ImageTk is None:
        return None
    try:
        width = max(900, root.winfo_width())
        height = max(500, root.winfo_height())
        font = _font(max(46, min(92, int(min(width, height) * 0.075))))
        if font is None:
            return None
        box = ImageDraw.Draw(Image.new("RGBA", (10, 10), (0, 0, 0, 0))).textbbox((0, 0), TEXT, font=font)
        tw = box[2] - box[0]
        th = box[3] - box[1]
        pad = 70
        canvas = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((pad, pad), TEXT, font=font, fill=(185, 185, 185, 58), stroke_width=2, stroke_fill=(20, 20, 20, 28))
        rotated = canvas.rotate(ANGLE, expand=True, resample=Image.Resampling.BICUBIC)
        return ImageTk.PhotoImage(rotated)
    except Exception:
        return None


class DevelopmentWatermark:
    """Nieblokująca warstwa znaku wodnego dla głównego okna Tk."""

    def __init__(self, root: tk.Misc):
        self.root = root
        self.label: tk.Label | None = None
        self.photo = None
        self._last_enabled: bool | None = None
        self._job = None
        self._refresh()
        self._schedule()

    def _schedule(self):
        try:
            self._job = self.root.after(900, self._tick)
        except Exception:
            self._job = None

    def _tick(self):
        try:
            if not self.root.winfo_exists():
                return
            enabled = _read_enabled()
            if enabled != self._last_enabled or (enabled and self.label is None):
                self._refresh()
            elif enabled and self.label is not None:
                self.label.place(relx=0.5, rely=0.5, anchor="center")
            self._schedule()
        except Exception:
            self._job = None

    def _refresh(self):
        enabled = _read_enabled()
        self._last_enabled = enabled
        if not enabled:
            if self.label is not None:
                try:
                    self.label.place_forget()
                except Exception:
                    pass
            return

        if self.label is None:
            self.label = tk.Label(self.root, bd=0, highlightthickness=0, relief="flat", cursor="arrow")
        self.photo = _make_image(self.root)
        if self.photo is not None:
            self.label.configure(image=self.photo, text="", bg=self.root.cget("bg"))
        else:
            self.label.configure(image="", text=TEXT, font=("Segoe UI", 56, "bold"), fg="#666666", bg=self.root.cget("bg"))
        try:
            self.label.configure(state="disabled")
        except Exception:
            pass
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        try:
            self.label.lift()
        except Exception:
            pass


def install(root: tk.Misc) -> DevelopmentWatermark:
    existing = getattr(root, "_wm_development_watermark", None)
    if existing is not None:
        return existing
    overlay = DevelopmentWatermark(root)
    setattr(root, "_wm_development_watermark", overlay)
    return overlay


def patch_mainloop() -> None:
    """Automatycznie instaluje znak wodny po zbudowaniu głównego GUI."""
    original = getattr(tk.Misc, "mainloop", None)
    if original is None or getattr(tk.Misc, "_wm_watermark_patched", False):
        return

    def _mainloop(self, *args, **kwargs):
        try:
            install(self)
        except Exception:
            pass
        return original(self, *args, **kwargs)

    tk.Misc.mainloop = _mainloop
    tk.Misc._wm_watermark_patched = True


def patch_settings_module(module) -> None:
    """Dodaje opcję do istniejącego panelu ustawień bez modyfikacji jego logiki."""
    cls = getattr(module, "SettingsPanel", None)
    if cls is None or getattr(cls, "_wm_watermark_patched", False):
        return
    original_build = getattr(cls, "_build_ui", None)
    if not callable(original_build):
        return

    def _build_ui(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        try:
            frame = getattr(self, "_footer_frame", None)
            if frame is None:
                return result
            var = tk.BooleanVar(master=frame, value=_read_enabled())
            check = tk.Checkbutton(
                frame,
                text="Pokaż znak wodny „PROGRAM W TRAKCIE ROZWOJU”",
                variable=var,
                anchor="w",
                command=lambda: _settings_changed(self, var.get()),
            )
            check.grid(row=1, column=0, sticky="w", pady=(4, 0))
            self._wm_watermark_var = var
            self._wm_watermark_check = check
        except Exception:
            pass
        return result

    cls._build_ui = _build_ui
    cls._wm_watermark_patched = True


def _settings_changed(panel, enabled: bool) -> None:
    set_enabled(enabled)
    try:
        root = panel.master.winfo_toplevel()
        overlay = getattr(root, "_wm_development_watermark", None)
        if overlay is None:
            overlay = install(root)
        overlay._refresh()
    except Exception:
        pass
