# version: 1.0
"""Warstwowe rozszerzenie działającego modułu Maszyny o pomieszczenia hali.

Nie zastępuje logiki Maszyn. Instaluje podklasę istniejącego renderera oraz
adapter lokalizacji, więc statusy, serwis, formularze i dotychczasowy zapis
pozostają w module bazowym.
"""
from __future__ import annotations

from copy import deepcopy
import logging
import math
import weakref
from typing import Any, MutableMapping, Optional

from .rooms import (
    Room,
    load_rooms,
    location_values,
    next_room_id,
    normalize_room_name,
    room_at_point,
    room_by_id,
    save_rooms,
    sync_location_fields,
    sync_record_from_point,
    validate_room,
)

log = logging.getLogger(__name__)


def _machine_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or "").strip()


def _hall_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("nr_hali") or row.get("hala") or "1").strip() or "1"


def _location_signature(row: MutableMapping[str, Any]) -> tuple[object, object, object]:
    return (
        row.get("lokalizacja"),
        row.get("lokalizacja_id"),
        row.get("placement_status"),
    )


class _TtkProxy:
    """Deleguj ttk, a pole Lokalizacja w formularzu Maszyn zrób listą."""

    def __init__(self, real_ttk, values_provider):
        self._real = real_ttk
        self._values_provider = values_provider
        self._entry_counts: "weakref.WeakKeyDictionary[object, int]" = (
            weakref.WeakKeyDictionary()
        )

    def __getattr__(self, name: str):
        return getattr(self._real, name)

    def _is_machine_edit_form(self, master) -> bool:
        if master is None:
            return False
        try:
            top = master.winfo_toplevel()
            return str(top.title() or "") == "Edycja maszyny" and master.master is top
        except Exception:
            return False

    def Entry(self, master=None, *args, **kwargs):  # noqa: N802 - zgodność z ttk
        if self._is_machine_edit_form(master):
            count = int(self._entry_counts.get(master, 0)) + 1
            self._entry_counts[master] = count
            # row_entry: ID, Nazwa, Typ, Lokalizacja, x, y
            if count == 4:
                combo_kwargs = dict(kwargs)
                combo_kwargs.setdefault("state", "normal")
                combo_kwargs["values"] = tuple(self._values_provider())
                return self._real.Combobox(master, *args, **combo_kwargs)
        return self._real.Entry(master, *args, **kwargs)


