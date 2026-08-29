# version: 1.2
# Moduł: settings_tools_runtime
# UI-only: porządkowanie Ustawienia → Moduły → Narzędzia.
# 1.2: zawersjonowano wybór Klasyczny / Nowy dla wspólnego edytora NN i SN.
# 1.1: dodano wspólny wybór Klasyczny / Nowy dla edytora NN i SN.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from config_manager import ConfigManager


def _all_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


def _module_tab(panel: Any, title: str) -> tk.Misc | None:
    nb = getattr(panel, "_modules_nb", None)
    if nb is None:
        return None
    wanted = str(title or "").strip().lower()
    for tab_id in nb.tabs():
        try:
            if str(nb.tab(tab_id, "text") or "").strip().lower() == wanted:
                return nb.nametowidget(tab_id)
        except Exception:
            continue
    return None


def _label_frame(root: tk.Misc, *titles: str) -> ttk.LabelFrame | None:
    wanted = {str(x).strip().lower() for x in titles}
    for child in _all_descendants(root):
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            text = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if text in wanted:
            return child
    return None


def _hide(widget: tk.Misc) -> None:
    try:
        if widget.grid_info():
            widget.grid_remove()
            return
    except Exception:
        pass
    try:
        if widget.pack_info():
            widget.pack_forget()
    except Exception:
        pass


def _rename_groups(panel: Any) -> None:
    root = _module_tab(panel, "Narzędzia")
    if root is None:
        return
    mapping = {
        "import narzędzi z excela": "Dane — import / eksport",
        "podgląd zdjęć": "Wygląd — zdjęcia",
        "kolekcje narzędzi": "Logika — kolekcje NN / SN",
        "podgląd definicji nn/sn (tylko do odczytu)": "Definicje — typy, statusy i zadania",
        "wersja panelu": "Wygląd — panel i edytor",
    }
    for child in _all_descendants(root):
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            old = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if old in mapping:
            try:
                child.configure(text=mapping[old])
            except Exception:
                pass


def _remove_global_statuses(panel: Any) -> None:
    root = _module_tab(panel, "Narzędzia")
    if root is None:
        return
    box = _label_frame(root, "Statusy globalne (zakończenia)")
    if box is not None:
        _hide(box)

    defs = _label_frame(
        root,
        "Definicje — typy, statusy i zadania",
        "Podgląd definicji NN/SN (tylko do odczytu)",
    )
    if defs is not None and not getattr(defs, "_wm_status_hint", False):
        ttk.Label(
            defs,
            text=(
                "Statusy są definiowane dla konkretnego typu narzędzia. "
                "W edytorze ustawiasz też jeden status bazowy wizyty dla danego typu."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 8))
        setattr(defs, "_wm_status_hint", True)


def _collections_checkboxes(panel: Any) -> None:
    root = _module_tab(panel, "Narzędzia")
    if root is None:
        return
    box = _label_frame(root, "Logika — kolekcje NN / SN", "Kolekcje narzędzi")
    if box is None or getattr(box, "_wm_collections_choices", False):
        return

    source_var = getattr(panel, "vars", {}).get("tools.collections_enabled")
    default_var = getattr(panel, "vars", {}).get("tools.default_collection")
    old_entry = getattr(panel, "entry_tools_collections_enabled", None)
    combo = getattr(panel, "combo_tools_default_collection", None)
    if source_var is None or old_entry is None:
        return

    try:
        info = old_entry.grid_info()
    except Exception:
        info = {}
    if not info:
        return
    _hide(old_entry)

    holder = ttk.Frame(box)
    holder.grid(
        row=info.get("row", 0),
        column=info.get("column", 1),
        sticky="w",
        padx=info.get("padx", 8),
        pady=info.get("pady", 6),
    )

    def _current_items() -> list[str]:
        try:
            value = source_var.get()
        except Exception:
            value = []
        if isinstance(value, str):
            return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]
        return [str(x).strip() for x in (value or []) if str(x).strip()]

    current = _current_items()
    vars_by_code = {
        "NN": tk.BooleanVar(master=holder, value="NN" in current),
        "SN": tk.BooleanVar(master=holder, value="SN" in current),
    }

    extras = [x for x in current if x not in vars_by_code]

    def _sync() -> None:
        selected = [code for code in ("NN", "SN") if vars_by_code[code].get()]
        selected.extend(x for x in extras if x not in selected)
        if not selected:
            # Zawsze zostaw co najmniej jedną kolekcję aktywną.
            vars_by_code["NN"].set(True)
            selected = ["NN"]
        try:
            source_var.set(selected)
        except Exception:
            source_var.set(", ".join(selected))
        if combo is not None:
            try:
                combo.configure(values=selected)
            except Exception:
                pass
        if default_var is not None:
            try:
                if str(default_var.get() or "") not in selected:
                    default_var.set(selected[0])
            except Exception:
                pass

    ttk.Checkbutton(holder, text="NN — nowe", variable=vars_by_code["NN"], command=_sync).pack(side="left", padx=(0, 12))
    ttk.Checkbutton(holder, text="SN — stare", variable=vars_by_code["SN"], command=_sync).pack(side="left")
    if extras:
        ttk.Label(holder, text="Inne: " + ", ".join(extras)).pack(side="left", padx=(12, 0))

    if combo is not None:
        try:
            values = [code for code in ("NN", "SN") if vars_by_code[code].get()] + extras
            combo.configure(values=values, state="readonly")
        except Exception:
            pass

    setattr(box, "_wm_collections_choices", True)


