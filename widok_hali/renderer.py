import math
import os
import tkinter as tk
from tkinter import messagebox

# upewnij się, że eksportujemy nazwy funkcyjne używane przez stary kod
try:
    __all__
except NameError:
    __all__ = []
for _name in ("Renderer", "draw_background", "draw_grid"):
    if _name not in __all__:
        __all__.append(_name)


def draw_grid(*args, grid_size: int = 24, line: str = "#1e293b") -> None:
    """
    Kompatybilna wstecznie funkcja rysująca samą SIATKĘ.
    Akceptuje oba warianty wywołania spotykane w projekcie:
      - draw_grid(canvas, ...)
      - draw_grid(root, canvas, ...)
    """

    if not args:
        return

    # wariant (canvas, ...)
    if isinstance(args[0], tk.Canvas):
        canvas = args[0]
    # wariant (root, canvas, ...)
    elif len(args) >= 2 and isinstance(args[1], tk.Canvas):
        canvas = args[1]
    else:
        return

    try:
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        # fallback – jeśli jeszcze nie zrealizowany layout
        w = int(canvas["width"]) if "width" in str(canvas.keys()) else 700
        h = int(canvas["height"]) if "height" in str(canvas.keys()) else 520

    # siatka
    if grid_size and grid_size > 0:
        for x in range(0, w, grid_size):
            canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
        for y in range(0, h, grid_size):
            canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))


def draw_background(
    *args,
    grid_size: int = 24,
    bg: str = "#0f172a",
    line: str = "#1e293b",
) -> None:
    """
    Kompatybilna wstecznie funkcja tła Hali.
    Akceptuje oba warianty wywołania spotykane w projekcie:
      - draw_background(canvas, ...)
      - draw_background(root, canvas, ...)
    Rysuje jednolite tło i siatkę co 'grid_size' px.
    """

    if not args:
        return

    # wariant (canvas, ...)
    if isinstance(args[0], tk.Canvas):
        canvas = args[0]
    # wariant (root, canvas, ...)
    elif len(args) >= 2 and isinstance(args[1], tk.Canvas):
        canvas = args[1]
    else:
        return

    try:
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
    except Exception:
        # fallback – jeśli jeszcze nie zrealizowany layout
        w = int(canvas["width"]) if "width" in str(canvas.keys()) else 700
        h = int(canvas["height"]) if "height" in str(canvas.keys()) else 520

    # tło
    canvas.create_rectangle(0, 0, w, h, fill=bg, outline=bg, tags=("background",))

    # siatka
    if grid_size and grid_size > 0:
        for x in range(0, w, grid_size):
            canvas.create_line(x, 0, x, h, fill=line, width=1, tags=("grid",))
        for y in range(0, h, grid_size):
            canvas.create_line(0, y, w, y, fill=line, width=1, tags=("grid",))

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

STATUS_COLORS = {
    "sprawna":      "#22c55e",  # zielony
    "modyfikacja":  "#eab308",  # żółty
    "awaria":       "#ef4444",  # czerwony
}

DOT_RADIUS = 14             # promień kropki (pasuje pod ~110 punktów na powiększonym canvasie)
DOT_TEXT_COLOR = "#ffffff"  # numer ewidencyjny na kropce