def _make_renderer(base_cls, legacy_module):
    tk = legacy_module.tk
    ttk = legacy_module.ttk
    messagebox = legacy_module.messagebox
    simpledialog = legacy_module.simpledialog
    Image = legacy_module.Image
    ImageTk = legacy_module.ImageTk

    class RoomAwareMachineHallRenderer(base_cls):
        """Dotychczasowy renderer maszyn z dodatkową warstwą pomieszczeń."""

        ROOM_FILL = "#17324d"
        ROOM_OUTLINE = "#4b9bd3"
        ROOM_SELECTED = "#22d3ee"
        ROOM_TARGET = "#f59e0b"
        ROOM_DRAFT = "#a78bfa"
        WALL_WIDTH = 3
        SNAP_SCREEN_PX = 10
        RESIZE_DEBOUNCE_MS = 120

        def __init__(self, parent, rows, cfg=None, on_drag_commit=None, bg_path=None):
            super().__init__(
                parent,
                rows,
                cfg=cfg,
                on_drag_commit=on_drag_commit,
                bg_path=bg_path,
            )
            self._rooms: list[Room] = load_rooms()
            self._rooms_snapshot: list[Room] = deepcopy(self._rooms)
            self._layout_dirty = False
            self._layout_edit = False
            self._draft_points: list[tuple[int, int]] = []
            self._selected_room_id: Optional[str] = None
            self._vertex_drag: Optional[tuple[str, int]] = None
            self._vertex_drag_before: Optional[list[Room]] = None
            self._undo_stack: list[list[Room]] = []
            self._placement_machine_id: Optional[str] = None

            self._manual_scale: Optional[float] = None
            self._pan_x = 0
            self._pan_y = 0
            self._pan_start: Optional[tuple[int, int, int, int]] = None
            self._resize_job = None
            self._scaled_bg_size: Optional[tuple[int, int]] = None
            self._view_ready = False

            self._toolbar = ttk.Frame(parent)
            self._edit_var = tk.BooleanVar(master=parent, value=False)
            self._status_var = tk.StringVar(master=parent, value="Plan hali: tryb podglądu")
            self._unplaced_button = None
            self._build_room_toolbar()
            self._sync_rows_in_memory()

        # ---------- uruchomienie i odświeżanie ----------
        def render(self) -> None:
            self._toolbar.pack(fill="x", padx=8, pady=(6, 0))
            self._status_label.pack(fill="x", padx=10, pady=(2, 0))
            self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
            self._load_background()
            self._recompute_view()
            self._draw_all()
            self._bind_drag()
            self.canvas.bind("<Motion>", self._on_canvas_motion, add="+")
            self.canvas.bind("<Leave>", lambda _e: self.tip.hide(), add="+")
            self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
            self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
            self.canvas.bind("<ButtonPress-2>", self._on_pan_press, add="+")
            self.canvas.bind("<B2-Motion>", self._on_pan_motion, add="+")
            self.canvas.bind("<ButtonRelease-2>", self._on_pan_release, add="+")
            self._view_ready = True
            self._refresh_unplaced_button()

        def update_rows(self, rows):
            self.rows = rows or []
            self._sync_rows_in_memory()
            self._draw_all()
            self._refresh_unplaced_button()

        # ---------- pasek hali ----------
        def _build_room_toolbar(self) -> None:
            ttk.Button(self._toolbar, text="Dopasuj", command=self._fit_view).pack(
                side="left", padx=(0, 4)
            )
            ttk.Button(
                self._toolbar, text="−", width=3, command=lambda: self._zoom_by(1 / 1.15)
            ).pack(side="left", padx=2)
            ttk.Button(
                self._toolbar, text="+", width=3, command=lambda: self._zoom_by(1.15)
            ).pack(side="left", padx=2)
            ttk.Checkbutton(
                self._toolbar,
                text="Edytuj układ hali",
                variable=self._edit_var,
                command=self._toggle_layout_edit,
            ).pack(side="left", padx=(8, 6))

            self._btn_new_room = ttk.Button(
                self._toolbar, text="Nowe pomieszczenie", command=self._start_room
            )
            self._btn_rename_room = ttk.Button(
                self._toolbar, text="Zmień nazwę", command=self._rename_selected_room
            )
            self._btn_delete_room = ttk.Button(
                self._toolbar, text="Usuń pom.", command=self._delete_selected_room
            )
            self._btn_undo = ttk.Button(
                self._toolbar, text="Cofnij", command=self._undo_layout
            )
            self._btn_save_layout = ttk.Button(
                self._toolbar, text="Zapisz układ", command=self._save_layout
            )
            self._btn_cancel_layout = ttk.Button(
                self._toolbar, text="Anuluj", command=self._cancel_layout
            )
            for button in (
                self._btn_new_room,
                self._btn_rename_room,
                self._btn_delete_room,
                self._btn_undo,
                self._btn_save_layout,
                self._btn_cancel_layout,
            ):
                button.pack(side="left", padx=2)

            self._unplaced_button = ttk.Button(
                self._toolbar,
                text="Nieumieszczone (0)",
                command=self._choose_unplaced_machine,
            )
            self._unplaced_button.pack(side="right", padx=(6, 0))
            self._status_label = ttk.Label(
                self.parent, textvariable=self._status_var, anchor="w"
            )
            self._set_edit_buttons_state(False)

        def _set_edit_buttons_state(self, enabled: bool) -> None:
            state = ["!disabled"] if enabled else ["disabled"]
            for button in (
                self._btn_new_room,
                self._btn_rename_room,
                self._btn_delete_room,
                self._btn_undo,
                self._btn_save_layout,
                self._btn_cancel_layout,
            ):
                try:
                    button.state(state)
                except Exception:
                    pass

        def _toggle_layout_edit(self) -> None:
            self._layout_edit = bool(self._edit_var.get())
            self._placement_machine_id = None
            self._drag_active = False
            self._drag_id = None
            self._draft_points = []
            self._vertex_drag = None
            self._set_edit_buttons_state(self._layout_edit)
            self._status_var.set(
                "Układ hali: Nowe pomieszczenie → klikaj narożniki → kliknij pierwszy punkt."
                if self._layout_edit
                else "Plan hali: tryb podglądu"
            )
            self._draw_all()

        # ---------- skalowanie i transformacja ----------
        def _canvas_size(self) -> tuple[int, int]:
            try:
                width = max(1, int(self.canvas.winfo_width()))
                height = max(1, int(self.canvas.winfo_height()))
            except Exception:
                width, height = 1000, 1000
            if width <= 2:
                width = max(1, int(getattr(legacy_module, "CANVAS_W", 1000)))
            if height <= 2:
                height = max(1, int(getattr(legacy_module, "CANVAS_H", 1000)))
            return width, height

        def _set_bg_geometry(self, width: int, height: int) -> None:
            self._bg_w = max(0, int(width))
            self._bg_h = max(0, int(height))
            self._recompute_view()

        def _recompute_view(self) -> None:
            width, height = self._canvas_size()
            if self._bg_w <= 0 or self._bg_h <= 0:
                self._scale_x = self._scale_y = 1.0
                self._bg_anchor_xy = (0, 0)
                return
            fit = min(
                max(1, width - 16) / self._bg_w,
                max(1, height - 16) / self._bg_h,
            )
            scale = self._manual_scale if self._manual_scale is not None else fit
            scale = max(0.05, min(8.0, float(scale)))
            self._scale_x = self._scale_y = scale
            display_w = int(round(self._bg_w * scale))
            display_h = int(round(self._bg_h * scale))
            self._bg_anchor_xy = (
                (width - display_w) // 2 + int(self._pan_x),
                (height - display_h) // 2 + int(self._pan_y),
            )
            self._refresh_scaled_background()

        def _refresh_scaled_background(self) -> None:
            if self._bg_img_pil is None or ImageTk is None:
                return
            width = max(1, int(round(self._bg_w * self._scale_x)))
            height = max(1, int(round(self._bg_h * self._scale_y)))
            size = (width, height)
            if self._scaled_bg_size == size and self._bg_img_tk is not None:
                return
            try:
                source = self._bg_img_pil
                if source.size != size:
                    try:
                        resampling = Image.Resampling.LANCZOS
                    except Exception:
                        resampling = getattr(Image, "LANCZOS", 1)
                    source = source.resize(size, resampling)
                self._bg_img_tk = ImageTk.PhotoImage(source)
                self._scaled_bg_size = size
            except Exception:
                log.exception("[Maszyny][HALL][ROOMS] Błąd skalowania tła")

        def _load_bg_image_assets(self, path: str) -> None:
            self._scaled_bg_size = None
            if Image is not None and ImageTk is not None:
                try:
                    img = Image.open(path).convert("RGBA")
                except Exception:
                    img = None
                if img is not None:
                    self._bg_img_pil = img
                    self._bg_fallback = None
                    self._bg_w, self._bg_h = img.width, img.height
                    self._recompute_view()
                    return
            try:
                tk_img = tk.PhotoImage(file=path)
            except Exception:
                self._bg_fallback = None
                self._bg_w = self._bg_h = 0
                return
            self._bg_fallback = tk_img
            self._bg_img_pil = None
            self._bg_img_tk = None
            self._bg_w = int(tk_img.width())
            self._bg_h = int(tk_img.height())
            self._manual_scale = 1.0
            self._recompute_view()

        def _fit_view(self) -> None:
            self._manual_scale = None
            self._pan_x = self._pan_y = 0
            self._recompute_view()
            self._draw_all()

        def _zoom_by(self, factor: float) -> None:
            if self._bg_w <= 0 or self._bg_h <= 0:
                return
            self._manual_scale = max(
                0.05, min(8.0, float(self._scale_x or 1.0) * factor)
            )
            self._recompute_view()
            self._draw_all()

        def _on_mousewheel(self, event) -> None:
            delta = getattr(event, "delta", 0)
            if delta:
                self._zoom_by(1.15 if delta > 0 else 1 / 1.15)

        def _on_pan_press(self, event) -> None:
            if not self._layout_edit:
                self._pan_start = (event.x, event.y, self._pan_x, self._pan_y)

        def _on_pan_motion(self, event) -> None:
            if self._pan_start is None:
                return
            x0, y0, pan_x0, pan_y0 = self._pan_start
            self._pan_x = pan_x0 + event.x - x0
            self._pan_y = pan_y0 + event.y - y0
            if self._manual_scale is None:
                self._manual_scale = float(self._scale_x or 1.0)
            self._recompute_view()
            self._draw_all()

        def _on_pan_release(self, _event) -> None:
            self._pan_start = None

        def _on_canvas_configure(self, _event) -> None:
            if not self._view_ready:
                return
            if self._resize_job is not None:
                try:
                    self.canvas.after_cancel(self._resize_job)
                except Exception:
                    pass
            self._resize_job = self.canvas.after(
                self.RESIZE_DEBOUNCE_MS, self._apply_resize
            )

        def _apply_resize(self) -> None:
            self._resize_job = None
            self._recompute_view()
            self._draw_all()

        def _clamp_to_canvas(self, x: int, y: int) -> tuple[int, int]:
            width, height = self._canvas_size()
            return max(0, min(width - 1, int(x))), max(0, min(height - 1, int(y)))

        def _display_bounds(self, margin: int = 0) -> tuple[int, int, int, int]:
            ax, ay = self._bg_anchor_xy
            display_w = int(round(self._bg_w * self._scale_x))
            display_h = int(round(self._bg_h * self._scale_y))
            return (
                ax + margin,
                ay + margin,
                ax + display_w - margin,
                ay + display_h - margin,
            )

        def _node_center(self, row, idx: int, radius: int):
            x, y = row.get("x"), row.get("y")
            if isinstance(x, int) and isinstance(y, int) and self._bg_w > 0 and self._bg_h > 0:
                cx, cy = self._map_bg_to_canvas(x, y)
                min_x, min_y, max_x, max_y = self._display_bounds(max(radius, 4))
                if max_x >= min_x and max_y >= min_y:
                    return max(min_x, min(max_x, cx)), max(min_y, min(max_y, cy))
            return super()._node_center(row, idx, radius)

        def _move_group(self, mid: str, cx: int, cy: int):
            if self._bg_w <= 0 or self._bg_h <= 0:
                return super()._move_group(mid, cx, cy)
            radius = self._current_radius or self.RADIUS
            min_x, min_y, max_x, max_y = self._display_bounds(max(radius, 4))
            cx = max(min_x, min(max_x, int(cx)))
            cy = max(min_y, min(max_y, int(cy)))
            node = self.nodes_by_id.get(mid)
            if node:
                self.canvas.coords(node, cx - radius, cy - radius, cx + radius, cy + radius)
            text_id = self.text_by_id.get(mid)
            if text_id:
                self.canvas.coords(text_id, cx, cy)
            label_id = self.labels_by_id.get(mid)
            if label_id:
                self.canvas.coords(label_id, cx, cy + radius + 14)

        # ---------- tło, pomieszczenia, ściany, siatka ----------
        def _draw_background_and_grid(self) -> None:
            width, height = self._canvas_size()
            self.canvas.create_rectangle(
                0,
                0,
                width,
                height,
                fill=getattr(legacy_module, "DEFAULT_BG_COLOR", "#1e1e1e"),
                outline="",
                tags=("hall-background",),
            )
            ax, ay = self._bg_anchor_xy
            if self._bg_img_tk is not None:
                self.canvas.create_image(
                    ax, ay, image=self._bg_img_tk, anchor="nw", tags=("hall-background",)
                )
            elif self._bg_fallback is not None:
                self.canvas.create_image(
                    ax, ay, image=self._bg_fallback, anchor="nw", tags=("hall-background",)
                )

            self._draw_rooms()

            if self._bg_w > 0 and self._bg_h > 0:
                display_w = int(round(self._bg_w * self._scale_x))
                display_h = int(round(self._bg_h * self._scale_y))
                step_x = max(
                    4,
                    int(round(getattr(legacy_module, "GRID_BASE_BG_PX_X", 25) * self._scale_x)),
                )
                step_y = max(
                    4,
                    int(round(getattr(legacy_module, "GRID_BASE_BG_PX_Y", 25) * self._scale_y)),
                )
                x = ax
                while x <= ax + display_w:
                    self.canvas.create_line(
                        x, ay, x, ay + display_h, fill="#2a2a2a", tags=("hall-grid",)
                    )
                    x += step_x
                y = ay
                while y <= ay + display_h:
                    self.canvas.create_line(
                        ax, y, ax + display_w, y, fill="#2a2a2a", tags=("hall-grid",)
                    )
                    y += step_y
                self.canvas.create_rectangle(
                    ax,
                    ay,
                    ax + display_w,
                    ay + display_h,
                    outline="#3a3a3a",
                    tags=("hall-border",),
                )

        def _room_canvas_points(self, room: Room) -> list[int]:
            coords: list[int] = []
            for x, y in room.polygon:
                cx, cy = self._map_bg_to_canvas(x, y)
                coords.extend((cx, cy))
            return coords

        def _draw_rooms(self) -> None:
            for room in self._rooms:
                if not room.active or len(room.polygon) < 3:
                    continue
                coords = self._room_canvas_points(room)
                selected = room.id == self._selected_room_id
                target = False
                if self._placement_machine_id:
                    row = next(
                        (
                            candidate
                            for candidate in self.rows
                            if isinstance(candidate, dict)
                            and _machine_id(candidate) == self._placement_machine_id
                        ),
                        None,
                    )
                    target = bool(row and row.get("lokalizacja_id") == room.id)
                outline = (
                    self.ROOM_TARGET
                    if target
                    else self.ROOM_SELECTED if selected else self.ROOM_OUTLINE
                )
                self.canvas.create_polygon(
                    *coords,
                    fill=self.ROOM_FILL,
                    outline=outline,
                    width=4 if selected or target else self.WALL_WIDTH,
                    stipple="gray25",
                    tags=("hall-room", f"room-{room.id}"),
                )
                center_x = sum(x for x, _ in room.polygon) / len(room.polygon)
                center_y = sum(y for _, y in room.polygon) / len(room.polygon)
                cx, cy = self._map_bg_to_canvas(int(center_x), int(center_y))
                self.canvas.create_text(
                    cx,
                    cy,
                    text=room.name,
                    fill="#e5e7eb",
                    font=("TkDefaultFont", 10, "bold"),
                    tags=("hall-room-label", f"room-{room.id}"),
                )
                if self._layout_edit and selected:
                    for index, (x, y) in enumerate(room.polygon):
                        vx, vy = self._map_bg_to_canvas(x, y)
                        self.canvas.create_rectangle(
                            vx - 5,
                            vy - 5,
                            vx + 5,
                            vy + 5,
                            fill=self.ROOM_SELECTED,
                            outline="#071018",
                            tags=(
                                "hall-room-handle",
                                f"room-{room.id}",
                                f"vertex-{index}",
                            ),
                        )

            if self._draft_points:
                coords: list[int] = []
                for x, y in self._draft_points:
                    cx, cy = self._map_bg_to_canvas(x, y)
                    coords.extend((cx, cy))
                if len(coords) >= 4:
                    self.canvas.create_line(
                        *coords,
                        fill=self.ROOM_DRAFT,
                        width=3,
                        tags=("hall-room-draft",),
                    )
                for index in range(0, len(coords), 2):
                    cx, cy = coords[index], coords[index + 1]
                    self.canvas.create_oval(
                        cx - 5,
                        cy - 5,
                        cx + 5,
                        cy + 5,
                        fill=self.ROOM_DRAFT,
                        outline="",
                        tags=("hall-room-draft",),
                    )

        # ---------- edycja pomieszczeń ----------
        def _push_undo(self) -> None:
            self._undo_stack.append(deepcopy(self._rooms))
            if len(self._undo_stack) > 30:
                del self._undo_stack[0]

        def _undo_layout(self) -> None:
            if not self._undo_stack:
                return
            self._rooms = self._undo_stack.pop()
            self._draft_points = []
            self._selected_room_id = None
            self._layout_dirty = True
            self._draw_all()

        def _selected_room(self) -> Optional[Room]:
            return room_by_id(self._rooms, self._selected_room_id)

        def _start_room(self) -> None:
            if not self._layout_edit:
                return
            self._draft_points = []
            self._selected_room_id = None
            self._status_var.set(
                "Nowe pomieszczenie: klikaj narożniki; kliknij pierwszy punkt, aby zamknąć."
            )
            self._draw_all()

        def _snap_world_point(
            self,
            bx: int,
            by: int,
            *,
            previous: Optional[tuple[int, int]] = None,
            orthogonal: bool = False,
        ) -> tuple[int, int]:
            x, y = int(bx), int(by)
            px, py = self._map_bg_to_canvas(x, y)
            nearest = None
            nearest_dist = float("inf")
            for room in self._rooms:
                for vx, vy in room.polygon:
                    cx, cy = self._map_bg_to_canvas(vx, vy)
                    dist = math.hypot(cx - px, cy - py)
                    if dist <= self.SNAP_SCREEN_PX and dist < nearest_dist:
                        nearest = (vx, vy)
                        nearest_dist = dist
            if nearest is not None:
                x, y = nearest
            if orthogonal and previous is not None:
                old_x, old_y = previous
                if abs(x - old_x) >= abs(y - old_y):
                    y = old_y
                else:
                    x = old_x
            x = int(round(x / 5.0) * 5)
            y = int(round(y / 5.0) * 5)
            if self._bg_w > 0:
                x = max(0, min(self._bg_w - 1, x))
            if self._bg_h > 0:
                y = max(0, min(self._bg_h - 1, y))
            return x, y

        def _near_first_draft_point(self, event) -> bool:
            if len(self._draft_points) < 3:
                return False
            fx, fy = self._map_bg_to_canvas(*self._draft_points[0])
            return math.hypot(event.x - fx, event.y - fy) <= self.SNAP_SCREEN_PX + 2

        def _finish_draft_room(self) -> None:
            if len(self._draft_points) < 3:
                return
            name = simpledialog.askstring(
                "Pomieszczenie",
                "Nazwa pomieszczenia:",
                parent=self.canvas.winfo_toplevel(),
            )
            if name is None:
                return
            name = normalize_room_name(name)
            if not name:
                messagebox.showwarning(
                    "Pomieszczenie",
                    "Podaj nazwę pomieszczenia.",
                    parent=self.canvas.winfo_toplevel(),
                )
                return
            room = Room(
                id=next_room_id(self._rooms),
                name=name,
                polygon=list(self._draft_points),
                hala="1",
            )
            try:
                validate_room(room, existing=self._rooms)
            except ValueError as exc:
                messagebox.showwarning(
                    "Pomieszczenie", str(exc), parent=self.canvas.winfo_toplevel()
                )
                return
            self._push_undo()
            self._rooms.append(room)
            self._selected_room_id = room.id
            self._draft_points = []
            self._layout_dirty = True
            self._status_var.set(f'Dodano "{room.name}". Zapisz układ, gdy skończysz.')
            self._draw_all()

        def _room_at_canvas(self, x: int, y: int) -> Optional[Room]:
            bx, by = self._map_canvas_to_bg(x, y)
            return room_at_point(self._rooms, bx, by)

        def _vertex_at_canvas(self, x: int, y: int) -> Optional[tuple[str, int]]:
            room = self._selected_room()
            if room is None:
                return None
            for index, (vx, vy) in enumerate(room.polygon):
                cx, cy = self._map_bg_to_canvas(vx, vy)
                if math.hypot(x - cx, y - cy) <= self.SNAP_SCREEN_PX:
                    return room.id, index
            return None

        def _rename_selected_room(self) -> None:
            room = self._selected_room()
            if room is None:
                messagebox.showinfo(
                    "Pomieszczenie",
                    "Najpierw kliknij pomieszczenie na planie.",
                    parent=self.canvas.winfo_toplevel(),
                )
                return
            name = simpledialog.askstring(
                "Pomieszczenie",
                "Nowa nazwa:",
                initialvalue=room.name,
                parent=self.canvas.winfo_toplevel(),
            )
            if name is None:
                return
            candidate = Room(
                id=room.id,
                name=normalize_room_name(name),
                polygon=list(room.polygon),
                hala=room.hala,
                active=room.active,
            )
            try:
                validate_room(candidate, existing=self._rooms)
            except ValueError as exc:
                messagebox.showwarning(
                    "Pomieszczenie", str(exc), parent=self.canvas.winfo_toplevel()
                )
                return
            self._push_undo()
            room.name = candidate.name
            self._layout_dirty = True
            self._draw_all()

        def _delete_selected_room(self) -> None:
            room = self._selected_room()
            if room is None:
                return
            affected = [
                row
                for row in self.rows
                if isinstance(row, dict) and row.get("lokalizacja_id") == room.id
            ]
            if affected:
                messagebox.showwarning(
                    "Usuń pomieszczenie",
                    (
                        f'Nie można usunąć "{room.name}", bo przypisano do niego '
                        f"{len(affected)} maszyn. Najpierw zmień ich lokalizację."
                    ),
                    parent=self.canvas.winfo_toplevel(),
                )
                return
            if not messagebox.askyesno(
                "Usuń pomieszczenie",
                f'Usunąć "{room.name}" z planu?',
                parent=self.canvas.winfo_toplevel(),
            ):
                return
            self._push_undo()
            self._rooms = [candidate for candidate in self._rooms if candidate.id != room.id]
            self._selected_room_id = None
            self._layout_dirty = True
            self._draw_all()

        def _save_layout(self) -> None:
            try:
                save_rooms(self._rooms)
            except Exception as exc:
                log.exception("[Maszyny][HALL][ROOMS] Błąd zapisu układu")
                messagebox.showerror(
                    "Układ hali",
                    f"Nie udało się zapisać układu:\n{exc}",
                    parent=self.canvas.winfo_toplevel(),
                )
                return
            self._rooms_snapshot = deepcopy(self._rooms)
            self._layout_dirty = False
            self._undo_stack.clear()
            self._sync_and_persist_machine_locations()
            self._status_var.set("Układ hali zapisany.")
            self._refresh_unplaced_button()
            self._draw_all()

        def _cancel_layout(self) -> None:
            if self._layout_dirty and not messagebox.askyesno(
                "Układ hali",
                "Odrzucić niezapisane zmiany układu?",
                parent=self.canvas.winfo_toplevel(),
            ):
                return
            self._rooms = deepcopy(self._rooms_snapshot)
            self._layout_dirty = False
            self._draft_points = []
            self._selected_room_id = None
            self._undo_stack.clear()
            self._draw_all()

        # ---------- lokalizacja maszyn ----------
        def _sync_rows_in_memory(self) -> None:
            for row in self.rows:
                if isinstance(row, dict):
                    sync_location_fields(row, self._rooms)

        def _sync_and_persist_machine_locations(self) -> None:
            changed: list[tuple[str, int, int]] = []
            for row in list(self.rows):
                if not isinstance(row, dict):
                    continue
                before = _location_signature(row)
                sync_location_fields(row, self._rooms)
                if before != _location_signature(row):
                    mid = _machine_id(row)
                    x, y = row.get("x"), row.get("y")
                    if mid and isinstance(x, int) and isinstance(y, int):
                        changed.append((mid, x, y))
            for mid, x, y in changed:
                try:
                    if callable(self.on_drag_commit):
                        self.on_drag_commit(mid, x, y)
                except Exception:
                    log.exception(
                        "[Maszyny][HALL][ROOMS] Błąd synchronizacji lokalizacji %s",
                        mid,
                    )

        def _unplaced_rows(self) -> list[MutableMapping[str, Any]]:
            out = []
            for row in self.rows:
                if not isinstance(row, dict):
                    continue
                status = str(row.get("placement_status") or "").strip().lower()
                if status in {"unplaced", "outside_room"}:
                    out.append(row)
            return out

        def _refresh_unplaced_button(self) -> None:
            if self._unplaced_button is not None:
                self._unplaced_button.configure(
                    text=f"Nieumieszczone ({len(self._unplaced_rows())})"
                )

        def _choose_unplaced_machine(self) -> None:
            candidates = self._unplaced_rows()
            if not candidates:
                messagebox.showinfo(
                    "Plan hali",
                    "Wszystkie maszyny mają poprawne położenie albo lokalizację zewnętrzną.",
                    parent=self.canvas.winfo_toplevel(),
                )
                return

            win = tk.Toplevel(self.canvas.winfo_toplevel())
            win.title("Nieumieszczone na planie")
            win.geometry("520x360")
            win.transient(self.canvas.winfo_toplevel())
            frame = ttk.Frame(win, padding=10)
            frame.pack(fill="both", expand=True)
            ttk.Label(
                frame, text="Wybierz maszynę, potem kliknij jej miejsce na planie:"
            ).pack(anchor="w", pady=(0, 6))
            listbox = tk.Listbox(frame)
            listbox.pack(fill="both", expand=True)
            ids: list[str] = []
            for row in candidates:
                mid = _machine_id(row)
                ids.append(mid)
                listbox.insert(
                    "end",
                    f"{mid}  |  {row.get('nazwa', '')}  |  {row.get('lokalizacja', '')}",
                )
            if ids:
                listbox.selection_set(0)

            def choose(_event=None):
                selection = listbox.curselection()
                if not selection:
                    return
                self._placement_machine_id = ids[int(selection[0])]
                target_row = next(
                    (
                        row
                        for row in self.rows
                        if isinstance(row, dict)
                        and _machine_id(row) == self._placement_machine_id
                    ),
                    None,
                )
                target_name = (
                    str(target_row.get("lokalizacja") or "")
                    if target_row is not None
                    else ""
                )
                self._status_var.set(
                    f"Umieść maszynę {self._placement_machine_id}"
                    + (f' w "{target_name}"' if target_name else "")
                    + " – kliknij punkt na planie."
                )
                win.destroy()
                self._draw_all()

            ttk.Button(frame, text="Umieść", command=choose).pack(
                side="right", pady=(6, 0)
            )
            listbox.bind("<Double-Button-1>", choose)

        def _place_machine_at(self, event) -> bool:
            mid = self._placement_machine_id
            if not mid:
                return False
            row = next(
                (
                    candidate
                    for candidate in self.rows
                    if isinstance(candidate, dict) and _machine_id(candidate) == mid
                ),
                None,
            )
            if row is None:
                self._placement_machine_id = None
                return True

            bx, by = self._map_canvas_to_bg(event.x, event.y)
            clicked_room = room_at_point(self._rooms, bx, by, hala=_hall_id(row))
            assigned = room_by_id(self._rooms, row.get("lokalizacja_id"))
            if assigned is not None and clicked_room is not assigned:
                messagebox.showwarning(
                    "Plan hali",
                    f'Kliknij punkt wewnątrz pomieszczenia "{assigned.name}".',
                    parent=self.canvas.winfo_toplevel(),
                )
                return True
            if assigned is None and clicked_room is None:
                messagebox.showwarning(
                    "Plan hali",
                    "Kliknij wewnątrz narysowanego pomieszczenia.",
                    parent=self.canvas.winfo_toplevel(),
                )
                return True

            sync_record_from_point(row, bx, by, self._rooms)
            try:
                if callable(self.on_drag_commit):
                    self.on_drag_commit(mid, bx, by)
            finally:
                self._placement_machine_id = None
            self._status_var.set(f"Umieszczono maszynę {mid}.")
            self._refresh_unplaced_button()
            self._draw_all()
            return True

        # ---------- rozdzielenie trybu układu od działającego drag&drop ----------
        def _on_press(self, event):
            if self._placement_machine_id:
                self._place_machine_at(event)
                self._drag_active = False
                self._drag_id = None
                return
            if not self._layout_edit:
                return super()._on_press(event)

            self.tip.hide()
            self._drag_active = False
            self._drag_id = None
            if self._draft_points or self._status_var.get().startswith("Nowe pomieszczenie"):
                if self._near_first_draft_point(event):
                    self._finish_draft_room()
                    return
                bx, by = self._map_canvas_to_bg(event.x, event.y)
                previous = self._draft_points[-1] if self._draft_points else None
                orthogonal = bool(getattr(event, "state", 0) & 0x0001)
                self._draft_points.append(
                    self._snap_world_point(
                        bx,
                        by,
                        previous=previous,
                        orthogonal=orthogonal,
                    )
                )
                self._layout_dirty = True
                self._draw_all()
                return

            vertex = self._vertex_at_canvas(event.x, event.y)
            if vertex is not None:
                self._vertex_drag = vertex
                self._vertex_drag_before = deepcopy(self._rooms)
                return

            room = self._room_at_canvas(event.x, event.y)
            self._selected_room_id = room.id if room is not None else None
            self._draw_all()

        def _on_motion(self, event):
            if not self._layout_edit:
                return super()._on_motion(event)
            if self._vertex_drag is None:
                return
            room_id, index = self._vertex_drag
            room = room_by_id(self._rooms, room_id)
            if room is None or not (0 <= index < len(room.polygon)):
                return
            bx, by = self._map_canvas_to_bg(event.x, event.y)
            room.polygon[index] = self._snap_world_point(bx, by)
            self._layout_dirty = True
            self._draw_all()

        def _on_release(self, event):
            if self._layout_edit:
                if self._vertex_drag is not None:
                    if self._vertex_drag_before is not None:
                        self._undo_stack.append(self._vertex_drag_before)
                        if len(self._undo_stack) > 30:
                            del self._undo_stack[0]
                    self._vertex_drag = None
                    self._vertex_drag_before = None
                return

            if self._drag_active and self._drag_id and self._rooms:
                node = self.nodes_by_id.get(self._drag_id)
                if node:
                    x1, y1, x2, y2 = self.canvas.coords(node)
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    bx, by = self._map_canvas_to_bg(cx, cy)
                    row = self.rows_by_id.get(self._drag_id)
                    if row is not None:
                        sync_record_from_point(row, bx, by, self._rooms)
            result = super()._on_release(event)
            self._refresh_unplaced_button()
            return result

    RoomAwareMachineHallRenderer.__name__ = "MachineHallRenderer"
    RoomAwareMachineHallRenderer.__qualname__ = "MachineHallRenderer"
    return RoomAwareMachineHallRenderer


