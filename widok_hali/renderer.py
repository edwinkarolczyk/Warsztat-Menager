from __future__ import annotations
import tkinter as tk

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

# ===========================
# Legacy: funkcje stubujące
# ===========================
def draw_background(canvas: tk.Canvas, grid_size: int = 24, bg: str = "#0f172a", line: str = "#1e293b", **_):
    """Rysuje jednolite tło + lekką siatkę."""
    try:
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        # fallback
        w, h = 640, 540
    canvas.create_rectangle(0, 0, w, h, fill=bg, outline=bg, tags=("background",))
    # lekka siatka (wydajność lepsza niż gęsta co 4 px)
    for x in range(0, w, grid_size):
        canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
    for y in range(0, h, grid_size):
        canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))

def draw_grid(canvas: tk.Canvas, grid_size: int = 24, line: str = "#1e293b", **_):
    # dla kompatybilności — rysuje tylko siatkę na istniejącym tle
    try:
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        w, h = 640, 540
    for x in range(0, w, grid_size):
        canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
    for y in range(0, h, grid_size):
        canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))

def draw_machine(canvas: tk.Canvas, machine: dict, **_):
    """
    Legacy: narysuj pojedynczą maszynę (kropka + nr ewid.)
    Używane przez starsze miejsca, nie koliduje z klasą Renderer.
    """
    mid = str(machine.get("id") or machine.get("nr_ewid") or "?")
    status = (machine.get("status") or "sprawna").lower()
    color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])
    x = int(machine.get("pozycja", {}).get("x", 50))
    y = int(machine.get("pozycja", {}).get("y", 50))
    r = 14
    canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#0b1220", width=1,
                       tags=("machine", f"m:{mid}", f"status:{status}", "dot"))
    canvas.create_text(x, y, text=mid, fill=DOT_TEXT, font=("Segoe UI", 9, "bold"),
                       tags=("machine", f"m:{mid}", "label"))

def draw_status_overlay(canvas: tk.Canvas, machine: dict, **_):
    """Legacy: dodatkowy obrys przy awarii (wizualny akcent)."""
    if (machine.get("status") or "").lower() != "awaria":
        return
    x = int(machine.get("pozycja", {}).get("x", 50))
    y = int(machine.get("pozycja", {}).get("y", 50))
    r = 20
    canvas.create_oval(x - r, y - r, x + r, y + r, outline="#ef4444", width=2, dash=(3, 2),
                       tags=("overlay",))

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

    def __init__(self, root: tk.Tk, canvas: tk.Canvas, machines: list):
        self.root = root
        self.canvas = canvas
        self.machines = machines or []

        self.on_select = None
        self.on_move   = None

        self._items_by_id: dict[str, dict] = {}   # mid -> {"dot": id, "label": id, "r": int}
        self._blink_job = None
        self._blink_on  = True

        self._edit_mode = False
        self._drag_mid: str | None = None
        self._drag_off = (0, 0)

        self._draw_all()
        self._start_blink()

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

    def reload(self, machines: list):
        self.machines = machines or []
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
