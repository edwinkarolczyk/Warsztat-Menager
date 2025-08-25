# File: dashboard_demo_fs.py
# Version: 1.2.1
# Fullscreen dashboard Warsztat Menager z obsługą hal i awarii, integracja motywu ui_theme.py

import sys, os, json
import tkinter as tk
from tkinter import ttk, simpledialog
from math import ceil

try:
    from ui_theme import apply_theme
except Exception:
    apply_theme = lambda _: None

APP_TITLE = "Warsztat Menager - Dashboard (TEST)"

# ------------------ DATA LOADING ------------------
def load_awarie():
    path = "awarie.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return sum(1 for a in data if str(a.get("status", "")).lower() == "aktywna")
    except Exception:
        return 0

def load_hale():
    path = "hale.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_hale(hale_list):
    path = "hale.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hale_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Błąd zapisu hale.json:", e)

# Demo orders
def sample_orders():
    return [
        {"nr": "1002", "nazwa": "Przeglad okresowy", "maszyna": "Maszyna A", "status": "W toku"},
        {"nr": "1004", "nazwa": "Wymiana czesci", "maszyna": "Maszyna C", "status": "Nieprzypisane"},
        {"nr": "1005", "nazwa": "Naprawa silnika", "maszyna": "Maszyna B", "status": "W toku"},
        {"nr": "1006", "nazwa": "Regulacja napiecia", "maszyna": "Maszyna A", "status": "Zakonczone"},
    ]

def sample_list_short():
    return [
        {"nr": "1004", "nazwa": "Wymiana czesci"},
        {"nr": "1005", "nazwa": "Naprawa ukladu hamulcowego"},
        {"nr": "1007", "nazwa": "Przeglad techniczny"},
    ]

# ------------------ TILE ------------------
class WMTile(ttk.Frame):
    def __init__(self, parent, title, value, width=260, height=110):
        super().__init__(parent, style="WM.Card.TFrame")
        self["padding"] = 14
        ttk.Label(self, text=title, style="WM.Card.TLabel").pack(anchor="w")
        self.val = ttk.Label(self, text=value, style="WM.KPI.TLabel")
        self.val.pack(anchor="w", pady=(8, 0))
        self.grid_propagate(False)
        self.configure(width=width, height=height)

# ------------------ MINI HALA ------------------
class WMMiniHala(ttk.Frame):
    def __init__(self, parent, *, edit_mode=False):
        super().__init__(parent, style="WM.Card.TFrame", padding=12)
        self.edit_mode = edit_mode
        self.hale = load_hale()
        self.start_x = None
        self.start_y = None

        self.style = ttk.Style()
        bg = self.style.lookup("WM.Card.TFrame", "background")
        self.cv = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        self.cv.bind("<Configure>", self.on_resize)
        if self.edit_mode:
            self.cv.bind("<Button-1>", self.on_click)
            self.cv.bind("<B1-Motion>", self.on_drag)
            self.cv.bind("<ButtonRelease-1>", self.on_release)

        self.redraw()

    def on_resize(self, event):
        self.redraw()

    def redraw(self):
        self.cv.delete("all")
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        # Grid
        step = 40
        for x in range(0, w, step):
            self.cv.create_line(x, 0, x, h, fill="#2e323c")
        for y in range(0, h, step):
            self.cv.create_line(0, y, w, y, fill="#2e323c")
        # Hale
        for hala in self.hale:
            x1, y1, x2, y2 = hala["x1"], hala["y1"], hala["x2"], hala["y2"]
            self.cv.create_rectangle(x1, y1, x2, y2, outline="#ff4b4b", width=2)
            fg = self.style.lookup("WM.TLabel", "foreground")
            self.cv.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=hala["nazwa"], fill=fg)

    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return
        self.redraw()
        self.cv.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline="#ff4b4b", dash=(4, 2))

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
        name = simpledialog.askstring("Nowa hala", "Podaj nazwę hali:")
        if name:
            self.hale.append({
                "nazwa": name,
                "x1": self.start_x,
                "y1": self.start_y,
                "x2": event.x,
                "y2": event.y
            })
            save_hale(self.hale)
        self.start_x = None
        self.start_y = None
        self.redraw()

