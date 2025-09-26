from __future__ import annotations

import json
import tkinter as tk

from config.paths import get_path
from wm_log import dbg as wm_dbg, err as wm_err

__all__ = [
    "Renderer",
    # legacy stubs — dla zgodności ze starymi importami
    "draw_background",
    "draw_grid",
    "draw_machine",
    "draw_status_overlay",
    "draw_walls",
]

# Kolory statusów
STATUS_COLORS = {
    "sprawna":     "#22c55e",  # zielony
    "modyfikacja": "#eab308",  # żółty
    "awaria":      "#ef4444",  # czerwony (miga)
}
DOT_TEXT = "#ffffff"

# Helpers for legacy compatibility -------------------------------------------------

def _coerce_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _canvas_size(canvas: tk.Canvas) -> tuple[int, int]:
    try:
        width = int(canvas.winfo_width() or canvas["width"])
        height = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        width, height = 640, 540
    return width, height


def _machine_attr(machine, key, default=None):
    if isinstance(machine, dict):
        return machine.get(key, default)
    return getattr(machine, key, default)


def _machine_position(machine) -> tuple[int, int]:
    pos = None
    if isinstance(machine, dict):
        pos = machine.get("pozycja")
    else:
        pos = getattr(machine, "pozycja", None)
    if isinstance(pos, dict):
        x = pos.get("x")
        y = pos.get("y")
    else:
        x = _machine_attr(machine, "x")
        y = _machine_attr(machine, "y")
    return _coerce_int(x, 50), _coerce_int(y, 50)

# ===========================
# Legacy: funkcje stubujące
# ===========================
def draw_background(canvas: tk.Canvas, grid_size: int = 24, bg: str = "#0f172a", line: str = "#1e293b", **_):
    """Rysuje jednolite tło + lekką siatkę (kompatybilnie z legacy API)."""

    width_override = _coerce_int(bg)
    height_override = _coerce_int(line)
    grid = _coerce_int(grid_size, default=24)
    if not grid or grid <= 0:
        grid = 24

    width, height = _canvas_size(canvas)
    if width_override is not None:
        width = width_override
        bg_color = "#0f172a"
    else:
        bg_color = bg
    if height_override is not None:
        height = height_override
        line_color = "#1e293b"
    else:
        line_color = line

    canvas.create_rectangle(0, 0, width, height, fill=bg_color, outline=bg_color, tags=("background",))
    for x in range(0, width, grid):
        canvas.create_line(x, 0, x, height, fill=line_color, width=1, tags=("grid",))
    for y in range(0, height, grid):
        canvas.create_line(0, y, width, y, fill=line_color, width=1, tags=("grid",))

def draw_grid(canvas: tk.Canvas, grid_size: int = 24, line: str = "#1e293b", **_):
    """Rysuje samą siatkę – wspiera stare wywołania (canvas, width, height)."""

    height_override = _coerce_int(line)
    if height_override is not None:
        width_override = _coerce_int(grid_size)
        grid = 24
        line_color = "#1e293b"
    else:
        width_override = None
        grid = _coerce_int(grid_size, default=24)
        if not grid or grid <= 0:
            grid = 24
        line_color = line

    width, height = _canvas_size(canvas)
    if width_override is not None:
        width = width_override
    if height_override is not None:
        height = height_override

    for x in range(0, width, grid):
        canvas.create_line(x, 0, x, height, fill=line_color, width=1, tags=("grid",))
    for y in range(0, height, grid):
        canvas.create_line(0, y, width, y, fill=line_color, width=1, tags=("grid",))

def draw_machine(canvas: tk.Canvas, machine, **_):
    """Legacy: narysuj pojedynczą maszynę (kropka + nr ewid.)."""

    mid = str(
        _machine_attr(machine, "id")
        or _machine_attr(machine, "nr_ewid")
        or "?"
    )
    status = str(_machine_attr(machine, "status", "sprawna")).lower()
    color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])
    x, y = _machine_position(machine)
    r = 14
    canvas.create_oval(
        x - r,
        y - r,
        x + r,
        y + r,
        fill=color,
        outline="#0b1220",
        width=1,
        tags=("machine", f"m:{mid}", f"status:{status}", "dot"),
    )
    canvas.create_text(
        x,
        y,
        text=mid,
        fill=DOT_TEXT,
        font=("Segoe UI", 9, "bold"),
        tags=("machine", f"m:{mid}", "label"),
    )


def draw_status_overlay(canvas: tk.Canvas, machine, **_):
    """Legacy: dodatkowy obrys przy awarii (wizualny akcent)."""

    if str(_machine_attr(machine, "status", "")).lower() != "awaria":
        return
    x, y = _machine_position(machine)
    r = 20
    canvas.create_oval(
        x - r,
        y - r,
        x + r,
        y + r,
        outline="#ef4444",
        width=2,
        dash=(3, 2),
        tags=("overlay",),
    )

def draw_walls(*_, **__):
    """Stub warstwy pomieszczeń/ścian — celowo puste (do implementacji)."""
    return


