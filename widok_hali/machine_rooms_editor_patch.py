# version: 1.0
"""Narzędzia edycji pomieszczeń hali i kontrola dostępu brygadzisty.

Ta warstwa jest instalowana na końcu rozszerzeń modułu Maszyny. Nie zmienia
``gui_maszyny_legacy.py``. Rozdziela zwykłe kontrolki widoku od edycji
pomieszczeń, dodaje rysowanie prostokąta dwoma kliknięciami i pilnuje, aby
narzędzia modyfikujące układ hali były dostępne wyłącznie dla brygadzisty.
"""
from __future__ import annotations

from typing import Optional


_EDIT_WIDGET_TEXTS = {
    "Edytuj układ hali",
    "Nowe pomieszczenie",
    "Zmień nazwę",
    "Usuń pom.",
    "Cofnij",
    "Zapisz układ",
    "Anuluj",
}


def _normalize_role(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _is_brygadzista(value: object) -> bool:
    return _normalize_role(value) == "brygadzista"


def _role_from_widget(widget) -> str:
    """Odczytaj rolę przekazaną przez panel główny z najbliższego kontenera."""
    checked: set[int] = set()
    current = widget
    for _ in range(12):
        if current is None or id(current) in checked:
            break
        checked.add(id(current))
        for attr in ("_wm_role", "active_role", "rola", "role"):
            value = _normalize_role(getattr(current, attr, ""))
            if value:
                return value
        current = getattr(current, "master", None)

    try:
        top = widget.winfo_toplevel()
    except Exception:
        top = None
    if top is not None:
        for attr in ("_wm_role", "active_role", "rola", "role"):
            value = _normalize_role(getattr(top, attr, ""))
            if value:
                return value
    return ""


def _rectangle_polygon(
    first: tuple[int, int],
    opposite: tuple[int, int],
    *,
    minimum_size: int = 10,
) -> Optional[list[tuple[int, int]]]:
    """Zbuduj prostokąt z dwóch przeciwległych narożników."""
    x1, y1 = int(first[0]), int(first[1])
    x2, y2 = int(opposite[0]), int(opposite[1])
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    if right - left < int(minimum_size) or bottom - top < int(minimum_size):
        return None
    return [(left, top), (right, top), (right, bottom), (left, bottom)]


def install_machine_room_editor(legacy_module) -> None:
    """Dołóż prostokąty, jawny tryb edycji i ochronę roli dokładnie raz."""
    if getattr(legacy_module, "_WM_ROOM_EDITOR_INSTALLED", False):
        return

    base_renderer = legacy_module.MachineHallRenderer
    base_panel_maszyny = legacy_module.panel_maszyny
    tk = legacy_module.tk
    messagebox = legacy_module.messagebox
    wrapped_ttk = legacy_module.ttk
    real_ttk = getattr(wrapped_ttk, "_real", wrapped_ttk)

    def panel_maszyny_with_room_role(root, frame, login=None, rola=None):
        """Zachowaj istniejącą rolę panelu dla renderera hali."""
        role = _normalize_role(rola)
        if not role:
            role = _role_from_widget(root)
        for target in (root, frame):
            if target is None:
                continue
            try:
                setattr(target, "_wm_role", role)
                setattr(target, "_wm_login", str(login or "").strip())
            except Exception:
                pass
        return base_panel_maszyny(root, frame, login, rola)

    class MachineHallRendererWithRoomEditor(base_renderer):
        """Renderer hali z osobnym paskiem edycji pomieszczeń."""

        RECT_MIN_WORLD_PX = 10

        def __init__(self, parent, rows, cfg=None, on_drag_commit=None, bg_path=None):
            self._wm_room_role = _role_from_widget(parent)
            self._wm_room_tool: Optional[str] = None
            self._wm_rectangle_start: Optional[tuple[int, int]] = None
            self._wm_rectangle_hover: Optional[tuple[int, int]] = None
            self._wm_edit_toolbar = None
            super().__init__(
                parent,
                rows,
                cfg=cfg,
                on_drag_commit=on_drag_commit,
                bg_path=bg_path,
            )

        def _wm_can_edit_rooms(self) -> bool:
            role = _role_from_widget(self.parent) or self._wm_room_role
            return _is_brygadzista(role)

        def _build_room_toolbar(self) -> None:
            # Najpierw budujemy działający pasek bazowy (Dopasuj/zoom/Tło/Siatka
            # oraz dotychczasowe przyciski), a następnie chowamy tylko elementy
            # modyfikujące geometrię. Kontrolki widoku zostają dla wszystkich.
            super()._build_room_toolbar()
            for child in tuple(self._toolbar.winfo_children()):
                try:
                    text = str(child.cget("text") or "")
                except Exception:
                    text = ""
                if text in _EDIT_WIDGET_TEXTS:
                    try:
                        child.pack_forget()
                    except Exception:
                        pass

            self._wm_edit_toolbar = real_ttk.Frame(self.parent)
            real_ttk.Label(
                self._wm_edit_toolbar,
                text="Pomieszczenia:",
            ).pack(side="left", padx=(0, 6))

            self._wm_edit_toggle = real_ttk.Checkbutton(
                self._wm_edit_toolbar,
                text="Edytuj pomieszczenia",
                variable=self._edit_var,
                command=self._toggle_layout_edit,
            )
            self._wm_edit_toggle.pack(side="left", padx=(0, 8))

            self._wm_btn_polygon = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Rysuj liniami",
                command=self._wm_start_polygon,
            )
            self._wm_btn_rectangle = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Prostokąt",
                command=self._wm_start_rectangle,
            )
            self._wm_btn_edit_room = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Edytuj pomieszczenie",
                command=self._wm_start_existing_room_edit,
            )
            self._wm_btn_rename = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Zmień nazwę",
                command=self._rename_selected_room,
            )
            self._wm_btn_delete = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Usuń pom.",
                command=self._delete_selected_room,
            )
            self._wm_btn_undo_room = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Cofnij",
                command=self._undo_layout,
            )
            self._wm_btn_save_room = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Zapisz układ",
                command=self._save_layout,
            )
            self._wm_btn_cancel_room = real_ttk.Button(
                self._wm_edit_toolbar,
                text="Anuluj",
                command=self._cancel_layout,
            )
            self._wm_edit_action_buttons = (
                self._wm_btn_polygon,
                self._wm_btn_rectangle,
                self._wm_btn_edit_room,
                self._wm_btn_rename,
                self._wm_btn_delete,
                self._wm_btn_undo_room,
                self._wm_btn_save_room,
                self._wm_btn_cancel_room,
            )
            for button in self._wm_edit_action_buttons:
                button.pack(side="left", padx=2)
            self._wm_set_editor_button_state(False)

        def render(self) -> None:
            super().render()
            if self._wm_can_edit_rooms() and self._wm_edit_toolbar is not None:
                try:
                    self._wm_edit_toolbar.pack(
                        fill="x",
                        padx=8,
                        pady=(2, 0),
                        before=self._status_label,
                    )
                except Exception:
                    self._wm_edit_toolbar.pack(fill="x", padx=8, pady=(2, 0))
            else:
                self._edit_var.set(False)
                self._layout_edit = False
                if self._wm_edit_toolbar is not None:
                    try:
                        self._wm_edit_toolbar.pack_forget()
                    except Exception:
                        pass

        def _wm_set_editor_button_state(self, enabled: bool) -> None:
            state = ["!disabled"] if enabled and self._wm_can_edit_rooms() else ["disabled"]
            for button in getattr(self, "_wm_edit_action_buttons", ()):
                try:
                    button.state(state)
                except Exception:
                    pass

        def _wm_clear_rectangle(self) -> None:
            self._wm_rectangle_start = None
            self._wm_rectangle_hover = None
            try:
                self.canvas.delete("hall-room-rect-preview")
            except Exception:
                pass

        def _wm_leave_current_tool(self) -> None:
            self._wm_clear_rectangle()
            self._draft_points = []
            self._vertex_drag = None
            self._vertex_drag_before = None

        def _toggle_layout_edit(self) -> None:
            if bool(self._edit_var.get()) and not self._wm_can_edit_rooms():
                self._edit_var.set(False)
                self._layout_edit = False
                self._wm_room_tool = None
                self._wm_set_editor_button_state(False)
                self._status_var.set("Edycja pomieszczeń jest dostępna tylko dla brygadzisty.")
                return

            super()._toggle_layout_edit()
            if self._layout_edit:
                self._wm_room_tool = "edit"
                self._status_var.set(
                    "Edycja pomieszczeń: wybierz Rysuj liniami, Prostokąt albo Edytuj pomieszczenie."
                )
            else:
                self._wm_room_tool = None
                self._wm_leave_current_tool()
            self._wm_set_editor_button_state(self._layout_edit)

        def _wm_start_polygon(self) -> None:
            if not self._wm_can_edit_rooms() or not self._layout_edit:
                return
            self._wm_leave_current_tool()
            self._wm_room_tool = "polygon"
            super()._start_room()

        def _wm_start_rectangle(self) -> None:
            if not self._wm_can_edit_rooms() or not self._layout_edit:
                return
            self._wm_leave_current_tool()
            self._wm_room_tool = "rectangle"
            self._selected_room_id = None
            self._status_var.set(
                "Prostokąt: kliknij pierwszy narożnik, potem przeciwległy narożnik."
            )
            self._draw_all()

        def _wm_start_existing_room_edit(self) -> None:
            if not self._wm_can_edit_rooms() or not self._layout_edit:
                return
            self._wm_leave_current_tool()
            self._wm_room_tool = "edit"
            self._status_var.set(
                "Edytuj pomieszczenie: kliknij pomieszczenie, potem przeciągaj jego narożniki."
            )
            self._draw_all()

        def _wm_draw_rectangle_preview(self) -> None:
            try:
                self.canvas.delete("hall-room-rect-preview")
            except Exception:
                return
            if (
                not self._layout_edit
                or self._wm_room_tool != "rectangle"
                or self._wm_rectangle_start is None
                or self._wm_rectangle_hover is None
            ):
                return
            x1, y1 = self._map_bg_to_canvas(*self._wm_rectangle_start)
            x2, y2 = self._map_bg_to_canvas(*self._wm_rectangle_hover)
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=getattr(self, "ROOM_DRAFT", "#a78bfa"),
                width=2,
                dash=(6, 4),
                tags=("hall-room-rect-preview",),
            )

        def _draw_rooms(self) -> None:
            super()._draw_rooms()
            self._wm_draw_rectangle_preview()

        def _on_canvas_motion(self, event):
            result = super()._on_canvas_motion(event)
            if (
                self._layout_edit
                and self._wm_room_tool == "rectangle"
                and self._wm_rectangle_start is not None
            ):
                bx, by = self._map_canvas_to_bg(event.x, event.y)
                self._wm_rectangle_hover = self._snap_world_point(bx, by)
                self._wm_draw_rectangle_preview()
            return result

        def _on_press(self, event):
            if self._layout_edit and not self._wm_can_edit_rooms():
                self._edit_var.set(False)
                self._layout_edit = False
                self._wm_room_tool = None
                self._wm_set_editor_button_state(False)
                return super()._on_press(event)

            if self._layout_edit and self._wm_room_tool == "rectangle":
                self.tip.hide()
                self._drag_active = False
                self._drag_id = None
                bx, by = self._map_canvas_to_bg(event.x, event.y)
                point = self._snap_world_point(bx, by)
                if self._wm_rectangle_start is None:
                    self._wm_rectangle_start = point
                    self._wm_rectangle_hover = point
                    self._status_var.set(
                        "Prostokąt: teraz kliknij przeciwległy narożnik."
                    )
                    self._wm_draw_rectangle_preview()
                    return

                polygon = _rectangle_polygon(
                    self._wm_rectangle_start,
                    point,
                    minimum_size=self.RECT_MIN_WORLD_PX,
                )
                if polygon is None:
                    self._status_var.set(
                        "Prostokąt jest za mały. Wskaż dalszy przeciwległy narożnik."
                    )
                    return

                self._draft_points = polygon
                self._wm_clear_rectangle()
                before_count = len(self._rooms)
                super()._finish_draft_room()
                if len(self._rooms) > before_count:
                    self._wm_room_tool = "edit"
                    room = self._selected_room()
                    if room is not None:
                        self._status_var.set(
                            f'Dodano "{room.name}". Możesz od razu przeciągać jego narożniki.'
                        )
                else:
                    # Anulowana nazwa lub walidacja nie może pozostawić połowy
                    # prostokąta jako szkicu trybu liniowego.
                    self._draft_points = []
                    self._wm_room_tool = "rectangle"
                    self._status_var.set(
                        "Prostokąt nie został dodany. Kliknij pierwszy narożnik, aby spróbować ponownie."
                    )
                    self._draw_all()
                return

            return super()._on_press(event)

        # Dodatkowa warstwa ochrony: nawet programowe wywołanie metod edycji
        # nie zapisze geometrii, jeśli aktywna rola nie jest brygadzistą.
        def _start_room(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._start_room()
            return None

        def _rename_selected_room(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._rename_selected_room()
            return None

        def _delete_selected_room(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._delete_selected_room()
            return None

        def _undo_layout(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._undo_layout()
            return None

        def _save_layout(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._save_layout()
            try:
                messagebox.showwarning(
                    "Układ hali",
                    "Edycja pomieszczeń jest dostępna tylko dla brygadzisty.",
                    parent=self.canvas.winfo_toplevel(),
                )
            except Exception:
                pass
            return None

        def _cancel_layout(self) -> None:
            if self._wm_can_edit_rooms():
                return super()._cancel_layout()
            return None

    MachineHallRendererWithRoomEditor.__name__ = "MachineHallRenderer"
    MachineHallRendererWithRoomEditor.__qualname__ = "MachineHallRenderer"

    legacy_module.panel_maszyny = panel_maszyny_with_room_role
    legacy_module.MachineHallRenderer = MachineHallRendererWithRoomEditor
    legacy_module._WM_ROOM_EDITOR_INSTALLED = True


__all__ = [
    "_is_brygadzista",
    "_rectangle_polygon",
    "install_machine_room_editor",
]