def _friendly_preview_delay(panel: Any) -> None:
    root = _module_tab(panel, "Narzędzia")
    if root is None:
        return
    box = _label_frame(root, "Wygląd — zdjęcia", "Podgląd zdjęć")
    if box is None or getattr(box, "_wm_preview_delay_friendly", False):
        return

    source_var = getattr(panel, "vars", {}).get("tools.preview_delay_sec")
    combo = next((x for x in _all_descendants(box) if isinstance(x, ttk.Combobox)), None)
    if source_var is None or combo is None:
        return

    display = tk.StringVar(master=box)
    labels = {"1": "1 s", "2": "2 s", "3": "3 s"}

    def _from_source(*_args: Any) -> None:
        try:
            value = str(source_var.get())
        except Exception:
            value = "3"
        display.set(labels.get(value, f"{value} s"))

    def _from_display(_event=None) -> None:
        selected = str(display.get() or "")
        for value, label in labels.items():
            if selected == label:
                source_var.set(value)
                break

    try:
        combo.unbind("<<ComboboxSelected>>")
    except Exception:
        pass
    combo.configure(textvariable=display, values=list(labels.values()), state="readonly", width=9)
    combo.bind("<<ComboboxSelected>>", _from_display)
    try:
        source_var.trace_add("write", _from_source)
    except Exception:
        pass
    _from_source()
    setattr(box, "_wm_preview_delay_friendly", True)


def _editor_variant_selector(panel: Any) -> None:
    """Add one shared NN/SN editor selector without replacing the classic editor."""

    root = _module_tab(panel, "Narzędzia")
    if root is None:
        return
    box = _label_frame(root, "Wygląd — panel i edytor", "Wersja panelu")
    if box is None or getattr(box, "_wm_editor_variant_selector", False):
        return

    rows: list[int] = []
    for child in box.winfo_children():
        try:
            info = child.grid_info()
            if info:
                rows.append(int(info.get("row", 0)))
        except Exception:
            continue
    row = max(rows, default=-1) + 1

    ttk.Separator(box, orient="horizontal").grid(
        row=row,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=8,
        pady=(10, 8),
    )
    row += 1

    ttk.Label(box, text="Edytor NN / SN").grid(
        row=row,
        column=0,
        sticky="w",
        padx=8,
        pady=6,
    )

    labels = {
        "classic": "Klasyczny",
        "card": "Nowy — karta z miniaturą",
    }
    reverse = {label: value for value, label in labels.items()}

    try:
        current = str(ConfigManager().get("tools.editor_variant", "classic") or "classic").strip().lower()
    except Exception:
        current = "classic"
    if current not in labels:
        current = "classic"

    display = tk.StringVar(master=box, value=labels[current])
    combo = ttk.Combobox(
        box,
        textvariable=display,
        values=list(labels.values()),
        state="readonly",
        width=30,
    )
    combo.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
    try:
        box.columnconfigure(1, weight=1)
    except Exception:
        pass

    row += 1
    ttk.Label(
        box,
        text=(
            "Wspólny wybór dla NN i SN. Klasyczny widok pozostaje dostępny; "
            "zmiana działa od następnego otwarcia edytora."
        ),
        wraplength=760,
        justify="left",
    ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

    def _save_variant(_event=None) -> None:
        value = reverse.get(str(display.get() or ""), "classic")
        try:
            cfg = ConfigManager()
            cfg.set("tools.editor_variant", value, who="settings")
            cfg.save_all()
        except Exception:
            return
        try:
            panel.event_generate("<<ConfigUpdated>>", when="tail")
        except Exception:
            pass

    combo.bind("<<ComboboxSelected>>", _save_variant)
    setattr(box, "_wm_editor_variant_selector", True)


def _decorate(panel: Any) -> None:
    for action in (
        _rename_groups,
        _remove_global_statuses,
        _collections_checkboxes,
        _friendly_preview_delay,
        _editor_variant_selector,
    ):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_tools_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_tools_runtime", False):
        return
    original = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original):
        return

    def _build_ui_with_tools(self, *args: Any, **kwargs: Any):
        result = original(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_tools
    settings_panel_cls._wm_settings_tools_runtime = True
