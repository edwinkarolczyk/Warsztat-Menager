# version: 1.0
"""Lokalizacja w nagłówku „Użytkowanie maszyny”.

Dodatek jest celowo warstwowy: nie zmienia gui_maszyny_legacy.py. Rozszerza
aktualny proxy ttk o prawą etykietę lokalizacji oraz udostępnia prosty wybór
pomieszczenia po kliknięciu „Brak lokalizacji”.
"""
from __future__ import annotations

from copy import deepcopy
import weakref
from typing import Any, MutableMapping, Optional

from .rooms import (
    Room,
    load_rooms,
    normalize_hall_id,
    point_in_polygon,
    room_by_id,
    room_by_name,
    sync_location_fields,
)

_LOCATION_KEYS = ("lokalizacja", "lokalizacja_id", "placement_status")


def _machine_id(row: MutableMapping[str, Any]) -> str:
    return str(row.get("id") or row.get("nr_ewid") or row.get("nr") or "").strip()


def _location_signature(row: MutableMapping[str, Any]) -> tuple[object, object, object]:
    return tuple(row.get(key) for key in _LOCATION_KEYS)  # type: ignore[return-value]


def _location_patch(row: MutableMapping[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in _LOCATION_KEYS}


def _patch_signature(patch: MutableMapping[str, Any]) -> tuple[object, object, object]:
    return tuple(patch.get(key) for key in _LOCATION_KEYS)  # type: ignore[return-value]


def _usage_machine_id(widget) -> str:
    """Odczytaj ID z tytułu „Użytkowanie maszyny — ID”."""
    try:
        title = str(widget.winfo_toplevel().title() or "").strip()
    except Exception:
        return ""
    if not title.lower().startswith("użytkowanie maszyny"):
        return ""
    tail = title[len("Użytkowanie maszyny") :].strip()
    for separator in ("—", "–", "-"):
        if tail.startswith(separator):
            return tail[len(separator) :].strip()
    return tail.strip()


def _row_for_machine(rows, machine_id: str) -> Optional[dict[str, Any]]:
    target = str(machine_id or "").strip()
    for row in rows or []:
        if isinstance(row, dict) and _machine_id(row) == target:
            return row
    return None


def _display_location(row: Optional[MutableMapping[str, Any]], rooms: list[Room]) -> str:
    if row is None:
        return "Brak lokalizacji"
    candidate = deepcopy(dict(row))
    sync_location_fields(candidate, rooms)
    value = str(candidate.get("lokalizacja") or "").strip()
    if value and value.casefold() != "brak lokalizacji":
        return value
    return "Brak lokalizacji"


def _rooms_for_machine(row: MutableMapping[str, Any], rooms: list[Room]) -> list[Room]:
    hall = normalize_hall_id(row.get("nr_hali") or row.get("hala") or "1")
    return [
        room
        for room in rooms
        if room.active and normalize_hall_id(room.hala) == hall
    ]


def install_machine_usage_location(legacy_module) -> None:
    """Dodaj lokalizację do widoku użytkowania maszyny dokładnie raz."""
    if getattr(legacy_module, "_WM_USAGE_LOCATION_INSTALLED", False):
        return

    wrapped_ttk = legacy_module.ttk
    real_ttk = getattr(wrapped_ttk, "_real", wrapped_ttk)
    tk = legacy_module.tk
    messagebox = legacy_module.messagebox
    base_upsert = legacy_module.upsert_machine
    base_renderer = legacy_module.MachineHallRenderer

    # Po zapisie z okna Użytkowanie panel może nadal trzymać poprzednią kopię
    # rows_cache. Override chroni świeżą lokalizację przed nadpisaniem przez
    # późniejszy zapis statusu/serwisu z tej starej kopii.
    overrides: dict[str, dict[str, Any]] = {}
    renderers: "weakref.WeakSet[object]" = weakref.WeakSet()

    def _load_rows_and_path() -> tuple[list[dict], str]:
        cfg = legacy_module.get_config() or {}
        rows, primary_path = legacy_module.load_machines_rows_with_fallback(
            cfg, legacy_module.resolve_rel
        )
        if not rows:
            rows = list(legacy_module.load_machines_rows() or [])
        return list(rows or []), str(primary_path or "")

    def _current_row(machine_id: str) -> Optional[dict[str, Any]]:
        rows, _path = _load_rows_and_path()
        return _row_for_machine(rows, machine_id)

    def _current_display(machine_id: str) -> str:
        return _display_location(_current_row(machine_id), load_rooms())

    def _refresh_live_renderers(rows: list[dict]) -> None:
        for renderer in list(renderers):
            try:
                renderer.update_rows(deepcopy(rows))
            except Exception:
                pass

    def _assign_machine_to_room(machine_id: str, room_name: str) -> dict[str, Any]:
        rows, primary_path = _load_rows_and_path()
        existing = _row_for_machine(rows, machine_id)
        if existing is None:
            raise ValueError(f"Nie znaleziono maszyny {machine_id}.")

        rooms = load_rooms()
        candidates = _rooms_for_machine(existing, rooms)
        room = room_by_name(candidates, room_name)
        if room is None:
            raise ValueError(f'Nie znaleziono pomieszczenia „{room_name}” dla tej hali.')

        before = _location_signature(existing)
        candidate = deepcopy(existing)
        candidate["lokalizacja"] = room.name
        candidate["lokalizacja_id"] = room.id

        # base_upsert zawiera już wdrożoną logikę relokacji do wolnego punktu
        # wewnątrz wybranego pomieszczenia.
        new_rows = base_upsert(rows, candidate)
        changed = _row_for_machine(new_rows, machine_id)
        if changed is None:
            raise ValueError(f"Nie udało się zaktualizować maszyny {machine_id}.")

        if not legacy_module._save_machines(primary_path, new_rows):
            raise OSError("Nie udało się zapisać lokalizacji maszyny.")

        after = _location_patch(changed)
        overrides[str(machine_id)] = {
            "before": before,
            "after": dict(after),
        }
        _refresh_live_renderers(list(new_rows))
        return deepcopy(changed)

    def upsert_with_usage_location_guard(rows, new_row):
        candidate = dict(new_row or {})
        mid = _machine_id(candidate)
        guard = overrides.get(mid)
        if guard:
            incoming = _location_signature(candidate)
            before = tuple(guard.get("before") or ())
            after_patch = dict(guard.get("after") or {})
            after = _patch_signature(after_patch)
            if incoming == before:
                # Stary rows_cache zapisuje np. nowy status – dokładamy świeżą
                # lokalizację zamiast pozwolić mu ją cofnąć.
                candidate.update(after_patch)
            elif incoming == after:
                # Panel dogonił już zapis na dysku; strażnik nie jest potrzebny.
                overrides.pop(mid, None)
            else:
                # Użytkownik jawnie wybrał inną lokalizację w formularzu.
                overrides.pop(mid, None)
        return base_upsert(rows, candidate)

    def _ask_room(parent, machine_id: str, on_saved) -> None:
        row = _current_row(machine_id)
        if row is None:
            messagebox.showerror(
                "Lokalizacja maszyny",
                f"Nie znaleziono maszyny {machine_id}.",
                parent=parent,
            )
            return
        rooms = _rooms_for_machine(row, load_rooms())
        if not rooms:
            messagebox.showinfo(
                "Lokalizacja maszyny",
                "Dla tej hali nie ma jeszcze narysowanych pomieszczeń.",
                parent=parent,
            )
            return

        win = tk.Toplevel(parent)
        win.title(f"Przypisz lokalizację — {machine_id}")
        win.transient(parent)
        win.resizable(False, False)
        try:
            win.grab_set()
        except Exception:
            pass

        body = real_ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        real_ttk.Label(
            body,
            text="Wybierz pomieszczenie dla maszyny:",
        ).pack(anchor="w", pady=(0, 6))
        names = [room.name for room in rooms]
        combo = real_ttk.Combobox(body, values=tuple(names), state="readonly", width=34)
        combo.pack(fill="x")
        combo.set(names[0])

        buttons = real_ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))

        def save_choice() -> None:
            selected = str(combo.get() or "").strip()
            if not selected:
                return
            try:
                changed = _assign_machine_to_room(machine_id, selected)
            except Exception as exc:
                messagebox.showerror(
                    "Lokalizacja maszyny",
                    f"Nie udało się zapisać lokalizacji:\n{exc}",
                    parent=win,
                )
                return
            try:
                on_saved(str(changed.get("lokalizacja") or selected))
            finally:
                win.destroy()

        real_ttk.Button(buttons, text="Anuluj", command=win.destroy).pack(side="right")
        real_ttk.Button(buttons, text="Zapisz", command=save_choice).pack(
            side="right", padx=(0, 6)
        )
        try:
            combo.focus_set()
        except Exception:
            pass

    class UsageStatusLabel(real_ttk.Label):
        """Status po lewej + lokalizacja 2 pkt mniejsza po prawej."""

        def __init__(self, master=None, *args, machine_id: str = "", **kwargs):
            self._wm_machine_id = machine_id
            self._wm_location_label = None
            self._wm_location_installed = False
            super().__init__(master, *args, **kwargs)

        def pack(self, cnf=None, **kwargs):
            options = dict(cnf or {})
            options.update(kwargs)
            options.pop("side", None)
            result = super().pack(side="left", **options)
            if not self._wm_location_installed:
                self._wm_location_installed = True
                try:
                    self.after_idle(self._wm_install_location)
                except Exception:
                    self._wm_install_location()
            return result

        def _wm_install_location(self) -> None:
            if self._wm_location_label is not None:
                return
            location = _current_display(self._wm_machine_id)
            label = real_ttk.Label(
                self.master,
                text=location,
                font=("TkDefaultFont", 22, "bold"),
                anchor="e",
                justify="right",
            )
            label.pack(side="right", anchor="e", padx=10, pady=8)
            self._wm_location_label = label
            self._wm_configure_location_click()

        def _wm_configure_location_click(self) -> None:
            label = self._wm_location_label
            if label is None:
                return
            try:
                label.unbind("<Button-1>")
            except Exception:
                pass
            if str(label.cget("text") or "").strip().casefold() != "brak lokalizacji":
                try:
                    label.configure(cursor="")
                except Exception:
                    pass
                return
            try:
                label.configure(cursor="hand2")
            except Exception:
                pass

            def clicked(_event=None):
                top = self.winfo_toplevel()

                def saved(value: str) -> None:
                    label.configure(text=value, cursor="")
                    self._wm_configure_location_click()

                _ask_room(top, self._wm_machine_id, saved)

            label.bind("<Button-1>", clicked)

    class UsageLocationTtkProxy:
        def __init__(self):
            self._wrapped = wrapped_ttk
            self._real = real_ttk

        def __getattr__(self, name: str):
            return getattr(self._wrapped, name)

        def LabelFrame(self, master=None, *args, **kwargs):  # noqa: N802
            frame = self._wrapped.LabelFrame(master, *args, **kwargs)
            if str(kwargs.get("text") or "") == "Aktualny status":
                mid = _usage_machine_id(frame)
                if mid:
                    setattr(frame, "_wm_usage_machine_id", mid)
            return frame

        def Label(self, master=None, *args, **kwargs):  # noqa: N802
            mid = str(getattr(master, "_wm_usage_machine_id", "") or "").strip()
            if mid:
                return UsageStatusLabel(master, *args, machine_id=mid, **kwargs)
            return self._wrapped.Label(master, *args, **kwargs)

    class UsageLocationRenderer(base_renderer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                renderers.add(self)
            except Exception:
                pass

    UsageLocationRenderer.__name__ = "MachineHallRenderer"
    UsageLocationRenderer.__qualname__ = "MachineHallRenderer"

    legacy_module.upsert_machine = upsert_with_usage_location_guard
    legacy_module.ttk = UsageLocationTtkProxy()
    legacy_module.MachineHallRenderer = UsageLocationRenderer
    legacy_module._wm_assign_machine_to_room = _assign_machine_to_room
    legacy_module._WM_USAGE_LOCATION_OVERRIDES = overrides
    legacy_module._WM_USAGE_LOCATION_INSTALLED = True


__all__ = [
    "_display_location",
    "_location_signature",
    "_usage_machine_id",
    "install_machine_usage_location",
]
