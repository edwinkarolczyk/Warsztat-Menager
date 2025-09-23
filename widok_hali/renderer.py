# widok_hali/renderer.py
# Wersja: 1.0.3 (2025-09-19)
# - statusy: zielona/żółta/czerwona(migająca), overlay "NIE UŻYWAĆ", tooltipy
# - okno szczegółów (topmost) z miniaturą
# - miniatura z URL (http/https) lub LOKALNY plik; fallback: grafiki/machine_placeholder.png
# - API do docka: set_edit_mode / on_select / on_move / focus_machine
# - drag&drop kafli w trybie Edycja + podświetlenie zaznaczenia

from __future__ import annotations

import datetime as dt
import io
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import tkinter as tk
from tkinter import messagebox, ttk

from .const import BG_GRID_COLOR, GRID_STEP, HALL_OUTLINE
from .models import Machine as ModelMachine, WallSegment

try:
    from utils_maszyny import PLACEHOLDER_PATH, apply_machine_updates
except Exception:  # pragma: no cover - fallback gdy moduł niedostępny
    PLACEHOLDER_PATH = os.path.join("grafiki", "machine_placeholder.png")

    def apply_machine_updates(machine: dict, updates: dict) -> bool:  # type: ignore
        if not isinstance(machine, dict):
            return False
        changed = False
        for key in ("nazwa", "opis", "status"):
            if key in updates and machine.get(key) != updates[key]:
                machine[key] = updates[key]
                changed = True
        if "hala" in updates:
            machine["hala"] = updates["hala"]
            changed = True
        if "miniatura" in updates:
            media = machine.setdefault("media", {})
            media["preview_url"] = updates["miniatura"]
            changed = True
        return changed

try:
    from PIL import Image, ImageTk

    PIL_OK = True
except Exception:
    PIL_OK = False

try:  # pragma: no cover - logger opcjonalny w testach
    from logger import log_akcja as _log
except Exception:  # pragma: no cover - fallback
    def _log(msg: str) -> None:  # type: ignore
        print(msg)

try:
    import urllib.request as _url
except Exception:
    _url = None


STATUS_STYLE = {
    "sprawna": {
        "color": "#10B981",
        "blink": False,
        "overlay": False,
        "label": "Sprawna",
    },
    "modyfikacja": {
        "color": "#F59E0B",
        "blink": False,
        "overlay": False,
        "label": "Modyfikacja",
    },
    "awaria": {
        "color": "#EF4444",
        "blink": True,
        "overlay": True,
        "label": "Awaria",
    },
}
DEFAULT_STATUS = "sprawna"
BLINK_MS = 500
TOOLTIP_DELAY_MS = 200
TOOLTIP_OFFSET = 16
DOT_RADIUS = 5

BG_DARK = "#121212"
FG_LIGHT = "#DDDDDD"
FG_MUTED = "#AAAAAA"


def _now() -> dt.datetime:
    return dt.datetime.now()