class Renderer:
    """
    HALA — WIDOK KROPEK:
      • każda maszyna = kropka (kolor wg statusu) + numer ewidencyjny wewnątrz
      • do 110 kropek na powiększonym canvasie
      • drag&drop w trybie 'Edycja' (przesuwanie środka kropki)
      • miganie 'awaria'
      • tooltip i okno szczegółów pozostały kompatybilne
    """
    def __init__(self, root: tk.Tk, canvas: tk.Canvas, machines: list[dict]):
        self.root = root
        self.canvas = canvas
        self.machines = machines or []
        self.on_select = None
        self.on_move = None
        self._edit_mode = False

        self._items_by_id: dict[str, dict] = {}  # mid -> {"dot":..,"label":..}
        self._blink_on = True
        self._blink_job = None

        # state dla drag
        self._drag_mid = None
        self._drag_off = (0, 0)   # offset od środka

        # tooltip
        self._tooltip_win: tk.Toplevel | None = None
        self._tooltip_img = None

        self._draw_all()
        self._start_blink()

    # ---------- rysowanie ----------
    def _draw_all(self):
        self.canvas.delete("all")
        self._items_by_id.clear()
        for m in self.machines:
            self._draw_machine(m)

        # bindy ogólne
        self.canvas.tag_bind("machine", "<Enter>", self._on_hover_enter)
        self.canvas.tag_bind("machine", "<Leave>", self._on_hover_leave)
        self.canvas.tag_bind("machine", "<Button-1>", self._on_click)
        self.canvas.tag_bind("machine", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("machine", "<ButtonRelease-1>", self._on_drop)

    def _draw_machine(self, m: dict):
        mid = str(m.get("id") or m.get("nr_ewid") or "")
        if not mid:
            return

        # pozycja interpretowana jako ŚRODEK kropki
        pos = m.get("pozycja") or {}
        cx, cy = int(pos.get("x", 50)), int(pos.get("y", 50))
        r = DOT_RADIUS

        status = (m.get("status") or "sprawna").lower()
        color = STATUS_COLORS.get(status, STATUS_COLORS["sprawna"])

        # Rysujemy kropkę + numer ewidencyjny
        dot = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                      fill=color, outline="#0b1220", width=1,
                                      tags=("machine", f"m:{mid}", f"status:{status}", "dot"))
        nr = str(m.get("id") or m.get("nr_ewid") or "")
        label = self.canvas.create_text(cx, cy, text=nr, fill=DOT_TEXT_COLOR,
                                        font=("Segoe UI", 9, "bold"),
                                        tags=("machine", f"m:{mid}", "label"))

        self._items_by_id[mid] = {"dot": dot, "label": label, "r": r}

    # ---------- miganie awarii ----------
    def _start_blink(self):
        if self._blink_job:
            self.canvas.after_cancel(self._blink_job)
        self._blink_job = self.canvas.after(500, self._blink_tick)

    def _blink_tick(self):
        self._blink_on = not self._blink_on
        for mid, it in self._items_by_id.items():
            dot = it.get("dot")
            if not dot: continue
            tags = self.canvas.gettags(dot) or ()
            is_awaria = any(t == "status:awaria" for t in tags)
            if is_awaria:
                self.canvas.itemconfigure(dot, state=("normal" if self._blink_on else "hidden"))
                # etykieta ma znikać razem z kropką
                lbl = it.get("label")
                if lbl:
                    self.canvas.itemconfigure(lbl, state=("normal" if self._blink_on else "hidden"))
        self._start_blink()

    # ---------- API publiczne ----------
    def set_edit_mode(self, on: bool):
        self._edit_mode = bool(on)

    def reload(self, machines: list[dict]):
        self.machines = machines or []
        self._draw_all()

    def focus_machine(self, mid: str):
        it = self._items_by_id.get(str(mid))
        if not it: return
        dot = it.get("dot")
        if dot:
            # podświetl kontur kropki
            self.canvas.itemconfigure(dot, width=3, outline="#93c5fd")
        if callable(getattr(self, "on_select", None)):
            self.on_select(mid)

    def _open_details(self, mid: str):
        m = None
        for r in self.machines:
            rid = str(r.get("id") or r.get("nr_ewid"))
            if rid == str(mid):
                m = r; break
        if not m:
            messagebox.showerror("Maszyny", f"Nie znaleziono {mid}."); return
        win = tk.Toplevel(self.root); win.title(f"Maszyna {mid}")
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

    # ---------- interakcje (klik/drag) ----------
    def _center_from_oval(self, oid):
        x1, y1, x2, y2 = self.canvas.coords(oid)
        return ( (x1 + x2) / 2.0, (y1 + y2) / 2.0 )

    def _mid_from_event(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item) if item else ()
        mid = None
        for t in tags or ():
            if t.startswith("m:"):
                mid = t.split(":",1)[1]
                break
        return mid

    def _on_click(self, event):
        mid = self._mid_from_event(event)
        if not mid: return
        if callable(getattr(self, "on_select", None)):
            self.on_select(mid)
        if not self._edit_mode:
            self._open_details(mid)
            return
        # w edycji — zapamiętaj offset od środka
        it = self._items_by_id.get(mid); 
        if not it: return
        cx, cy = self._center_from_oval(it["dot"])
        self._drag_mid = mid
        self._drag_off = (event.x - cx, event.y - cy)

    def _on_drag(self, event):
        if not self._edit_mode: return
        mid = self._drag_mid
        if not mid: return
        it = self._items_by_id.get(mid); 
        if not it: return
        r = it["r"]
        cx = event.x - self._drag_off[0]
        cy = event.y - self._drag_off[1]
        # przesuń dot i label
        self.canvas.coords(it["dot"], cx - r, cy - r, cx + r, cy + r)
        self.canvas.coords(it["label"], cx, cy)

    def _on_drop(self, event):
        if not self._edit_mode: return
        mid = self._drag_mid
        if not mid: return
        it = self._items_by_id.get(mid); 
        if not it: return
        cx, cy = self._center_from_oval(it["dot"])
        # zgłoś zapis nowej pozycji (środek kropki)
        if callable(getattr(self, "on_move", None)):
            self.on_move(mid, {"x": int(cx), "y": int(cy)})
        self._drag_mid = None
        self._drag_off = (0, 0)

    # ---------- tooltip ----------
    def _on_hover_enter(self, event):
        mid = self._mid_from_event(event)
        if not mid: return
        m = None
        for r in self.machines:
            if str(r.get("id") or r.get("nr_ewid")) == str(mid):
                m = r; break
        if not m: return

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
        txt = tk.Label(frm, bg="#111827", fg="#e5e7eb", justify="left",
                       text=self._tooltip_text(m), font=("Segoe UI", 9))
        txt.pack(padx=8, pady=6, side="left")

        img = self._load_thumb(m)
        if img:
            self._tooltip_img = img
            tk.Label(frm, image=img, bg="#111827").pack(padx=8, pady=6, side="right")

        self._tooltip_win = win

    def _on_hover_leave(self, event):
        if self._tooltip_win:
            try: self._tooltip_win.destroy()
            except: pass
            self._tooltip_win = None
            self._tooltip_img = None

    def _tooltip_text(self, m: dict) -> str:
        name = m.get("nazwa","")
        typ  = m.get("typ","")
        st   = (m.get("status") or "sprawna").lower()
        since= m.get("status_since") or "-"
        nr   = str(m.get("id") or m.get("nr_ewid") or "")
        return f"nr ewid.: {nr}\nNazwa: {name}\nTyp: {typ}\nStatus: {st}\nOd: {since}"

    # ---------- miniatury (tooltip/okno opisu) ----------
    def _load_thumb(self, m: dict):
        path = m.get("miniatura_url") or (m.get("media", {}) or {}).get("preview_url") or ""
        fallback_png = os.path.join("grafiki", "machine_placeholder.png")
        try_paths = [p for p in [path, fallback_png] if p]
        for p in try_paths:
            if not os.path.exists(p):
                continue
            if p.lower().endswith(".png"):
                try:
                    img = tk.PhotoImage(file=p)
                    return img.subsample(max(1, img.width()//48), max(1, img.height()//48))
                except Exception as e:
                    print(f"[WARN][Maszyny] PNG load fail {p}: {e}")
                    continue
            else:
                if Image is None or ImageTk is None:
                    continue
                try:
                    im = Image.open(p)
                    im.thumbnail((48,48))
                    return ImageTk.PhotoImage(im)
                except Exception as e:
                    print(f"[WARN][Maszyny] JPG load fail {p}: {e}")
                    continue
        return None
