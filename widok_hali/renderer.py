import os
import tkinter as tk
from tkinter import messagebox

ENABLE_TOOLTIP_IMAGE = False
HOVER_DELAY_MS = 150

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# --- eksport kompatybilny (stare importy nie wybuchną) ---
__all__ = [
    "Renderer",
    "draw_background",
    "draw_grid",
    "draw_machine",
    "draw_status_overlay",
    "draw_walls",
]

# --- konfiguracja kolorów statusów ---
STATUS_COLORS = {
    "sprawna":     "#22c55e",  # green
    "modyfikacja": "#eab308",  # yellow
    "awaria":      "#ef4444",  # red
}

DOT_TEXT = "#ffffff"


def _canvas_wh(canvas: tk.Canvas) -> tuple[int, int]:
    try:
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        w, h = 700, 520
    return w, h


# ------------------------
# Funkcje LEGACY (stuby)
# ------------------------
def draw_background(*args, grid_size: int = 24, bg: str = "#0f172a", line: str = "#1e293b", **kwargs) -> None:
    """
    Legacy: rysuje tło i siatkę. Akceptuje:
      draw_background(canvas, ...)
      draw_background(root, canvas, ...)
    """
    canvas = None
    if args and isinstance(args[0], tk.Canvas):
        canvas = args[0]
    elif len(args) >= 2 and isinstance(args[1], tk.Canvas):
        canvas = args[1]
    if not canvas:
        return
    w, h = _canvas_wh(canvas)
    canvas.create_rectangle(0, 0, w, h, fill=bg, outline=bg, tags=("background",))
    if grid_size > 0:
        for x in range(0, w, grid_size):
            canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
        for y in range(0, h, grid_size):
            canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))


def draw_grid(*args, grid_size: int = 24, line: str = "#1e293b", **kwargs) -> None:
    """Legacy: rysuje samą siatkę."""
    canvas = None
    if args and isinstance(args[0], tk.Canvas):
        canvas = args[0]
    elif len(args) >= 2 and isinstance(args[1], tk.Canvas):
        canvas = args[1]
    if not canvas:
        return
    w, h = _canvas_wh(canvas)
    for x in range(0, w, grid_size):
        canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
    for y in range(0, h, grid_size):
        canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))