def install_machine_rooms(legacy_module) -> None:
    """Zainstaluj rozszerzenie dokładnie raz w module Maszyn."""
    if getattr(legacy_module, "_WM_ROOM_EXTENSION_INSTALLED", False):
        return

    original_renderer = legacy_module.MachineHallRenderer
    original_upsert = legacy_module.upsert_machine
    real_ttk = legacy_module.ttk

    def current_rooms() -> list[Room]:
        return load_rooms()

    def location_values_provider() -> tuple[str, ...]:
        return location_values(current_rooms())

    def room_aware_upsert(rows, new_row):
        candidate = dict(new_row or {})
        if (
            "lokalizacja" in candidate
            or "lokalizacja_id" in candidate
            or "placement_status" in candidate
        ):
            sync_location_fields(candidate, current_rooms())
        return original_upsert(rows, candidate)

    legacy_module.upsert_machine = room_aware_upsert
    legacy_module.ttk = _TtkProxy(real_ttk, location_values_provider)
    legacy_module.MachineHallRenderer = _make_renderer(original_renderer, legacy_module)
    legacy_module._WM_ROOM_EXTENSION_INSTALLED = True
    log.info("[Maszyny][HALL][ROOMS] Rozszerzenie pomieszczeń aktywne")


__all__ = ["install_machine_rooms"]
