# renderer.py — Widok Hali (Renderer)
# Wersja pliku: 1.0.0
# Data: 2025-09-18
# Zmiany:
# - Kropki statusu: sprawna (zielona), modyfikacja (żółta), awaria (czerwona migająca)
# - Overlay "NIE UŻYWAĆ" przy awarii
# - Tooltip (hover) z treścią zależną od statusu + czasy (awaria / sprawna od)
# - Klik → okno opisu (Toplevel, zawsze na wierzchu, jedno okno na maszynę)
# - Miniatura z media.preview_url (fallback: grafiki/machine_placeholder.png)
# - Cache obrazów i okien, logi po polsku
#
# Uwaga: Ten plik nie zmienia formatu danych. Pola "czas" i "media" są opcjonalne.
#        Działa także z dotychczasowym maszynopiskiem (id, nazwa, hala, pozycja, status).

from __future__ import annotations

import datetime as dt
import io
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import tkinter as tk

from .const import BG_GRID_COLOR, GRID_STEP, HALL_OUTLINE
from .models import Machine as ModelMachine, WallSegment

try:
    from PIL import Image, ImageTk  # Pillow

    PIL_OK = True
except Exception as _e:
    PIL_OK = False

try:  # pragma: no cover - logger opcjonalny w testach
    from logger import log_akcja as _log
except Exception:  # pragma: no cover - fallback
    def _log(msg: str) -> None:  # type: ignore
        print(msg)

try:
    # urllib tylko do pobrania miniatury (1s timeout)
    import urllib.request as _url
except Exception:
    _url = None

# ========== KONFIG ==========

STATUS_STYLE = {
    "sprawna": {"color": "#10B981", "blink": False, "overlay": False, "label": "Sprawna"},
    "modyfikacja": {"color": "#F59E0B", "blink": False, "overlay": False, "label": "Modyfikacja"},
    "awaria": {"color": "#EF4444", "blink": True, "overlay": True, "label": "Awaria"},
}
DEFAULT_STATUS = "sprawna"
BLINK_MS = 500  # miganie czerwonej kropki
TOOLTIP_DELAY_MS = 200
TOOLTIP_PAD = 16
DOT_RADIUS = 5  # 10x10

PLACEHOLDER_PATH = os.path.join("grafiki", "machine_placeholder.png")

# Ciemny motyw lokalnie (nie naruszamy globalnego theme)
BG_DARK = "#121212"
FG_LIGHT = "#DDDDDD"
FG_MUTED = "#AAAAAA"

# ========== POMOCNICZE ==========


def _now() -> dt.datetime:
    return dt.datetime.now()


