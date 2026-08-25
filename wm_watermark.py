"""Globalny znak wodny WM: PROGRAM W TRAKCIE ROZWOJU."""
from __future__ import annotations
import ctypes
import json
import os
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:
    Image = ImageDraw = ImageFont = ImageTk = None

KEY = "ui.show_development_watermark"
DEFAULT_ENABLED = True
TEXT = "PROGRAM W TRAKCIE ROZWOJU"
ANGLE = 25
_TRANSPARENT = "#010203"

def _config_path() -> Path | None:
    env = os.environ.get("WM_CONFIG_FILE")
    return Path(env).expanduser() if env else Path("config.json")

def _read_enabled() -> bool:
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        value = (data.get("ui") or {}).get("show_development_watermark", DEFAULT_ENABLED)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    except Exception:
        return DEFAULT_ENABLED

def set_enabled(enabled: bool) -> bool:
    try:
        path = _config_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(data, dict): data = {}
        ui = data.setdefault("ui", {})
        if not isinstance(ui, dict): ui = {}; data["ui"] = ui
        ui["show_development_watermark"] = bool(enabled)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
        return True
    except Exception:
        return False

def _font(size: int):
    if ImageFont is None: return None
    for path in (r"C:\\Windows\\Fonts\\segoeuib.ttf", r"C:\\Windows\\Fonts\\arialbd.ttf"):
        try: return ImageFont.truetype(path, size)
        except Exception: pass
    try: return ImageFont.load_default()
    except Exception: return None

def _make_image(width: int, height: int):
    if Image is None or ImageDraw is None or ImageTk is None: return None
    try:
        font = _font(max(52, min(100, int(min(width, height) * 0.075))))
        if font is None: return None
        probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        box = ImageDraw.Draw(probe).textbbox((0, 0), TEXT, font=font)
        tw, th = box[2]-box[0], box[3]-box[1]
        pad = 80
        img = Image.new("RGBA", (tw+pad*2, th+pad*2), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((pad,pad), TEXT, font=font, fill=(185,185,185,62), stroke_width=2, stroke_fill=(20,20,20,30))
        return img.rotate(ANGLE, expand=True, resample=Image.Resampling.BICUBIC)
    except Exception:
        return None

def _make_clickthrough(win):
    if os.name != "nt": return
    try:
        hwnd = win.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        user32 = ctypes.windll.user32
        get_long = user32.GetWindowLongW
        set_long = user32.SetWindowLongW
        style = get_long(hwnd, GWL_EXSTYLE)
        set_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    except Exception:
        pass

class DevelopmentWatermark:
    def __init__(self, root: tk.Misc):
        self.root = root
        self.win = None
        self.label = None
        self.photo = None
        self._last = None
        self._job = None
        self._create()
        self._tick()

    def _create(self):
        try:
            self.win = tk.Toplevel(self.root)
            self.win.overrideredirect(True)
            self.win.configure(bg=_TRANSPARENT)
            try: self.win.attributes("-transparentcolor", _TRANSPARENT)
            except Exception: pass
            self.label = tk.Label(self.win, bg=_TRANSPARENT, bd=0, highlightthickness=0)
            self.label.pack(expand=True, fill="both")
            self.win.update_idletasks()
            _make_clickthrough(self.win)
        except Exception:
            self.win = None

    def _position(self):
        if not self.win: return
        try:
            self.root.update_idletasks()
            x = self.root.winfo_rootx(); y = self.root.winfo_rooty()
            w = max(900, self.root.winfo_width()); h = max(500, self.root.winfo_height())
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            self.photo = _make_image(w, h)
            if self.photo is not None:
                self.label.configure(image=self.photo, text="", bg=_TRANSPARENT)
            else:
                self.label.configure(image="", text=TEXT, font=("Segoe UI", 64, "bold"), fg="#666666", bg=_TRANSPARENT)
        except Exception:
            pass

    def _refresh(self):
        enabled = _read_enabled()
        self._last = enabled
        if not self.win: return
        if enabled:
            self._position()
            try: self.win.deiconify(); self.win.lift()
            except Exception: pass
        else:
            try: self.win.withdraw()
            except Exception: pass

    def _tick(self):
        try:
            if not self.root.winfo_exists(): return
            enabled = _read_enabled()
            if enabled != self._last or (enabled and self.win): self._refresh()
            self._job = self.root.after(700, self._tick)
        except Exception:
            self._job = None

    def destroy(self):
        if self._job:
            try: self.root.after_cancel(self._job)
            except Exception: pass
        try: self.win.destroy()
        except Exception: pass

def install(root: tk.Misc) -> DevelopmentWatermark:
    existing = getattr(root, "_wm_development_watermark", None)
    if existing is not None:
        existing._refresh()
        return existing
    overlay = DevelopmentWatermark(root)
    setattr(root, "_wm_development_watermark", overlay)
    return overlay