def draw_machine(*args, **kwargs) -> None:
    """
    Legacy: rysuje pojedynczą maszynę jako kropkę z nr_ewid.
    W nowych ekranach i tak używamy klasy Renderer.
    """
    try:
        if "canvas" in kwargs and "machine" in kwargs:
            canvas, m = kwargs["canvas"], kwargs["machine"]
        elif len(args) >= 2:
            canvas, m = args[0], args[1]
        else:
            return
        mid = str(m.get("id") or m.get("nr_ewid") or "?")
        status = (m.get("status") or "sprawna").lower()
        color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])
        x = int(m.get("pozycja", {}).get("x", 50))
        y = int(m.get("pozycja", {}).get("y", 50))
        # promień dopasowany do rozmiaru canvas (~110 kropek)
        w, _ = _canvas_wh(canvas)
        r = max(10, min(16, w // 70))
        canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#0b1220", width=1,
                           tags=("machine", f"m:{mid}", f"status:{status}"))
        canvas.create_text(x, y, text=mid, fill=DOT_TEXT, font=("Segoe UI", 9, "bold"),
                           tags=("machine", f"m:{mid}", "label"))
    except Exception as e:
        print(f"[WARN][Renderer] draw_machine error: {e}")


def draw_status_overlay(*args, **kwargs) -> None:
    """Legacy: prosta nakładka statusu (np. awaria – czerwony obrys)."""
    try:
        if "canvas" in kwargs and "machine" in kwargs:
            canvas, m = kwargs["canvas"], kwargs["machine"]
        elif len(args) >= 2:
            canvas, m = args[0], args[1]
        else:
            return
        if (m.get("status") or "").lower() != "awaria":
            return
        x = int(m.get("pozycja", {}).get("x", 50))
        y = int(m.get("pozycja", {}).get("y", 50))
        r = 22
        canvas.create_oval(x - r, y - r, x + r, y + r, outline="#ef4444", width=2, dash=(3, 2),
                           tags=("overlay",))
    except Exception as e:
        print(f"[WARN][Renderer] draw_status_overlay error: {e}")


def draw_walls(*args, **kwargs) -> None:
    """
    Legacy: stub. Obsługa ścian/pomieszczeń dojdzie później.
    Funkcja celowo nic nie rysuje, ale istnieje żeby importy nie wybuchały.
    """
    return


# ------------------------
# Nowy Renderer — dot view
# ------------------------
class Renderer:
    """
    Hala jako kropki:
      • maszyna = kropka (kolor wg statusu) + nr_ewid NA KROPCE (max 3 cyfry)
      • do ~110 kropek na powiększonym canvasie
      • tryb Edycja: drag zapisuje środek kropki
      • awaria miga
    """
    def __init__(self, root: tk.Tk, canvas: tk.Canvas, machines: list[dict]):
        self.root = root
        self.canvas = canvas
        self.machines = machines or []
        self.on_select = None
        self.on_move = None
        self._edit_mode = False

        self._items_by_id: dict[str, dict] = {}
        self._blink_job = None
        self._blink_on = True

        # drag state
        self._drag_mid = None
        self._drag_off = (0, 0)

        self._tooltip_win: tk.Toplevel | None = None
        self._tooltip_img = None
        self._hover_job = None
        self._hover_mid = None
        self._hover_event = None

        self._draw_all()
        self._start_blink()

    # --- rysowanie ---
    def _dot_radius(self) -> int:
        w, _ = _canvas_wh(self.canvas)
        return max(10, min(16, w // 70))  # ~110 kropek na płótnie 700px

    def _draw_all(self):
        self.canvas.delete("all")
        self._items_by_id.clear()

        # tło + siatka subtelna
        draw_background(self.canvas, grid_size=24, bg="#0f172a", line="#1e293b")

        for m in self.machines:
            self._draw_machine(m)

        # bindy
        self.canvas.tag_bind("machine", "<Enter>", self._on_hover_enter)
        self.canvas.tag_bind("machine", "<Leave>", self._on_hover_leave)
        self.canvas.tag_bind("machine", "<Button-1>", self._on_click)
        self.canvas.tag_bind("machine", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("machine", "<ButtonRelease-1>", self._on_drop)

    def _draw_machine(self, m: dict):
        mid = str(m.get("id") or m.get("nr_ewid") or "")
        if not mid:
            return
        pos = m.get("pozycja") or {}
        cx, cy = int(pos.get("x", 50)), int(pos.get("y", 50))
        r = self._dot_radius()

        status = (m.get("status") or "sprawna").lower()
        color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])

        dot = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                      fill=color, outline="#0b1220", width=1,
                                      tags=("machine", f"m:{mid}", f"status:{status}", "dot"))
        label = self.canvas.create_text(cx, cy, text=mid, fill=DOT_TEXT,
                                        font=("Segoe UI", 9, "bold"),
                                        tags=("machine", f"m:{mid}", "label"))
        self._items_by_id[mid] = {"dot": dot, "label": label, "r": r}

        # ewentualny overlay
        draw_status_overlay(self.canvas, m)

    # --- mruganie awarii ---
    def _start_blink(self):
        if self._blink_job:
            self.canvas.after_cancel(self._blink_job)
        self._blink_job = self.canvas.after(500, self._blink_tick)

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        for mid, it in self._items_by_id.items():
            dot = it.get("dot")
            if not dot:
                continue
            tags = self.canvas.gettags(dot) or ()
            if "status:awaria" in tags:
                state = "normal" if self._blink_on else "hidden"
                self.canvas.itemconfigure(dot, state=state)
                lbl = it.get("label")
                if lbl:
                    self.canvas.itemconfigure(lbl, state=state)
        self._start_blink()

    # --- API publiczne ---
    def set_edit_mode(self, on: bool):
        self._edit_mode = bool(on)

    def reload(self, machines: list[dict]):
        self.machines = machines or []
        self._draw_all()

    def focus_machine(self, mid: str):
        it = self._items_by_id.get(str(mid))
        if not it:
            return
        dot = it.get("dot")
        if dot:
            self.canvas.itemconfigure(dot, width=3, outline="#93c5fd")
        if callable(getattr(self, "on_select", None)):
            self.on_select(str(mid))

    def _open_details(self, mid: str):
        m = None
        for r in self.machines:
            rid = str(r.get("id") or r.get("nr_ewid"))
            if rid == str(mid):
                m = r
                break
        if not m:
            messagebox.showerror("Maszyny", f"Nie znaleziono {mid}.")
            return
        win = tk.Toplevel(self.root)
        win.title(f"Maszyna {mid}")
        win.attributes("-topmost", True)
        txt = tk.Text(win, width=60, height=16)
        lines = []
        lines.append(f"ID: {mid}")
        lines.append(f"Nazwa: {m.get('nazwa','')}")
        lines.append(f"Typ: {m.get('typ','')}")
        lines.append(f"Hala: {m.get('hala','')}")
        lines.append(f"Status: {m.get('status','')}")
        if m.get("status_since"):
            lines.append(f"Status od: {m.get('status_since')}")
        if m.get("link"):
            lines.append(f"Link: {m.get('link')}")
        if m.get("miniatura_url"):
            lines.append(f"Miniatura: {m.get('miniatura_url')}")
        if m.get("opis"):
            lines.append("")
            lines.append("Opis:")
            lines.append(m.get("opis",""))
        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

    # --- interakcje ---
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
        return ( (x1 + x2) / 2.0, (y1 + y2) / 2.0 )

    def _on_click(self, event):
        mid = self._mid_from_event(event)
        if not mid:
            return
        if callable(getattr(self, "on_select", None)):
            self.on_select(mid)
        if not self._edit_mode:
            self._open_details(mid)
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
        if callable(getattr(self, "on_move", None)):
            self.on_move(self._drag_mid, {"x": int(cx), "y": int(cy)})
        self._drag_mid = None
        self._drag_off = (0, 0)

    # --- tooltip (lekki) ---
    def _on_hover_enter(self, event):
        mid = self._mid_from_event(event)
        if not mid:
            return

        if hasattr(self, "_hover_job") and self._hover_job:
            self.canvas.after_cancel(self._hover_job)
        self._hover_mid = mid
        self._hover_event = event
        self._hover_job = self.canvas.after(HOVER_DELAY_MS, self._show_tooltip)

    def _show_tooltip(self):
        mid = getattr(self, "_hover_mid", None)
        event = getattr(self, "_hover_event", None)
        if not mid or not event:
            return
        self._hover_job = None
        m = None
        for r in self.machines:
            if str(r.get("id") or r.get("nr_ewid")) == str(mid):
                m = r
                break
        if not m:
            return
        if self._tooltip_win:
            try: self._tooltip_win.destroy()
            except: pass

        win = tk.Toplevel(self.canvas)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        x = self.canvas.winfo_rootx() + event.x + 16
        y = self.canvas.winfo_rooty() + event.y + 16
        win.wm_geometry(f"+{x}+{y}")

        frm = tk.Frame(win, bg="#111827", bd=1, relief="solid")
        frm.pack()
        text = self._tooltip_text(m)
        tk.Label(frm, bg="#111827", fg="#e5e7eb", justify="left",
                 text=text, font=("Segoe UI", 9)).pack(padx=8, pady=6, side="left")

        if ENABLE_TOOLTIP_IMAGE:
            img = self._load_thumb(m)
            if img:
                self._tooltip_img = img
                tk.Label(frm, image=img, bg="#111827").pack(padx=8, pady=6, side="right")

        self._tooltip_win = win

    def _on_hover_leave(self, event):
        if hasattr(self, "_hover_job") and self._hover_job:
            self.canvas.after_cancel(self._hover_job)
            self._hover_job = None
        self._hover_mid = None
        self._hover_event = None
        if self._tooltip_win:
            try: self._tooltip_win.destroy()
            except: pass
            self._tooltip_win = None
            self._tooltip_img = None

    def _tooltip_text(self, m: dict) -> str:
        nr = str(m.get("id") or m.get("nr_ewid") or "")
        st = (m.get("status") or "sprawna").lower()
        since = m.get("status_since") or "-"
        return f"nr ewid.: {nr}\nNazwa: {m.get('nazwa','')}\nTyp: {m.get('typ','')}\nStatus: {st}\nOd: {since}"

    def _load_thumb(self, m: dict):
        path = m.get("miniatura_url") or (m.get("media", {}) or {}).get("preview_url") or ""
        fallback_png = os.path.join("grafiki", "machine_placeholder.png")
        for p in (path, fallback_png):
            if not p or not os.path.exists(p):
                continue
            # prefer PNG przez PhotoImage (mniej zależności)
            if p.lower().endswith(".png"):
                try:
                    img = tk.PhotoImage(file=p)
                    # pomniejsz do tooltips
                    scale = max(1, img.width() // 48)
                    return img.subsample(scale, scale)
                except Exception:
                    continue
            if Image and ImageTk:
                try:
                    im = Image.open(p); im.thumbnail((48, 48))
                    return ImageTk.PhotoImage(im)
                except Exception:
                    continue
        return None