def _parse_iso(ts: Optional[str]) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def _fmt_duration(start: Optional[dt.datetime], end: Optional[dt.datetime] = None) -> Optional[str]:
    if not start:
        return None
    end = end or _now()
    delta = end - start
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 0:
        total_minutes = 0
    days, rem_min = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rem_min, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _safe_get(d: dict, path: List[str], default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _uwaga_text(uwaga) -> Optional[str]:
    # uwaga może być obiektem lub stringiem
    if uwaga is None:
        return None
    if isinstance(uwaga, str):
        return uwaga.strip() or None
    if isinstance(uwaga, dict):
        typ = (uwaga.get("typ") or "").strip()
        opis = (uwaga.get("opis") or "").strip()
        if typ and opis:
            return f"{typ}: {opis}"
        return typ or opis or None
    return None


# ========== KLASY ==========


@dataclass
class RendererMachine:
    raw: dict

    @property
    def id(self) -> str:
        return str(self.raw.get("id", ""))

    @property
    def name(self) -> str:
        return str(self.raw.get("nazwa", self.id or "Nieznana maszyna"))

    @property
    def hall(self) -> int:
        return int(self.raw.get("hala", 1))

    @property
    def pos(self) -> Dict[str, int]:
        p = self.raw.get("pozycja") or {}
        return {"x": int(p.get("x", 0)), "y": int(p.get("y", 0))}

    @property
    def size(self) -> Dict[str, int]:
        s = self.raw.get("rozmiar") or {}
        return {"w": int(s.get("w", 80)), "h": int(s.get("h", 60))}

    @property
    def status(self) -> str:
        st = (self.raw.get("status") or DEFAULT_STATUS).lower()
        return st if st in STATUS_STYLE else DEFAULT_STATUS

    @property
    def time_since_status(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe_get(self.raw, ["czas", "status_since"]))

    @property
    def awaria_start(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe_get(self.raw, ["czas", "awaria_start"]))

    @property
    def last_awaria_end(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe_get(self.raw, ["czas", "last_awaria_end"]))

    @property
    def uwaga_text(self) -> Optional[str]:
        return _uwaga_text(self.raw.get("uwaga"))

    @property
    def awaria_comment(self) -> Optional[str]:
        s = (self.raw.get("komentarz_awarii") or "").strip()
        return s or None

    @property
    def preview_url(self) -> Optional[str]:
        return _safe_get(self.raw, ["media", "preview_url"])


class Tooltip:
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.win: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None

    def show_after(self, ms: int, x: int, y: int, lines: List[str]) -> None:
        self.cancel()
        self._after_id = self.parent.after(ms, lambda: self._show(x, y, lines))

    def move(self, x: int, y: int) -> None:
        if self.win:
            self.win.geometry(f"+{x}+{y}")

    def _show(self, x: int, y: int, lines: List[str]) -> None:
        self.close()
        win = tk.Toplevel(self.parent)
        win.overrideredirect(True)
        win.configure(bg=BG_DARK)
        # prosta ramka
        frame = tk.Frame(
            win,
            bg=BG_DARK,
            bd=1,
            highlightthickness=1,
            highlightbackground="#333333",
        )
        frame.pack(fill="both", expand=True)
        for line in lines:
            lbl = tk.Label(
                frame,
                text=line,
                bg=BG_DARK,
                fg=FG_LIGHT,
                anchor="w",
                justify="left",
            )
            lbl.pack(fill="x", padx=8, pady=(6 if not frame.children else 2))
        win.geometry(f"+{x}+{y}")
        self.win = win

    def close(self) -> None:
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None

    def cancel(self) -> None:
        if self._after_id:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None


class Renderer:
    """Renderer widoku hali z obsługą statusów, tooltipów i okien detali."""

    def __init__(self, root: tk.Tk, canvas: tk.Canvas, machines: List[dict]):
        self.root = root
        self.canvas = canvas
        self.machines_raw = machines
        self.machines: List[RendererMachine] = [RendererMachine(m) for m in machines]

        self._items_by_id: Dict[str, int] = {}
        self._dot_items_by_id: Dict[str, int] = {}
        self._blink_state = True
        self._blink_job: Optional[str] = None

        self._tooltip = Tooltip(self.canvas)
        self._hover_machine_id: Optional[str] = None

        self._preview_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._details_windows: Dict[str, tk.Toplevel] = {}

        self._draw_all()
        self._install_blink()

    # ========== RYSOWANIE ==========

    def _draw_all(self) -> None:
        self.canvas.delete("all")
        self._items_by_id.clear()
        self._dot_items_by_id.clear()

        for machine in self.machines:
            self._draw_machine_tile(machine)

    def _draw_machine_tile(self, machine: RendererMachine) -> None:
        x, y = machine.pos["x"], machine.pos["y"]
        width, height = machine.size["w"], machine.size["h"]

        rect = self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill="#1F2937",
            outline="#374151",
            width=1,
            tags=(f"machine:{machine.id}", "machine"),
        )
        self._items_by_id[machine.id] = rect

        self.canvas.create_text(
            x + 8,
            y + 10,
            text=f"hala nr {machine.hall}",
            anchor="w",
            fill=FG_MUTED,
            font=("Segoe UI", 9),
            tags=(f"machine:{machine.id}",),
        )

        self.canvas.create_text(
            x + 8,
            y + height / 2,
            text=machine.name,
            anchor="w",
            fill=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            tags=(f"machine:{machine.id}",),
        )

        self._draw_status_dot(machine, x, y, width, height)

        if STATUS_STYLE[machine.status]["overlay"]:
            self._draw_awaria_overlay(machine, x, y, width, height)

        tag = f"machine:{machine.id}"
        self.canvas.tag_bind(tag, "<Enter>", lambda event, mid=machine.id: self._on_hover_enter(mid, event))
        self.canvas.tag_bind(tag, "<Leave>", lambda event, mid=machine.id: self._on_hover_leave(mid, event))
        self.canvas.tag_bind(tag, "<Motion>", lambda event, mid=machine.id: self._on_hover_motion(mid, event))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, mid=machine.id: self._on_click(mid))

        print(f"[WM-DBG][HALA] Rysuję maszynę id={machine.id} status={machine.status}")

    def _draw_status_dot(self, machine: RendererMachine, x: int, y: int, width: int, height: int) -> None:
        cfg = STATUS_STYLE.get(machine.status, STATUS_STYLE[DEFAULT_STATUS])
        color = cfg["color"]

        cx = x + width - DOT_RADIUS - 6
        cy = y + DOT_RADIUS + 6

        dot = self.canvas.create_oval(
            cx - DOT_RADIUS,
            cy - DOT_RADIUS,
            cx + DOT_RADIUS,
            cy + DOT_RADIUS,
            fill=color,
            outline="",
            tags=(f"machine:{machine.id}",),
        )
        self._dot_items_by_id[machine.id] = dot
        print(f"[WM-DBG][HALA] Rysuję status={machine.status} (kropka) dla id={machine.id}")

    def _draw_awaria_overlay(self, machine: RendererMachine, x: int, y: int, width: int, height: int) -> None:
        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill="#7F1D1D",
            stipple="gray25",
            outline="",
            tags=(f"machine:{machine.id}",),
        )
        self.canvas.create_text(
            x + width / 2,
            y + height / 2,
            text="NIE UŻYWAĆ",
            fill="#FFE4E6",
            font=("Segoe UI", 11, "bold"),
            tags=(f"machine:{machine.id}",),
        )
        print(f"[WM-DBG][HALA] Overlay awaria dla id={machine.id}")

    # ========== MIGANIE ==========

    def _install_blink(self) -> None:
        if self._blink_job:
            try:
                self.root.after_cancel(self._blink_job)
            except Exception:
                pass
        self._blink_job = self.root.after(BLINK_MS, self._blink_tick)

    def _blink_tick(self) -> None:
        self._blink_state = not self._blink_state
        for machine_id, item in self._dot_items_by_id.items():
            machine = self._machine_by_id(machine_id)
            if not machine:
                continue
            if STATUS_STYLE.get(machine.status, {}).get("blink"):
                try:
                    state = "hidden" if not self._blink_state else "normal"
                    self.canvas.itemconfigure(item, state=state)
                except Exception:
                    pass
        self._install_blink()

    # ========== HOVER / TOOLTIP ==========

    def _on_hover_enter(self, machine_id: str, event: tk.Event) -> None:
        self._hover_machine_id = machine_id
        mx, my = event.x_root + TOOLTIP_PAD, event.y_root + TOOLTIP_PAD
        lines = self._tooltip_lines(machine_id)
        self._tooltip.show_after(TOOLTIP_DELAY_MS, mx, my, lines)
        print(f"[WM-DBG][HALA] Tooltip ENTER id={machine_id}")

    def _on_hover_motion(self, machine_id: str, event: tk.Event) -> None:
        if self._hover_machine_id != machine_id:
            return
        self._tooltip.move(event.x_root + TOOLTIP_PAD, event.y_root + TOOLTIP_PAD)

    def _on_hover_leave(self, machine_id: str, _event: tk.Event) -> None:
        if self._hover_machine_id == machine_id:
            self._hover_machine_id = None
        self._tooltip.cancel()
        self._tooltip.close()
        print(f"[WM-DBG][HALA] Tooltip LEAVE id={machine_id}")

    def _tooltip_lines(self, machine_id: str) -> List[str]:
        machine = self._machine_by_id(machine_id)
        if not machine:
            return ["Maszyna nieznana"]

        label = STATUS_STYLE.get(machine.status, STATUS_STYLE[DEFAULT_STATUS])["label"]
        lines = [f"{machine.name}  ({machine.id})", f"Hala: {machine.hall}", f"Status: {label}"]

        if machine.status == "awaria":
            start = machine.awaria_start or machine.time_since_status
            dur = _fmt_duration(start)
            if dur:
                lines.append(f"Awaria: {dur}")
            lines.append("NIE UŻYWAĆ")
        elif machine.status == "modyfikacja":
            uwaga = machine.uwaga_text
            if uwaga:
                lines.append(f"Do zrobienia: {uwaga}")
            if machine.last_awaria_end:
                lines.append(f"Sprawna od: {_fmt_duration(machine.last_awaria_end)}")
        else:
            if machine.last_awaria_end:
                lines.append(f"Sprawna od: {_fmt_duration(machine.last_awaria_end)}")

        return lines

    # ========== KLIK / OKNO OPISU ==========

    def _on_click(self, machine_id: str) -> None:
        print(f"[WM-DBG][HALA] Klik na maszynie id={machine_id}")
        self._open_machine_details(machine_id)

    def _open_machine_details(self, machine_id: str) -> None:
        machine = self._machine_by_id(machine_id)
        if not machine:
            return

        if machine_id in self._details_windows:
            try:
                window = self._details_windows[machine_id]
                window.deiconify()
                window.lift()
                window.focus_force()
                print(f"[WM-DBG][HALA] Okno opisu istnieje — fokus id={machine_id}")
                return
            except Exception:
                pass

        top = tk.Toplevel(self.root)
        top.title(f"Maszyna {machine.id} — opis")
        top.configure(bg=BG_DARK)
        try:
            top.wm_attributes("-topmost", True)
        except Exception:
            pass

        self._details_windows[machine_id] = top
        top.protocol("WM_DELETE_WINDOW", lambda mid=machine_id: self._close_details(mid))
        top.bind("<Escape>", lambda _event, mid=machine_id: self._close_details(mid))

        wrap = tk.Frame(top, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        header = tk.Frame(wrap, bg=BG_DARK)
        header.pack(fill="x")
        name_lbl = tk.Label(
            header,
            text=f"{machine.name}  ({machine.id})",
            bg=BG_DARK,
            fg=FG_LIGHT,
            font=("Segoe UI", 12, "bold"),
        )
        name_lbl.pack(side="left")

        status_color = STATUS_STYLE[machine.status]["color"]
        dot = tk.Canvas(header, width=12, height=12, bg=BG_DARK, highlightthickness=0)
        dot.create_oval(2, 2, 10, 10, fill=status_color, outline="")
        dot.pack(side="left", padx=8, pady=2)

        main = tk.Frame(wrap, bg=BG_DARK)
        main.pack(fill="x", pady=8)

        preview_frame = tk.Frame(
            main,
            bg=BG_DARK,
            highlightbackground=status_color,
            highlightthickness=2,
            bd=0,
        )
        preview_frame.pack(side="left", padx=(0, 12))
        preview_lbl = tk.Label(preview_frame, bg=BG_DARK)
        preview_lbl.pack(padx=4, pady=4)

        img = self._get_preview_image(machine)
        if img is not None:
            preview_lbl.configure(image=img)
            preview_lbl.image = img

        info = tk.Frame(main, bg=BG_DARK)
        info.pack(side="left", fill="both", expand=True)

        label = STATUS_STYLE[machine.status]["label"]
        tk.Label(info, text=f"Hala: {machine.hall}", bg=BG_DARK, fg=FG_LIGHT).pack(anchor="w")
        tk.Label(info, text=f"Status: {label}", bg=BG_DARK, fg=FG_LIGHT).pack(anchor="w")

        if machine.status == "awaria":
            start = machine.awaria_start or machine.time_since_status
            dur = _fmt_duration(start)
            if dur:
                tk.Label(info, text=f"Awaria: {dur}", bg=BG_DARK, fg="#FFD1D1").pack(anchor="w")
            tk.Label(
                info,
                text="NIE UŻYWAĆ",
                bg=BG_DARK,
                fg="#FFC7C7",
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w")
            if machine.awaria_comment:
                tk.Label(
                    info,
                    text=f"Powód awarii: {machine.awaria_comment}",
                    bg=BG_DARK,
                    fg=FG_LIGHT,
                ).pack(anchor="w")
        elif machine.status == "modyfikacja":
            if machine.uwaga_text:
                tk.Label(
                    info,
                    text=f"Do zrobienia: {machine.uwaga_text}",
                    bg=BG_DARK,
                    fg=FG_LIGHT,
                ).pack(anchor="w")
            if machine.last_awaria_end:
                tk.Label(
                    info,
                    text=f"Sprawna od: {_fmt_duration(machine.last_awaria_end)}",
                    bg=BG_DARK,
                    fg=FG_LIGHT,
                ).pack(anchor="w")
        else:
            if machine.last_awaria_end:
                tk.Label(
                    info,
                    text=f"Sprawna od: {_fmt_duration(machine.last_awaria_end)}",
                    bg=BG_DARK,
                    fg=FG_LIGHT,
                ).pack(anchor="w")

        footer = tk.Frame(wrap, bg=BG_DARK)
        footer.pack(fill="x", pady=(8, 0))
        close_btn = tk.Button(footer, text="Zamknij", command=lambda mid=machine.id: self._close_details(mid))
        close_btn.pack(side="right")

        print(f"[WM-DBG][HALA] Okno opisu maszyny id={machine.id}")

    def _close_details(self, machine_id: str) -> None:
        win = self._details_windows.pop(machine_id, None)
        if win:
            try:
                win.destroy()
            except Exception:
                pass

    # ========== ZDJĘCIA ==========

    def _get_preview_image(self, machine: RendererMachine, max_width: int = 256) -> Optional[ImageTk.PhotoImage]:
        if not PIL_OK:
            print("[ERROR][HALA] Pillow nie jest dostępny – miniatura wyłączona")
            return None

        if machine.id in self._preview_cache:
            return self._preview_cache[machine.id]

        img: Optional[Image.Image]
        img = None

        if machine.preview_url and _url is not None:
            try:
                print(f"[WM-DBG][HALA] Ładuję miniaturę z URL: {machine.preview_url}")
                with _url.urlopen(machine.preview_url, timeout=1) as resp:
                    data = resp.read()
                img = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception as exc:
                print(f"[ERROR][HALA] Nie udało się pobrać miniatury z URL ({exc}); używam placeholdera")

        if img is None:
            try:
                img = Image.open(PLACEHOLDER_PATH).convert("RGB")
            except Exception as exc:
                print(
                    f"[ERROR][HALA] Brak placeholdera ({PLACEHOLDER_PATH}). Miniatura wyłączona. {exc}",
                )
                return None

        width, height = img.size
        if width > max_width:
            ratio = max_width / float(width)
            img = img.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)

        tkimg = ImageTk.PhotoImage(img)
        self._preview_cache[machine.id] = tkimg
        return tkimg

    # ========== POMOC ==========

    def _machine_by_id(self, machine_id: str) -> Optional[RendererMachine]:
        for machine in self.machines:
            if machine.id == machine_id:
                return machine
        return None


def draw_background(canvas: tk.Canvas, path: str, width: int, height: int) -> None:
    """Rysuj tło z pliku ``path`` lub szachownicę gdy plik nie istnieje."""

    try:
        img = tk.PhotoImage(file=path)
        canvas.image = img  # type: ignore[attr-defined]
        canvas.create_image(0, 0, image=img, anchor="nw", tags=("background",))
    except Exception:
        _log(f"[HALA][WARN] Brak pliku tła {path}")
        size = 20
        for y_pos in range(0, height, size):
            for x_pos in range(0, width, size):
                fill = "#cccccc" if (x_pos // size + y_pos // size) % 2 == 0 else "#eeeeee"
                canvas.create_rectangle(
                    x_pos,
                    y_pos,
                    x_pos + size,
                    y_pos + size,
                    fill=fill,
                    outline=fill,
                    tags=("background",),
                )
    canvas.tag_lower("background")


def draw_grid(canvas: tk.Canvas, width: int, height: int) -> None:
    """Rysuj siatkę o kroku ``GRID_STEP``."""

    for x_pos in range(0, width, GRID_STEP):
        canvas.create_line(
            x_pos,
            0,
            x_pos,
            height,
            fill=BG_GRID_COLOR,
            tags=("grid",),
        )
    for y_pos in range(0, height, GRID_STEP):
        canvas.create_line(
            0,
            y_pos,
            width,
            y_pos,
            fill=BG_GRID_COLOR,
            tags=("grid",),
        )
    canvas.tag_lower("grid")


def draw_walls(canvas: tk.Canvas, walls: List[WallSegment]) -> None:
    """Rysuj segmenty ścian."""

    for wall in walls:
        canvas.create_line(
            wall.x1,
            wall.y1,
            wall.x2,
            wall.y2,
            width=2,
            fill=HALL_OUTLINE,
            tags=("walls",),
        )


def draw_machine(canvas: tk.Canvas, machine: ModelMachine) -> int:
    """Rysuj pojedynczą maszynę jako małe kółko."""

    radius = 5
    item = canvas.create_oval(
        machine.x - radius,
        machine.y - radius,
        machine.x + radius,
        machine.y + radius,
        fill="blue",
        tags=("machines", f"machine:{machine.id}"),
    )
    return item


def draw_status_overlay(canvas: tk.Canvas, machine: ModelMachine) -> None:
    """Rysuj nakładkę informującą o statusie maszyny."""

    if machine.status == "OK":
        return
    color = "red" if machine.status == "AWARIA" else "orange"
    canvas.create_text(
        machine.x,
        machine.y - 10,
        text=machine.status,
        fill=color,
        tags=("overlays",),
    )


__all__ = [
    "Renderer",
    "RendererMachine",
    "draw_background",
    "draw_grid",
    "draw_walls",
    "draw_machine",
    "draw_status_overlay",
]