# ===========================
# Nowy renderer (zalecany)
# ===========================
class Renderer:
    """
    Renderer rysujący hale:
      - maszyny jako kropki z numerem ewidencyjnym na środku,
      - kolor kropki = status,
      - mruganie dla 'awaria',
      - focus/select, drag&drop (w trybie edycji),
      - lekkie tło + siatka.
    Callbacki:
      - on_select(mid: str)
      - on_move(mid: str, new_pos: {"x": int, "y": int})
    """

    def __init__(
        self,
        root: tk.Tk,
        canvas: tk.Canvas,
        machines: list | None = None,
    ):
        self.root = root
        self.canvas = canvas

        self.on_select = None
        self.on_move   = None

        self.machines: list[dict] = []
        self._items_by_id: dict[str, dict] = {}   # mid -> {"dot": id, "label": id, "r": int}
        self._blink_job = None
        self._blink_on  = True

        self._edit_mode = False
        self._drag_mid: str | None = None
        self._drag_off = (0, 0)

        self._bg_image: tk.PhotoImage | None = None
        self._bg_image_path: str = ""
        self._bg_image_loaded_from: str = ""
        self._machines_path: str = ""

        self._configure_data_sources(machines)

        self._draw_all()
        self._start_blink()

    # ---------- konfiguracja źródeł danych ----------
    def _configure_data_sources(self, machines: list | None) -> None:
        self._update_paths_from_config()
        self._load_config_background()
        if machines is None:
            machines = self._load_machines_from_config()
        self.machines = self._normalize_machines(machines)

    def _update_paths_from_config(self) -> None:
        try:
            machines_path = get_path("hall.machines_file")
        except Exception as exc:
            self._machines_path = ""
            wm_err("hala.renderer", "machines path resolve failed", exc)
        else:
            self._machines_path = machines_path.strip()
            if self._machines_path:
                wm_dbg("hala.renderer", "machines path resolved", path=self._machines_path)

        try:
            bg_path = get_path("hall.background_image", "")
        except Exception as exc:
            self._bg_image_path = ""
            wm_err("hala.renderer", "bg path resolve failed", exc)
        else:
            self._bg_image_path = bg_path.strip()
            if self._bg_image_path:
                wm_dbg("hala.renderer", "bg path resolved", bg=self._bg_image_path)

    def _load_config_background(self) -> None:
        if not self._bg_image_path:
            self._bg_image = None
            self._bg_image_loaded_from = ""
            return
        if (
            self._bg_image_loaded_from == self._bg_image_path
            and self._bg_image is not None
        ):
            return
        if self._load_bg_image(self._bg_image_path):
            self._bg_image_loaded_from = self._bg_image_path
        else:
            self._bg_image_loaded_from = ""

    def _load_bg_image(self, path: str) -> bool:
        try:
            self._bg_image = tk.PhotoImage(file=path)
        except Exception as exc:
            self._bg_image = None
            wm_err("hala.renderer", "bg load failed", exc, bg=path)
            return False
        wm_dbg("hala.renderer", "bg loaded", bg=path)
        return True

    def _load_machines_from_config(self) -> list[dict]:
        if not self._machines_path:
            return []
        try:
            with open(self._machines_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as exc:
            wm_err("hala.renderer", "machines load failed", exc, path=self._machines_path)
            return []
        except json.JSONDecodeError as exc:
            wm_err("hala.renderer", "machines load failed", exc, path=self._machines_path)
            return []
        except Exception as exc:
            wm_err("hala.renderer", "machines load failed", exc, path=self._machines_path)
            return []
        if isinstance(data, list):
            machines = [item for item in data if isinstance(item, dict)]
            wm_dbg("hala.renderer", "machines loaded", path=self._machines_path, count=len(machines))
            return machines
        return []

    def _normalize_machines(self, machines: list | None) -> list[dict]:
        if not machines:
            return []
        return [m for m in machines if isinstance(m, dict)]

    # ---------- rysowanie ----------
    def _dot_radius(self) -> int:
        """Promień kropki skalowany do szerokości canvasa (~110 kropek)."""
        try:
            w = int(self.canvas.winfo_width() or self.canvas["width"])
        except Exception:
            w = 640
        return max(10, min(16, w // 70))

    def _draw_all(self):
        self.canvas.delete("all")
        self._items_by_id.clear()

        # tło + siatka
        if self._bg_image is not None:
            self.canvas.create_image(
                0,
                0,
                image=self._bg_image,
                anchor="nw",
                tags=("background", "background-image"),
            )
            draw_grid(self.canvas, grid_size=24, line="#1e293b")
        else:
            draw_background(self.canvas, grid_size=24, bg="#0f172a", line="#1e293b")

        # maszyny
        for m in self.machines:
            self._draw_machine(m)

        # interakcje
        self.canvas.tag_bind("machine", "<Enter>", self._on_hover_enter)
        self.canvas.tag_bind("machine", "<Leave>", self._on_hover_leave)
        self.canvas.tag_bind("machine", "<Button-1>", self._on_click)
        self.canvas.tag_bind("machine", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("machine", "<ButtonRelease-1>", self._on_drop)

    def _draw_machine(self, m: dict):
        mid = str(m.get("id") or m.get("nr_ewid") or "").strip()
        if not mid:
            return
        x = int(m.get("pozycja", {}).get("x", 50))
        y = int(m.get("pozycja", {}).get("y", 50))
        r = self._dot_radius()
        status = (m.get("status") or "sprawna").lower()
        color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])

        dot = self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="#0b1220", width=1,
            tags=("machine", f"m:{mid}", f"status:{status}", "dot")
        )
        label = self.canvas.create_text(
            x, y,
            text=mid,
            fill=DOT_TEXT,
            font=("Segoe UI", 9, "bold"),
            tags=("machine", f"m:{mid}", "label")
        )
        self._items_by_id[mid] = {"dot": dot, "label": label, "r": r}

        # akcent awarii
        draw_status_overlay(self.canvas, m)

    # ---------- animacja mrugania awarii ----------
    def _start_blink(self):
        if self._blink_job:
            try:
                self.canvas.after_cancel(self._blink_job)
            except Exception:
                pass
        self._blink_job = self.canvas.after(500, self._blink_tick)

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        for mid, it in self._items_by_id.items():
            dot = it.get("dot")
            if not dot:
                continue
            tags = self.canvas.gettags(dot)
            # miga tylko awaria
            if tags and "status:awaria" in tags:
                state = "normal" if self._blink_on else "hidden"
                self.canvas.itemconfigure(dot, state=state)
                lbl = it.get("label")
                if lbl:
                    self.canvas.itemconfigure(lbl, state=state)
        self._start_blink()

    # ---------- API publiczne ----------
    def set_edit_mode(self, on: bool):
        self._edit_mode = bool(on)

    def reload(self, machines: list | None = None):
        self._configure_data_sources(machines)
        self._draw_all()

    def focus_machine(self, mid: str):
        """Wyróżnij maszynę i wywołaj on_select."""
        it = self._items_by_id.get(str(mid))
        if not it:
            return
        dot = it.get("dot")
        if dot:
            self.canvas.itemconfigure(dot, width=3, outline="#93c5fd")
        if callable(self.on_select):
            self.on_select(str(mid))

    # ---------- interakcje ----------
    def _mid_from_event(self, event) -> str | None:
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return None
        for t in self.canvas.gettags(item):
            if t.startswith("m:"):
                return t.split(":", 1)[1]
        return None

    def _oval_center(self, oid):
        x1, y1, x2, y2 = self.canvas.coords(oid)
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _on_click(self, event):
        mid = self._mid_from_event(event)
        if not mid:
            return
        if callable(self.on_select):
            self.on_select(mid)
        if not self._edit_mode:
            return
        it = self._items_by_id.get(mid)
        if not it:
            return
        cx, cy = self._oval_center(it["dot"])
        self._drag_mid = mid
        self._drag_off = (event.x - cx, event.y - cy)

    def _on_drag(self, event):
        if not self._edit_mode or not self._drag_mid:
            return
        it = self._items_by_id.get(self._drag_mid)
        if not it:
            return
        r = it["r"]
        cx = event.x - self._drag_off[0]
        cy = event.y - self._drag_off[1]
        self.canvas.coords(it["dot"], cx - r, cy - r, cx + r, cy + r)
        self.canvas.coords(it["label"], cx, cy)

    def _on_drop(self, event):
        if not self._edit_mode or not self._drag_mid:
            return
        it = self._items_by_id.get(self._drag_mid)
        if not it:
            return
        cx, cy = self._oval_center(it["dot"])
        if callable(self.on_move):
            self.on_move(self._drag_mid, {"x": int(cx), "y": int(cy)})
        self._drag_mid = None
        self._drag_off = (0, 0)

    # prosty tooltip tekstowy (bez miniatur, dla wydajności)
    def _on_hover_enter(self, event):
        mid = self._mid_from_event(event)
        if not mid:
            return
        m = None
        for r in self.machines:
            if str(r.get("id") or r.get("nr_ewid")) == str(mid):
                m = r
                break
        if not m:
            return
        # zamknij stary tooltip
        if hasattr(self, "_tooltip_win") and self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
        win = tk.Toplevel(self.canvas)
        win.wm_overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        x = self.canvas.winfo_rootx() + event.x + 16
        y = self.canvas.winfo_rooty() + event.y + 16
        win.wm_geometry(f"+{x}+{y}")
        lines = [
            f"nr ewid.: {mid}",
            f"Nazwa: {m.get('nazwa', '')}",
            f"Typ: {m.get('typ', '')}",
            f"Status: {m.get('status','')}",
            f"Od: {m.get('status_since','-')}",
        ]
        lbl = tk.Label(win, text="\n".join(lines), bg="#111827", fg="#e5e7eb",
                       font=("Segoe UI", 9), justify="left", bd=1, relief="solid")
        lbl.pack()
        self._tooltip_win = win

    def _on_hover_leave(self, _event):
        if hasattr(self, "_tooltip_win") and self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None