# ------------------ WYKRES ------------------
class WMSpark(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="WM.Card.TFrame", padding=12)
        ttk.Label(self, text="Zlecenia", style="WM.Card.TLabel").pack(anchor="w", pady=(0, 8))
        style = ttk.Style()
        bg = style.lookup("WM.Card.TFrame", "background")
        self.cv = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        self.redraw()

    def redraw(self):
        self.cv.delete("all")
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        self.cv.create_rectangle(6, 6, w - 6, h - 6, outline="#2e323c")
        pts = [
            (w * 0.05, h * 0.8),
            (w * 0.2, h * 0.6),
            (w * 0.35, h * 0.65),
            (w * 0.5, h * 0.55),
            (w * 0.65, h * 0.62),
            (w * 0.8, h * 0.57),
            (w * 0.95, h * 0.45)
        ]
        for i in range(len(pts) - 1):
            self.cv.create_line(*pts[i], *pts[i + 1], fill="#ff4b4b", width=2)
        for x, y in pts:
            self.cv.create_oval(x - 3, y - 3, x + 3, y + 3, outline="#ff4b4b", fill="#ff4b4b")

# ------------------ MAIN APP ------------------
class WMDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self._enable_dpi_awareness()
        apply_theme(self)

        try:
            self.state("zoomed")
        except:
            self.attributes("-fullscreen", True)

        self.edit_mode = False

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Sidebar
        side = ttk.Frame(self, style="WM.Side.TFrame", width=240)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        ttk.Label(side, text="WARSZTAT\nMENAGER", style="WM.H2.TLabel").pack(anchor="w", padx=18, pady=(20, 10))

        ttk.Button(side, text="Przełącz tryb edycji hal", style="WM.Side.TButton", command=self.toggle_edit_mode).pack(fill="x", padx=14, pady=6)

        ttk.Label(side, text="v1.2.1 - testowy motyw", style="WM.Muted.TLabel", font=("Segoe UI", 9)).pack(side="bottom", anchor="w", padx=18, pady=12)

        # Main
        main = ttk.Frame(self, style="WM.TFrame", padding=16)
        main.grid(row=0, column=1, sticky="nsew")
        ttk.Label(main, text="Warsztat Menager", style="WM.H1.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 14))

        # Tiles
        tiles = ttk.Frame(main, style="WM.TFrame")
        tiles.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            tiles.columnconfigure(i, weight=1)

        orders = sample_orders()
        nieprz = sum(1 for o in orders if o["status"].lower().startswith("nieprz"))
        wtoku = sum(1 for o in orders if o["status"] == "W toku")
        zako = sum(1 for o in orders if o["status"] == "Zakonczone")
        awarie = load_awarie()

        WMTile(tiles, "Nieprzypisane", str(nieprz)).grid(row=0, column=0, sticky="ew", padx=(0, 12))
        WMTile(tiles, "Zlecenia w toku", str(wtoku)).grid(row=0, column=1, sticky="ew", padx=12)
        WMTile(tiles, "Zakonczone", str(zako)).grid(row=0, column=2, sticky="ew", padx=12)
        WMTile(tiles, "Awarie", str(awarie)).grid(row=0, column=3, sticky="ew", padx=(12, 0))

        # Body
        body = ttk.Frame(main, style="WM.TFrame")
        body.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
        main.rowconfigure(2, weight=1)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # Table
        table_card = ttk.Frame(body, style="WM.Card.TFrame", padding=12)
        table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(table_card, text="Aktualnie Zlecenia", style="WM.Card.TLabel").pack(anchor="w", pady=(0, 8))
        cols = ("nr", "nazwa", "maszyna", "status")
        tv = ttk.Treeview(table_card, columns=cols, show="headings", style="WM.Treeview")
        for c, t in zip(cols, ["Nr", "Zlecenie", "Maszyna", "Status"]):
            tv.heading(c, text=t)
            tv.column(c, anchor="w", width=ceil(560 / len(cols)) if c != "nazwa" else 280)
        for r in orders:
            tv.insert("", "end", values=(r["nr"], r["nazwa"], r["maszyna"], r["status"]))
        tv.pack(fill="both", expand=True)

        # Right: spark + mini-hala
        right_top = ttk.Frame(body, style="WM.TFrame")
        right_top.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right_top.columnconfigure(0, weight=1)
        WMSpark(right_top).grid(row=0, column=0, sticky="nsew")

        mini_card = ttk.Frame(body, style="WM.Card.TFrame", padding=12)
        mini_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        ttk.Label(mini_card, text="Widok Hali", style="WM.Card.TLabel").pack(anchor="w", pady=(0, 8))
        self.mini_hala = WMMiniHala(mini_card, edit_mode=self.edit_mode)
        self.mini_hala.pack(fill="both", expand=True)

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        self.mini_hala.destroy()
        self.mini_hala = WMMiniHala(self.mini_hala.master, edit_mode=self.edit_mode)
        self.mini_hala.pack(fill="both", expand=True)

    def _enable_dpi_awareness(self):
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

if __name__ == "__main__":
    WMDashboard().mainloop()