def _parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def _fmt_duration(
    start: Optional[dt.datetime],
    end: Optional[dt.datetime] = None,
) -> Optional[str]:
    if not start:
        return None
    end = end or _now()
    minutes = int((end - start).total_seconds() // 60)
    if minutes < 0:
        minutes = 0
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")
    return " ".join(parts)


def _safe(data: dict, path: List[str], default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _uwaga_to_text(uwaga) -> Optional[str]:
    if not uwaga:
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


def _is_url(value: str) -> bool:
    value = value.lower().strip()
    return value.startswith("http://") or value.startswith("https://")


def _to_int(value: Union[str, int, float, None], default: int = 0) -> int:
    try:
        if value is None:
            raise ValueError
        if isinstance(value, str):
            if not value.strip():
                raise ValueError
        return int(value)
    except Exception:
        return default


@dataclass
class Machine:
    raw: dict

    @property
    def id(self) -> str:
        return str(self.raw.get("id", ""))

    @property
    def name(self) -> str:
        return str(self.raw.get("nazwa", self.id or "Nieznana maszyna"))

    @property
    def type(self) -> str:
        return str(self.raw.get("typ") or self.raw.get("type") or "")

    @property
    def description(self) -> str:
        return str(self.raw.get("opis") or "")

    @property
    def hall(self) -> int:
        return _to_int(self.raw.get("hala"), 1)

    @property
    def pos(self) -> Dict[str, int]:
        raw_pos = self.raw.get("pozycja") or {}
        if not isinstance(raw_pos, dict):
            raw_pos = {}
        return {
            "x": _to_int(raw_pos.get("x"), 0),
            "y": _to_int(raw_pos.get("y"), 0),
        }

    @property
    def size(self) -> Dict[str, int]:
        raw_size = self.raw.get("rozmiar") or {}
        if not isinstance(raw_size, dict):
            raw_size = {}
        return {
            "w": _to_int(raw_size.get("w"), 80),
            "h": _to_int(raw_size.get("h"), 60),
        }

    @property
    def status(self) -> str:
        status = (self.raw.get("status") or DEFAULT_STATUS).lower()
        return status if status in STATUS_STYLE else DEFAULT_STATUS

    @property
    def time_since_status(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe(self.raw, ["czas", "status_since"]))

    @property
    def status_changed_at(self) -> Optional[dt.datetime]:
        return self.time_since_status

    @property
    def awaria_start(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe(self.raw, ["czas", "awaria_start"]))

    @property
    def last_awaria_end(self) -> Optional[dt.datetime]:
        return _parse_iso(_safe(self.raw, ["czas", "last_awaria_end"]))

    @property
    def uwaga_text(self) -> Optional[str]:
        return _uwaga_to_text(self.raw.get("uwaga"))

    @property
    def awaria_comment(self) -> Optional[str]:
        comment = (self.raw.get("komentarz_awarii") or "").strip()
        return comment or None

    @property
    def preview_url(self) -> Optional[str]:
        return _safe(self.raw, ["media", "preview_url"])


class Tooltip:
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.win: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None

    def show_after(
        self, delay_ms: int, x: int, y: int, lines: List[str]
    ) -> None:
        self.cancel()
        self._after_id = self.parent.after(
            delay_ms,
            lambda: self._show(x, y, lines),
        )

    def _show(self, x: int, y: int, lines: List[str]) -> None:
        self.close()
        window = tk.Toplevel(self.parent)
        window.overrideredirect(True)
        window.configure(bg=BG_DARK)

        frame = tk.Frame(
            window,
            bg=BG_DARK,
            bd=1,
            highlightthickness=1,
            highlightbackground="#333",
        )
        frame.pack(fill="both", expand=True)

        first = True
        for line in lines:
            padding = (6, 2) if first else (2, 2)
            first = False
            tk.Label(
                frame,
                text=line,
                bg=BG_DARK,
                fg=FG_LIGHT,
                anchor="w",
            ).pack(fill="x", padx=8, pady=padding)

        window.geometry(f"+{x}+{y}")
        self.win = window

    def move(self, x: int, y: int) -> None:
        if self.win:
            self.win.geometry(f"+{x}+{y}")

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
    """Renderer widoku hali."""

    def __init__(
        self,
        root: tk.Tk,
        canvas: tk.Canvas,
        machines: Optional[List[dict]] = None,
    ):
        self.root = root
        self.canvas = canvas
        self.machines: List[Machine] = [Machine(m) for m in machines or []]

        self._dot_items: Dict[str, int] = {}
        self._machine_items: Dict[str, List[int]] = {}
        self._blink_state = True
        self._blink_job: Optional[str] = None

        self._tooltip = Tooltip(self.canvas)
        self._hover_id: Optional[str] = None

        self._preview_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._details_windows: Dict[str, tk.Toplevel] = {}
        self._details_forms: Dict[str, dict] = {}
        self._selected_mid: Optional[str] = None
        self._selection_item: Optional[int] = None

        # tryb edycji i zewnętrzne callbacki
        self.edit_mode: bool = False
        self.on_select = None  # callable(machine_id: str)
        self.on_move = None  # callable(machine_id: str, new_pos: dict)
        self.on_update = None  # callable(machine_id: str, row: dict)
        self._drag_mid: Optional[str] = None
        self._drag_start: Tuple[int, int] = (0, 0)

        self.draw_all()
        self._start_blink()

    # public API -----------------------------------------------------
    def reload(self, machines: Optional[List[dict]]) -> None:
        self.machines = [Machine(m) for m in machines or []]
        self._preview_cache.clear()
        self.draw_all()
        for machine_id in list(self._details_windows.keys()):
            machine = self._by_id(machine_id)
            if machine:
                self._populate_details_form(machine_id, machine)
            else:
                self._close_details(machine_id)

    def set_edit_mode(self, enabled: bool) -> None:
        self.edit_mode = bool(enabled)

    def focus_machine(self, machine_id: str) -> None:
        """Zaznacz wskazaną maszynę i podnieś jej elementy."""

        if not machine_id:
            self._clear_selection()
            print("[WM-DBG][HALA] Focus — brak identyfikatora")
            return

        machine = self._by_id(machine_id)
        if not machine:
            self._clear_selection()
            print(f"[WM-DBG][HALA] Focus — nie znaleziono {machine_id}")
            return

        self._set_selected(machine_id)
        try:
            self.canvas.tag_raise(f"machine:{machine_id}")
        except Exception:
            pass

        window = self._details_windows.get(machine_id)
        if window:
            try:
                window.deiconify()
                window.lift()
                window.focus_force()
            except Exception:
                pass

        print(f"[WM-DBG][HALA] Focus {machine_id}")

    def draw_all(self) -> None:
        self.canvas.delete("all")
        self._dot_items.clear()
        self._machine_items.clear()
        self._drag_mid = None
        for machine in self.machines:
            self._draw_machine(machine)
        self._redraw_selection()

    def _register_item(self, machine_id: str, item_id: int | None) -> None:
        if not machine_id or item_id is None:
            return
        bucket = self._machine_items.setdefault(machine_id, [])
        bucket.append(item_id)

    # rendering ------------------------------------------------------
    def _draw_machine(self, machine: Machine) -> None:
        x, y = machine.pos["x"], machine.pos["y"]
        width, height = machine.size["w"], machine.size["h"]
        self._machine_items[machine.id] = []
        rect = self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill="#1F2937",
            outline="#374151",
            tags=(f"machine:{machine.id}",),
        )
        self._register_item(machine.id, rect)
        hall_label = self.canvas.create_text(
            x + 8,
            y + 10,
            text=f"hala nr {machine.hall}",
            anchor="w",
            fill=FG_MUTED,
            font=("Segoe UI", 9),
            tags=(f"machine:{machine.id}",),
        )
        self._register_item(machine.id, hall_label)
        name_label = self.canvas.create_text(
            x + 8,
            y + height / 2,
            text=machine.name,
            anchor="w",
            fill=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            tags=(f"machine:{machine.id}",),
        )
        self._register_item(machine.id, name_label)
        self._draw_status_dot(machine, x, y, width, height)
        if STATUS_STYLE[machine.status]["overlay"]:
            self._draw_awaria_overlay(machine, x, y, width, height)

        tag = f"machine:{machine.id}"
        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda event, mid=machine.id: self._on_enter(mid, event),
        )
        self.canvas.tag_bind(
            tag,
            "<Leave>",
            lambda event, mid=machine.id: self._on_leave(mid, event),
        )
        self.canvas.tag_bind(
            tag,
            "<Motion>",
            lambda event, mid=machine.id: self._on_motion(mid, event),
        )
        self.canvas.tag_bind(
            tag,
            "<ButtonPress-1>",
            lambda event, mid=machine.id: self._on_drag_start(event, mid),
        )
        self.canvas.tag_bind(
            tag,
            "<B1-Motion>",
            lambda event, mid=machine.id: self._on_drag_move(event, mid),
        )
        self.canvas.tag_bind(
            tag,
            "<ButtonRelease-1>",
            lambda event, mid=machine.id: self._on_release(event, mid),
        )

        print(
            f"[WM-DBG][HALA] Rysuję maszynę id={machine.id} "
            f"status={machine.status}"
        )

    def _draw_status_dot(
        self, machine: Machine, x: int, y: int, width: int, height: int
    ) -> None:
        color = STATUS_STYLE[machine.status]["color"]
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
        self._dot_items[machine.id] = dot
        self._register_item(machine.id, dot)
        print(
            f"[WM-DBG][HALA] Kropka statusu {machine.status} "
            f"dla {machine.id}"
        )

    def _draw_awaria_overlay(
        self, machine: Machine, x: int, y: int, width: int, height: int
    ) -> None:
        overlay = self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill="#7F1D1D",
            stipple="gray25",
            outline="",
            tags=(f"machine:{machine.id}",),
        )
        self._register_item(machine.id, overlay)
        overlay_text = self.canvas.create_text(
            x + width / 2,
            y + height / 2,
            text="NIE UŻYWAĆ",
            fill="#FFE4E6",
            font=("Segoe UI", 11, "bold"),
            tags=(f"machine:{machine.id}",),
        )
        self._register_item(machine.id, overlay_text)
        print(f"[WM-DBG][HALA] Overlay awaria dla {machine.id}")

    # blinking -------------------------------------------------------
    def _start_blink(self) -> None:
        if self._blink_job:
            try:
                self.root.after_cancel(self._blink_job)
            except Exception:
                pass
        self._blink_job = self.root.after(BLINK_MS, self._tick_blink)

    def _tick_blink(self) -> None:
        self._blink_state = not self._blink_state
        for machine_id, item in list(self._dot_items.items()):
            machine = self._by_id(machine_id)
            if machine and STATUS_STYLE.get(machine.status, {}).get("blink"):
                state = "hidden" if not self._blink_state else "normal"
                try:
                    self.canvas.itemconfigure(item, state=state)
                except Exception:
                    pass
        self._start_blink()

    # hover ----------------------------------------------------------
    def _on_enter(self, machine_id: str, event: tk.Event) -> None:
        self._hover_id = machine_id
        lines = self._tooltip_lines(machine_id)
        self._tooltip.show_after(
            TOOLTIP_DELAY_MS,
            event.x_root + TOOLTIP_OFFSET,
            event.y_root + TOOLTIP_OFFSET,
            lines,
        )
        print(f"[WM-DBG][HALA] Tooltip enter {machine_id}")

    def _on_motion(self, machine_id: str, event: tk.Event) -> None:
        if self._hover_id == machine_id:
            self._tooltip.move(
                event.x_root + TOOLTIP_OFFSET,
                event.y_root + TOOLTIP_OFFSET,
            )

    def _on_leave(self, machine_id: str, _event: tk.Event) -> None:
        if self._hover_id == machine_id:
            self._hover_id = None
        self._tooltip.cancel()
        self._tooltip.close()
        print(f"[WM-DBG][HALA] Tooltip leave {machine_id}")

    def _tooltip_lines(self, machine_id: str) -> List[str]:
        machine = self._by_id(machine_id)
        if not machine:
            return ["Maszyna nieznana"]

        status_cfg = STATUS_STYLE.get(
            machine.status,
            STATUS_STYLE[DEFAULT_STATUS],
        )
        type_label = machine.type or "brak typu"
        lines = [
            f"{machine.name} ({type_label})",
            f"ID: {machine.id} • Hala: {machine.hall}",
            f"Status: {status_cfg['label']}",
        ]

        duration_source = machine.awaria_start or machine.status_changed_at
        if duration_source:
            lines.append(f"Od zmiany: {_fmt_duration(duration_source)}")

        if machine.status == "awaria":
            lines.append("NIE UŻYWAĆ")
            if machine.awaria_comment:
                lines.append(f"Powód: {machine.awaria_comment}")
        elif machine.status == "modyfikacja":
            uwaga = machine.uwaga_text
            if uwaga:
                lines.append(f"Do zrobienia: {uwaga}")
        else:
            if machine.last_awaria_end:
                lines.append(
                    f"Sprawna od: {_fmt_duration(machine.last_awaria_end)}"
                )

        if machine.description:
            lines.append(machine.description)

        return lines

    # click ----------------------------------------------------------
    def _on_release(self, event: tk.Event, machine_id: str) -> None:
        self._on_drag_end(event, machine_id)
        self._on_click(machine_id)

    def _on_click(self, machine_id: str) -> None:
        self._set_selected(machine_id)
        if callable(self.on_select):
            try:
                self.on_select(machine_id)
            except Exception:
                pass
        if self.edit_mode:
            return
        print(f"[WM-DBG][HALA] Klik {machine_id}")
        self._open_details(machine_id)

    def _on_drag_start(self, event: tk.Event, machine_id: str) -> None:
        if not self.edit_mode:
            return
        self._drag_mid = machine_id
        self._drag_start = (event.x, event.y)

    def _on_drag_move(self, event: tk.Event, machine_id: str) -> None:
        if not self.edit_mode or self._drag_mid != machine_id:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        moved = False
        items = self._machine_items.get(machine_id)
        if items:
            for item in items:
                try:
                    self.canvas.move(item, dx, dy)
                    moved = True
                except Exception:
                    continue
        if not moved:
            try:
                self.canvas.move(f"machine:{machine_id}", dx, dy)
            except Exception:
                return
        self._drag_start = (event.x, event.y)
        if self._selected_mid == machine_id:
            self._redraw_selection()

    def _on_drag_end(self, event: tk.Event, machine_id: str) -> None:
        if not self.edit_mode or self._drag_mid != machine_id:
            return
        self._drag_mid = None
        bbox = self.canvas.bbox(f"machine:{machine_id}")
        if not bbox:
            return
        new_pos = {"x": int(bbox[0]), "y": int(bbox[1])}
        machine = self._by_id(machine_id)
        if machine:
            machine.raw.setdefault("pozycja", {})
            machine.raw["pozycja"]["x"] = new_pos["x"]
            machine.raw["pozycja"]["y"] = new_pos["y"]
        if callable(self.on_move):
            try:
                self.on_move(machine_id, new_pos)
            except Exception:
                pass
        if self._selected_mid == machine_id:
            self._redraw_selection()

    def _open_details(self, machine_id: str) -> None:
        machine = self._by_id(machine_id)
        if not machine:
            return

        if machine_id in self._details_windows:
            window = self._details_windows[machine_id]
            self._populate_details_form(machine_id, machine)
            try:
                window.deiconify()
                window.lift()
                window.focus_force()
            except Exception:
                pass
            print(f"[WM-DBG][HALA] Fokus okna opisu {machine_id}")
            return

        window = tk.Toplevel(self.root)
        window.title(f"Maszyna {machine.id} — opis")
        window.configure(bg=BG_DARK)
        try:
            window.wm_attributes("-topmost", True)
        except Exception:
            pass

        self._details_windows[machine_id] = window
        window.protocol(
            "WM_DELETE_WINDOW",
            lambda mid=machine_id: self._close_details(mid),
        )
        window.bind(
            "<Escape>",
            lambda _event, mid=machine_id: self._close_details(mid),
        )
        window.bind(
            "<Control-s>",
            lambda _event, mid=machine_id: self._save_details(mid),
        )

        wrapper = tk.Frame(window, bg=BG_DARK)
        wrapper.pack(fill="both", expand=True, padx=12, pady=12)

        header = tk.Frame(wrapper, bg=BG_DARK)
        header.pack(fill="x")
        header_label = tk.Label(
            header,
            text="",
            bg=BG_DARK,
            fg=FG_LIGHT,
            font=("Segoe UI", 12, "bold"),
        )
        header_label.pack(side="left")

        status_canvas = tk.Canvas(
            header,
            width=12,
            height=12,
            bg=BG_DARK,
            highlightthickness=0,
        )
        status_canvas.pack(side="left", padx=8, pady=2)

        main = tk.Frame(wrapper, bg=BG_DARK)
        main.pack(fill="x", pady=8)

        preview_frame = tk.Frame(
            main,
            bg=BG_DARK,
            highlightbackground="#333",
            highlightthickness=2,
        )
        preview_frame.pack(side="left", padx=(0, 12))
        preview_label = tk.Label(preview_frame, bg=BG_DARK, fg=FG_MUTED)
        preview_label.pack(padx=4, pady=4)

        info = tk.Frame(main, bg=BG_DARK)
        info.pack(side="left", fill="both", expand=True)

        info_label = tk.Label(
            info,
            text="",
            bg=BG_DARK,
            fg=FG_LIGHT,
            justify="left",
            anchor="w",
        )
        info_label.pack(fill="x")

        tk.Label(
            info,
            text="Edycja danych",
            bg=BG_DARK,
            fg=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(10, 4))

        form = tk.Frame(info, bg=BG_DARK)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=machine.name)
        tk.Label(form, text="Nazwa", bg=BG_DARK, fg=FG_LIGHT).grid(
            row=0, column=0, sticky="w"
        )
        name_entry = ttk.Entry(form, textvariable=name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))

        tk.Label(form, text="Opis", bg=BG_DARK, fg=FG_LIGHT).grid(
            row=1, column=0, sticky="nw"
        )
        opis_widget = tk.Text(
            form,
            height=4,
            bg=BG_DARK,
            fg=FG_LIGHT,
            insertbackground=FG_LIGHT,
            wrap="word",
        )
        opis_widget.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))

        hall_var = tk.StringVar(value=str(machine.hall))
        tk.Label(form, text="Hala", bg=BG_DARK, fg=FG_LIGHT).grid(
            row=2, column=0, sticky="w"
        )
        hall_entry = ttk.Entry(form, textvariable=hall_var, width=8)
        hall_entry.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 4))

        status_var = tk.StringVar(value=machine.status)
        tk.Label(form, text="Status", bg=BG_DARK, fg=FG_LIGHT).grid(
            row=3, column=0, sticky="w"
        )
        status_combo = ttk.Combobox(
            form,
            textvariable=status_var,
            values=tuple(STATUS_STYLE.keys()),
            state="readonly",
        )
        status_combo.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(0, 4))

        mini_var = tk.StringVar(value=machine.preview_url or "")
        tk.Label(form, text="Miniatura", bg=BG_DARK, fg=FG_LIGHT).grid(
            row=4, column=0, sticky="w"
        )
        mini_entry = ttk.Entry(form, textvariable=mini_var)
        mini_entry.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))

        status_msg = tk.StringVar(value="")
        tk.Label(
            info,
            textvariable=status_msg,
            bg=BG_DARK,
            fg=FG_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

        footer = tk.Frame(wrapper, bg=BG_DARK)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(
            footer,
            text="Zapisz",
            command=lambda mid=machine_id: self._save_details(mid),
        ).pack(side="right")
        ttk.Button(
            footer,
            text="Zamknij",
            command=lambda mid=machine_id: self._close_details(mid),
        ).pack(side="right", padx=(0, 8))

        self._details_forms[machine_id] = {
            "name": name_var,
            "hall": hall_var,
            "status": status_var,
            "status_combo": status_combo,
            "mini": mini_var,
            "opis": opis_widget,
            "status_msg": status_msg,
            "preview_label": preview_label,
            "preview_frame": preview_frame,
            "header_label": header_label,
            "status_dot": status_canvas,
            "info_label": info_label,
        }

        self._populate_details_form(machine_id, machine)
        name_entry.focus_set()

        print(f"[WM-DBG][HALA] Okno opisu {machine_id} gotowe")

    def _close_details(self, machine_id: str) -> None:
        window = self._details_windows.pop(machine_id, None)
        self._details_forms.pop(machine_id, None)
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    def _populate_details_form(self, machine_id: str, machine: Machine) -> None:
        form = self._details_forms.get(machine_id)
        if not form:
            return

        form["name"].set(machine.name)
        form["hall"].set(str(machine.hall))

        status_value = machine.status
        status_values = list(STATUS_STYLE.keys())
        if status_value not in STATUS_STYLE:
            status_values.append(status_value)
        status_combo = form.get("status_combo")
        if status_combo:
            status_combo.configure(values=tuple(status_values))
            status_combo.set(status_value)
        form["status"].set(status_value)

        preview_value = machine.preview_url or ""
        form["mini"].set(preview_value)

        opis_widget: tk.Text = form["opis"]
        opis_widget.delete("1.0", "end")
        if machine.description:
            opis_widget.insert("1.0", machine.description)

        form["status_msg"].set("")

        header_label: tk.Label = form["header_label"]
        header_label.configure(text=f"{machine.name}  ({machine.id})")

        status_cfg = STATUS_STYLE.get(status_value, STATUS_STYLE[DEFAULT_STATUS])
        color = status_cfg["color"]
        status_dot: tk.Canvas = form["status_dot"]
        status_dot.delete("all")
        status_dot.create_oval(2, 2, 10, 10, fill=color, outline="")

        preview_frame = form.get("preview_frame")
        if isinstance(preview_frame, tk.Frame):
            preview_frame.configure(highlightbackground=color)

        preview_label: tk.Label = form["preview_label"]
        image = self._get_preview(machine)
        if image:
            preview_label.configure(image=image, text="")
            preview_label.image = image
        else:
            preview_label.configure(image="", text="Brak miniatury", fg=FG_MUTED)
            preview_label.image = None

        info_lines = [
            f"Typ: {machine.type or 'brak'}",
            f"Hala: {machine.hall}",
            f"Status: {status_cfg['label']}",
        ]
        duration_source = machine.awaria_start or machine.status_changed_at
        if duration_source:
            duration = _fmt_duration(duration_source)
            if duration:
                info_lines.append(f"Od zmiany: {duration}")
        if machine.status == "awaria":
            info_lines.append("NIE UŻYWAĆ")
            if machine.awaria_comment:
                info_lines.append(f"Powód awarii: {machine.awaria_comment}")
        elif machine.status == "modyfikacja":
            uwaga = machine.uwaga_text
            if uwaga:
                info_lines.append(f"Do zrobienia: {uwaga}")
        if machine.last_awaria_end:
            duration = _fmt_duration(machine.last_awaria_end)
            if duration:
                info_lines.append(f"Sprawna od: {duration}")

        info_label: tk.Label = form["info_label"]
        info_label.configure(text="\n".join(info_lines))

    def _save_details(self, machine_id: str) -> None:
        machine = self._by_id(machine_id)
        form = self._details_forms.get(machine_id)
        if not machine or not form:
            return

        name = form["name"].get().strip()
        opis_widget: tk.Text = form["opis"]
        description = opis_widget.get("1.0", "end-1c").strip()
        hall_text = form["hall"].get().strip()
        status_value = form["status"].get().strip().lower()
        mini_value = form["mini"].get().strip()

        if not status_value:
            status_value = DEFAULT_STATUS
        if status_value not in STATUS_STYLE:
            messagebox.showerror(
                "Maszyny",
                "Nieznany status maszyny. Dostępne: "
                + ", ".join(STATUS_STYLE.keys()),
            )
            return

        try:
            hall_value = int(hall_text or machine.hall)
        except ValueError:
            messagebox.showerror(
                "Maszyny", "Numer hali musi być liczbą całkowitą."
            )
            return

        updates = {
            "nazwa": name,
            "opis": description,
            "hala": hall_value,
            "status": status_value,
            "miniatura": mini_value,
        }

        try:
            changed = apply_machine_updates(machine.raw, updates)
        except ValueError as exc:
            messagebox.showerror("Maszyny", str(exc))
            return

        if not changed:
            form["status_msg"].set("Brak zmian.")
            return

        self._preview_cache.pop(machine.id, None)
        form["status_msg"].set("Zapisano zmiany.")
        self._notify_machine_update(machine_id, machine.raw)
        self.draw_all()
        self._populate_details_form(machine_id, machine)

    def _notify_machine_update(self, machine_id: str, row: dict) -> None:
        if callable(self.on_update):
            try:
                self.on_update(machine_id, row)
            except Exception:
                pass

    # previews -------------------------------------------------------
    def _get_preview(self, machine: Machine, max_width: int = 256):
        if not PIL_OK:
            print("[ERROR][HALA] Pillow niedostępny – miniatury wyłączone")
            return None

        if machine.id in self._preview_cache:
            return self._preview_cache[machine.id]

        image = None
        source = (machine.preview_url or "").strip() if machine.preview_url else ""
        if source:
            try:
                if _is_url(source) and _url:
                    with _url.urlopen(source, timeout=1) as response:
                        data = response.read()
                    image = Image.open(io.BytesIO(data)).convert("RGB")
                    print(f"[WM-DBG][HALA] Miniatura z URL: {source}")
                else:
                    local_path = self._resolve_local_path(source)
                    if local_path:
                        image = Image.open(local_path).convert("RGB")
                        print(f"[WM-DBG][HALA] Miniatura FILE: {local_path}")
            except Exception as exc:
                print(
                    f"[ERROR][HALA] Miniatura błąd ({exc}) — placeholder"
                )

        if image is None:
            placeholder = self._resolve_local_path(PLACEHOLDER_PATH) or PLACEHOLDER_PATH
            try:
                image = Image.open(placeholder).convert("RGB")
            except Exception as exc:
                print(
                    f"[ERROR][HALA] Brak placeholdera ({placeholder}): {exc}"
                )
                return None

        width, height = image.size
        if width > max_width:
            image = image.resize(
                (max_width, int(height * max_width / width)),
                Image.LANCZOS,
            )

        tk_image = ImageTk.PhotoImage(image)
        self._preview_cache[machine.id] = tk_image
        return tk_image

    # utils ----------------------------------------------------------
    def _by_id(self, machine_id: str) -> Optional[Machine]:
        for machine in self.machines:
            if machine.id == machine_id:
                return machine
        return None

    def _set_selected(self, machine_id: Optional[str]) -> None:
        if machine_id is None:
            self._clear_selection()
            return
        if self._selected_mid != machine_id:
            self._selected_mid = machine_id
        self._redraw_selection()

    def _clear_selection(self) -> None:
        self._selected_mid = None
        if self._selection_item is not None:
            try:
                self.canvas.delete(self._selection_item)
            except Exception:
                pass
        self._selection_item = None

    def _redraw_selection(self) -> None:
        if self._selection_item is not None:
            try:
                self.canvas.delete(self._selection_item)
            except Exception:
                pass
            self._selection_item = None

        if not self._selected_mid:
            return

        bbox = self.canvas.bbox(f"machine:{self._selected_mid}")
        if not bbox:
            self._clear_selection()
            return

        x1, y1, x2, y2 = bbox
        padding = 4
        try:
            self._selection_item = self.canvas.create_rectangle(
                x1 - padding,
                y1 - padding,
                x2 + padding,
                y2 + padding,
                outline="#38BDF8",
                width=2,
                dash=(4, 2),
                fill="",
                state="disabled",
                tags=("machine-highlight", f"machine-highlight:{self._selected_mid}"),
            )
            self.canvas.tag_raise(self._selection_item)
        except Exception:
            self._selection_item = None

    def _resolve_local_path(self, path: str) -> Optional[str]:
        if not path:
            return None

        path = os.path.expanduser(path)
        if os.path.isabs(path) and os.path.exists(path):
            return path

        candidates = []
        norm = os.path.normpath(path)
        candidates.append(os.path.join(os.getcwd(), norm))

        module_dir = os.path.dirname(__file__)
        candidates.append(os.path.join(module_dir, norm))
        candidates.append(os.path.normpath(os.path.join(module_dir, "..", norm)))

        seen = set()
        for candidate in candidates:
            candidate = os.path.abspath(candidate)
            if candidate in seen:
                continue
            seen.add(candidate)
            if os.path.exists(candidate):
                return candidate
        return None


def draw_background(
    canvas: tk.Canvas,
    path: str,
    width: int,
    height: int,
) -> None:
    """Rysuj tło z pliku ``path`` lub szachownicę gdy plik nie istnieje."""

    try:
        image = tk.PhotoImage(file=path)
        canvas.image = image  # type: ignore[attr-defined]
        canvas.create_image(
            0,
            0,
            image=image,
            anchor="nw",
            tags=("background",),
        )
    except Exception:
        _log(f"[HALA][WARN] Brak pliku tła {path}")
        size = 20
        for y_pos in range(0, height, size):
            for x_pos in range(0, width, size):
                even = (x_pos // size + y_pos // size) % 2 == 0
                fill = "#cccccc" if even else "#eeeeee"
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
    "Machine",
    "draw_background",
    "draw_grid",
    "draw_walls",
    "draw_machine",
    "draw_status_overlay",
]
