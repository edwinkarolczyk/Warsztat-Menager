# version: 1.1
"""Warstwowe rozszerzenie listy Maszyn o kolumnę i filtr lokalizacji."""
from __future__ import annotations

from typing import Any

_INSTALLED = False
_ALL_LOCATIONS = "Wszystkie lokalizacje"
_NO_LOCATION = "Brak lokalizacji"


def _location_text(machine: dict[str, Any]) -> str:
    return str(
        machine.get("lokalizacja")
        or machine.get("location")
        or machine.get("miejsce")
        or ""
    ).strip()


def install(module) -> None:
    global _INSTALLED
    if _INSTALLED or getattr(module, "_wm_machine_location_filter_installed", False):
        return

    layout = list(getattr(module, "_TREE_COLUMN_LAYOUT", ()) or ())
    if not any(str(item[0]) == "lokalizacja" for item in layout if item):
        entry = ("lokalizacja", "Lokalizacja", 160, "w")
        insert_at = next(
            (idx for idx, item in enumerate(layout) if item and str(item[0]) == "przeglad"),
            len(layout),
        )
        layout.insert(insert_at, entry)
        module._TREE_COLUMN_LAYOUT = tuple(layout)

    original_insert = module._tree_insert_row

    def _tree_insert_row(tree, machine):
        location = _location_text(machine if isinstance(machine, dict) else {})
        selected = _ALL_LOCATIONS
        try:
            variable = getattr(tree, "_wm_location_filter_var", None)
            if variable is not None:
                selected = str(variable.get() or _ALL_LOCATIONS).strip()
        except Exception:
            selected = _ALL_LOCATIONS

        if selected == _NO_LOCATION:
            if location:
                return ""
        elif selected != _ALL_LOCATIONS:
            if location.casefold() != selected.casefold():
                return ""

        item_id = original_insert(tree, machine)

        # Po edycji lokalizacji dopisz nową wartość do filtra bez przebudowy UI.
        if location:
            try:
                combo = getattr(tree, "_wm_location_filter_box", None)
                if combo is not None:
                    values = list(combo.cget("values") or ())
                    if location not in values:
                        values.append(location)
                        head = [value for value in values if value == _ALL_LOCATIONS]
                        tail = sorted(
                            {
                                str(value)
                                for value in values
                                if value not in {_ALL_LOCATIONS, _NO_LOCATION} and str(value).strip()
                            },
                            key=str.casefold,
                        )
                        if _NO_LOCATION in values:
                            tail.append(_NO_LOCATION)
                        combo.configure(values=tuple(head + tail))
            except Exception:
                pass
        return item_id

    module._tree_insert_row = _tree_insert_row

    original_open = module._open_machines_panel

    def _walk(widget):
        try:
            children = list(widget.winfo_children())
        except Exception:
            return
        for child in children:
            yield child
            yield from _walk(child)

    def _open_machines_panel(root, container, Renderer=None, *, initial_machine_id=""):
        result = original_open(
            root,
            container,
            Renderer,
            initial_machine_id=initial_machine_id,
        )

        tree = None
        for widget in _walk(container):
            try:
                columns = tuple(str(value) for value in (widget.cget("columns") or ()))
            except Exception:
                continue
            if "lokalizacja" in columns and "przeglad" in columns:
                tree = widget
                break
        if tree is None:
            return result

        locations: set[str] = set()
        has_empty = False
        try:
            for iid in tree.get_children(""):
                value = str(tree.set(iid, "lokalizacja") or "").strip()
                if value:
                    locations.add(value)
                else:
                    has_empty = True
        except Exception:
            pass

        left = getattr(tree, "master", None)
        toolbar = None
        if left is not None:
            try:
                candidates = list(left.winfo_children())
            except Exception:
                candidates = []
            for candidate in candidates:
                try:
                    labels = [
                        str(child.cget("text") or "")
                        for child in candidate.winfo_children()
                        if hasattr(child, "cget")
                    ]
                except Exception:
                    continue
                if "Szukaj:" in labels and "Filtr:" in labels:
                    toolbar = candidate
                    break
        if toolbar is None:
            return result

        location_var = module.tk.StringVar(value=_ALL_LOCATIONS)
        values = [_ALL_LOCATIONS, *sorted(locations, key=str.casefold)]
        if has_empty:
            values.append(_NO_LOCATION)

        module.ttk.Label(toolbar, text="Lokalizacja:").pack(side="left", padx=(8, 4))
        location_box = module.ttk.Combobox(
            toolbar,
            state="readonly",
            width=18,
            values=tuple(values),
            textvariable=location_var,
        )
        location_box.pack(side="left", padx=(0, 8))
        tree._wm_location_filter_var = location_var
        tree._wm_location_filter_box = location_box

        schedule_filter = None
        try:
            toolbar_children = list(toolbar.winfo_children())
        except Exception:
            toolbar_children = []
        for child in toolbar_children:
            if child is location_box:
                continue
            try:
                raw_values = child.cget("values")
            except Exception:
                continue
            options = {str(value) for value in (raw_values or ())}
            if "Po terminie" in options and "Wkrótce" in options:
                schedule_filter = child
                break

        def _apply_location(_event=None):
            if schedule_filter is not None:
                try:
                    schedule_filter.event_generate("<<ComboboxSelected>>")
                    return
                except Exception:
                    pass
            # Jeśli struktura toolbara kiedyś się zmieni, filtr nie blokuje modułu.
            try:
                tree.event_generate("<<TreeviewSelect>>")
            except Exception:
                pass

        location_box.bind("<<ComboboxSelected>>", _apply_location, add=True)
        return result

    module._open_machines_panel = _open_machines_panel
    module._wm_machine_location_filter_installed = True
    _INSTALLED = True


__all__ = ["install"]
