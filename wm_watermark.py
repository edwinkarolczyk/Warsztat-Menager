"""Globalny znak wodny WM: PROGRAM W TRAKCIE ROZWOJU.
# Plik: wm_watermark.py
# Wersja: 1.0.1
# Zmiany 1.0.1:
# - Usunięto kosztowną regenerację grafiki co 700 ms.
# - Znak wodny jest przerysowywany tylko po zmianie stanu lub rozmiaru okna.
# - Dodano bezpieczne anulowanie timera i obsługę Configure.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:
    Image = ImageDraw = ImageFont = ImageTk = None

KEY = "ui.show_development_watermark"
DEFAULT_ENABLED = True
TEXT = "PROGRAM W TRAKCIE ROZWOJU"
ANGLE = 25
_TRANSPARENT = "#010203"


def _config_path() -> Path:
    env = os.environ.get("WM_CONFIG_FILE")
    return Path(env).expanduser() if env else Path("config.json")


def _read_enabled() -> bool:
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        value = (data.get("ui") or {}).get(KEY.split(".", 1)[1], DEFAULT_ENABLED)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    except Exception:
        return DEFAULT_ENABLED


def set_enabled(enabled: bool) -> bool:
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(data, dict):
            data = {}
        ui = data.setdefault("ui", {})
        if not isinstance(ui, dict):
            ui = {}
            data["ui"] = ui
        ui[KEY.split(".", 1)[1]] = bool(enabled)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def _font(size: int):
    if ImageFont is None:
        return None
    for path in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _make_image(width: int, height: int):
    if Image is None or ImageDraw is None or ImageTk is None:
        return None
    try:
        font = _font(max(52, min(100, int(min(width, height) * 0.075))))
        if font is None:
            return None
        probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        box = ImageDraw.Draw(probe).textbbox((0, 0), TEXT, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        pad = 80
        img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text(
            (pad, pad),
            TEXT,
            font=font,
            fill=(185, 185, 185, 62),
            stroke_width=2,
            stroke_fill=(20, 20, 20, 30),
        )
        return img.rotate(ANGLE, expand=True, resample=Image.Resampling.BICUBIC)
    except Exception:
        return None


def _make_clickthrough(win: tk.Misc) -> None:
    if os.name != "nt":
        return
    try:
        hwnd = win.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    except Exception:
        pass


class DevelopmentWatermark:
    def __init__(self, root: tk.Misc):
        self.root = root
        self.win: tk.Toplevel | None = None
        self.label: tk.Label | None = None
        self.photo = None
        self._last_enabled: bool | None = None
        self._last_size: tuple[int, int] | None = None
        self._job = None
        self._configure_bound = False
        self._create()
        self._bind_configure()
        self._refresh(force=True)
        self._schedule_check()

    def _create(self) -> None:
        try:
            self.win = tk.Toplevel(self.root)
            self.win.overrideredirect(True)
            self.win.configure(bg=_TRANSPARENT)
            try:
                self.win.attributes("-transparentcolor", _TRANSPARENT)
            except Exception:
                pass
            self.label = tk.Label(
                self.win,
                bg=_TRANSPARENT,
                bd=0,
                highlightthickness=0,
            )
            self.label.pack(expand=True, fill="both")
            self.win.update_idletasks()
            _make_clickthrough(self.win)
        except Exception:
            self.win = None
            self.label = None

    def _bind_configure(self) -> None:
        if self._configure_bound:
            return
        try:
            self.root.bind("<Configure>", self._on_root_configure, add="+")
            self._configure_bound = True
        except Exception:
            pass

    def _on_root_configure(self, _event=None) -> None:
        if self._last_enabled:
            self._refresh(force=False)

    def _get_geometry(self) -> tuple[int, int, int, int]:
        self.root.update_idletasks()
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty()
        w = max(900, self.root.winfo_width())
        h = max(500, self.root.winfo_height())
        return x, y, w, h

    def _position(self, force_image: bool = False) -> None:
        if self.win is None or self.label is None:
            return
        try:
            x, y, w, h = self._get_geometry()
            size = (w, h)
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            if force_image or size != self._last_size:
                self.photo = _make_image(w, h)
                if self.photo is not None:
                    self.label.configure(image=self.photo, text="", bg=_TRANSPARENT)
                else:
                    self.label.configure(
                        image="",
                        text=TEXT,
                        font=("Segoe UI", 64, "bold"),
                        fg="#666666",
                        bg=_TRANSPARENT,
                    )
                self._last_size = size
        except Exception:
            pass

    def _refresh(self, force: bool = False) -> None:
        enabled = _read_enabled()
        state_changed = enabled != self._last_enabled
        self._last_enabled = enabled
        if self.win is None:
            return
        if enabled:
            self._position(force_image=force or state_changed)
            try:
                self.win.deiconify()
                self.win.lift()
            except Exception:
                pass
        else:
            try:
                self.win.withdraw()
            except Exception:
                pass

    def _schedule_check(self) -> None:
        try:
            if not self.root.winfo_exists():
                return
            enabled = _read_enabled()
            if enabled != self._last_enabled:
                self._refresh(force=True)
            self._job = self.root.after(1200, self._schedule_check)
        except Exception:
            self._job = None

    def refresh(self) -> None:
        self._refresh(force=True)

    def destroy(self) -> None:
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        try:
            if self._configure_bound:
                self.root.unbind("<Configure>")
        except Exception:
            pass
        try:
            if self.win is not None:
                self.win.destroy()
        except Exception:
            pass
        self.win = None
        self.label = None
        self.photo = None


def install(root: tk.Misc) -> DevelopmentWatermark:
    existing = getattr(root, "_wm_development_watermark", None)
    if existing is not None:
        existing.refresh()
        return existing
    overlay = DevelopmentWatermark(root)
    setattr(root, "_wm_development_watermark", overlay)
    return overlay
