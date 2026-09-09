# version: 1.0
# Moduł: settings_orders_runtime
# UI-only: więcej wyboru, mniej ręcznego formatu w Ustawienia → Moduły → Zlecenia.

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Any


_DEFAULT_CODES = ("ZW", "ZN", "ZM", "ZZ")


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
            title = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if title in wanted:
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


def _raw_text(var: tk.Variable) -> str:
    try:
        return str(var._tk.globalgetvar(var._name))  # type: ignore[attr-defined]
    except Exception:
        try:
            return str(var.get())
        except Exception:
            return ""


def _hide_order_field(panel: Any, name: str) -> ttk.LabelFrame | None:
    meta = getattr(panel, "_orders_meta", {}).get(name) or {}
    widget = meta.get("widget")
    if widget is None:
        return None
    row = getattr(widget, "master", None)
    group = getattr(row, "master", None)
    if row is not None:
        _hide(row)
    return group if isinstance(group, ttk.LabelFrame) else None


def _rename_groups(panel: Any) -> None:
    root = _module_tab(panel, "Zlecenia")
    if root is None:
        return
    mapping = {
        "definicje typów zleceń (zw/zn/zm/zz)": "Logika — typy i numeracja",
        "statusy i kolory": "Wygląd i logika — statusy",
        "czynności technologiczne": "Logika — czynności",
        "progi alertów (%)": "Logika — progi alertów",
    }
    for child in _all_descendants(root):
        if not isinstance(child, ttk.LabelFrame):
            continue
        try:
            old = str(child.cget("text") or "").strip().lower()
        except Exception:
            continue
        if old in mapping:
            child.configure(text=mapping[old])


def _type_editor(panel: Any) -> None:
    vars_map = getattr(panel, "_orders_vars", {})
    enabled_var = vars_map.get("enabled_types")
    prefixes_var = vars_map.get("prefixes")
    if enabled_var is None or prefixes_var is None:
        return
    group = _hide_order_field(panel, "enabled_types") or _hide_order_field(panel, "prefixes")
    _hide_order_field(panel, "prefixes")
    if group is None or getattr(group, "_wm_types_editor", False):
        return

    try:
        enabled = [str(x).upper() for x in (enabled_var.get() or [])]
    except Exception:
        enabled = list(_DEFAULT_CODES)
    try:
        prefixes = dict(prefixes_var.get() or {})
    except Exception:
        prefixes = {}
    codes = list(_DEFAULT_CODES)
    for code in list(prefixes.keys()) + enabled:
        code = str(code).strip().upper()
        if code and code not in codes:
            codes.append(code)

    box = ttk.Frame(group)
    box.pack(fill="x", padx=8, pady=(4, 8))
    ttk.Label(box, text="Typ", width=8).grid(row=0, column=0, sticky="w")
    ttk.Label(box, text="Aktywny", width=10).grid(row=0, column=1, sticky="w")
    ttk.Label(box, text="Prefiks numeru").grid(row=0, column=2, sticky="w")

    active_vars: dict[str, tk.BooleanVar] = {}
    prefix_vars: dict[str, tk.StringVar] = {}

    def _sync_enabled() -> None:
        values = [code for code in codes if active_vars[code].get()]
        enabled_var.set("\n".join(values))

    def _sync_prefixes(*_args: Any) -> None:
        lines = []
        for code in codes:
            value = str(prefix_vars[code].get() or "").strip()
            if value:
                lines.append(f"{code} = {value}")
        prefixes_var.set("\n".join(lines))

    for idx, code in enumerate(codes, start=1):
        ttk.Label(box, text=code).grid(row=idx, column=0, sticky="w", pady=2)
        active = tk.BooleanVar(master=box, value=code in enabled)
        active_vars[code] = active
        ttk.Checkbutton(box, variable=active, command=_sync_enabled).grid(row=idx, column=1, sticky="w", pady=2)
        prefix = tk.StringVar(master=box, value=str(prefixes.get(code) or f"{code}-"))
        prefix_vars[code] = prefix
        ttk.Entry(box, textvariable=prefix, width=16).grid(row=idx, column=2, sticky="w", pady=2)
        prefix.trace_add("write", _sync_prefixes)

    setattr(group, "_wm_types_editor", True)


def _status_editor(panel: Any) -> None:
    vars_map = getattr(panel, "_orders_vars", {})
    statuses_var = vars_map.get("statuses")
    colors_var = vars_map.get("colors")
    if statuses_var is None or colors_var is None:
        return
    group = _hide_order_field(panel, "statuses") or _hide_order_field(panel, "colors")
    _hide_order_field(panel, "colors")
    if group is None or getattr(group, "_wm_status_editor", False):
        return

    try:
        statuses_data = {str(k): [str(x) for x in v] for k, v in dict(statuses_var.get() or {}).items()}
    except Exception:
        statuses_data = {}
    try:
        colors_data = {str(k): str(v) for k, v in dict(colors_var.get() or {}).items()}
    except Exception:
        colors_data = {}

    codes = list(_DEFAULT_CODES)
    for code in statuses_data:
        if code not in codes:
            codes.append(code)
    for code in codes:
        statuses_data.setdefault(code, [])

    outer = ttk.Frame(group)
    outer.pack(fill="x", padx=8, pady=(4, 8))
    outer.columnconfigure(1, weight=1)

    ttk.Label(outer, text="Typ zlecenia:").grid(row=0, column=0, sticky="w", pady=(0, 5))
    code_var = tk.StringVar(master=outer, value=codes[0] if codes else "ZW")
    code_combo = ttk.Combobox(outer, textvariable=code_var, values=codes, state="readonly", width=10)
    code_combo.grid(row=0, column=1, sticky="w", pady=(0, 5))

    listbox = tk.Listbox(outer, height=7, exportselection=False)
    listbox.grid(row=1, column=0, columnspan=2, sticky="ew")

    editor = ttk.Frame(outer)
    editor.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
    editor.columnconfigure(0, weight=1)
    new_var = tk.StringVar(master=editor)
    ttk.Entry(editor, textvariable=new_var).grid(row=0, column=0, sticky="ew")

    color_row = ttk.Frame(outer)
    color_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    ttk.Label(color_row, text="Kolor wybranego statusu:").pack(side="left")
    color_sample = tk.Label(color_row, text="  podgląd  ", bd=1, relief="solid")
    color_sample.pack(side="left", padx=6)
    color_value = ttk.Label(color_row, text="—")
    color_value.pack(side="left", padx=(0, 6))

    def _sync_statuses() -> None:
        try:
            statuses_var.set(statuses_data)
        except Exception:
            lines = [f"{code}: {', '.join(values)}" for code, values in statuses_data.items()]
            statuses_var.set("\n".join(lines))

    def _sync_colors() -> None:
        colors_var.set("\n".join(f"{k} = {v}" for k, v in colors_data.items() if k and v))

    def _refresh_list(*_args: Any) -> None:
        listbox.delete(0, "end")
        for status in statuses_data.get(code_var.get(), []):
            listbox.insert("end", status)
        _refresh_color()

    def _selected_status() -> str:
        sel = listbox.curselection()
        return str(listbox.get(sel[0])) if sel else ""

    def _refresh_color(_event=None) -> None:
        status = _selected_status()
        value = colors_data.get(status, "") if status else ""
        color_value.configure(text=value or "domyślny")
        bg = value if value.startswith("#") else "#808080"
        try:
            color_sample.configure(bg=bg, fg="#ffffff")
        except Exception:
            color_sample.configure(bg="#808080", fg="#ffffff")

    def _add() -> None:
        value = str(new_var.get() or "").strip()
        if not value:
            return
        arr = statuses_data.setdefault(code_var.get(), [])
        if value.lower() not in {x.lower() for x in arr}:
            arr.append(value)
            _sync_statuses()
            _refresh_list()
            listbox.selection_set("end")
            _refresh_color()
        new_var.set("")

    def _delete() -> None:
        sel = listbox.curselection()
        if not sel:
            return
        arr = statuses_data.setdefault(code_var.get(), [])
        idx = int(sel[0])
        if 0 <= idx < len(arr):
            arr.pop(idx)
            _sync_statuses()
            _refresh_list()

    def _move(delta: int) -> None:
        sel = listbox.curselection()
        if not sel:
            return
        arr = statuses_data.setdefault(code_var.get(), [])
        idx = int(sel[0])
        target = idx + delta
        if target < 0 or target >= len(arr):
            return
        arr[idx], arr[target] = arr[target], arr[idx]
        _sync_statuses()
        _refresh_list()
        listbox.selection_set(target)

    def _choose_color() -> None:
        status = _selected_status()
        if not status:
            return
        initial = colors_data.get(status, "")
        if not initial.startswith("#"):
            initial = None
        picked = colorchooser.askcolor(color=initial, parent=outer)[1]
        if picked:
            colors_data[status] = picked
            _sync_colors()
            _refresh_color()

    def _default_color() -> None:
        status = _selected_status()
        if not status:
            return
        colors_data.pop(status, None)
        _sync_colors()
        _refresh_color()

    ttk.Button(editor, text="Dodaj", command=_add).grid(row=0, column=1, padx=(5, 0))
    ttk.Button(editor, text="Usuń", command=_delete).grid(row=0, column=2, padx=(5, 0))
    ttk.Button(editor, text="↑", width=3, command=lambda: _move(-1)).grid(row=0, column=3, padx=(5, 0))
    ttk.Button(editor, text="↓", width=3, command=lambda: _move(1)).grid(row=0, column=4, padx=(2, 0))
    ttk.Button(color_row, text="Wybierz…", command=_choose_color).pack(side="left", padx=3)
    ttk.Button(color_row, text="Domyślny", command=_default_color).pack(side="left", padx=3)

    code_combo.bind("<<ComboboxSelected>>", _refresh_list)
    listbox.bind("<<ListboxSelect>>", _refresh_color)
    _refresh_list()
    setattr(group, "_wm_status_editor", True)


def _simple_list_editor(panel: Any, name: str) -> None:
    vars_map = getattr(panel, "_orders_vars", {})
    source_var = vars_map.get(name)
    if source_var is None:
        return
    group = _hide_order_field(panel, name)
    if group is None or getattr(group, f"_wm_{name}_editor", False):
        return
    try:
        values = [str(x).strip() for x in (source_var.get() or []) if str(x).strip()]
    except Exception:
        values = []

    box = ttk.Frame(group)
    box.pack(fill="x", padx=8, pady=(4, 8))
    box.columnconfigure(0, weight=1)
    listbox = tk.Listbox(box, height=6, exportselection=False)
    listbox.grid(row=0, column=0, columnspan=5, sticky="ew")
    for value in values:
        listbox.insert("end", value)
    entry_var = tk.StringVar(master=box)
    ttk.Entry(box, textvariable=entry_var).grid(row=1, column=0, sticky="ew", pady=(5, 0))

    def _sync() -> None:
        current = [str(listbox.get(i)).strip() for i in range(listbox.size())]
        source_var.set("\n".join(x for x in current if x))

    def _add() -> None:
        value = str(entry_var.get() or "").strip()
        if value and value.lower() not in {str(listbox.get(i)).lower() for i in range(listbox.size())}:
            listbox.insert("end", value)
            _sync()
        entry_var.set("")

    def _delete() -> None:
        sel = listbox.curselection()
        if sel:
            listbox.delete(sel[0])
            _sync()

    def _move(delta: int) -> None:
        sel = listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        target = idx + delta
        if target < 0 or target >= listbox.size():
            return
        value = listbox.get(idx)
        listbox.delete(idx)
        listbox.insert(target, value)
        listbox.selection_set(target)
        _sync()

    ttk.Button(box, text="Dodaj", command=_add).grid(row=1, column=1, padx=(5, 0), pady=(5, 0))
    ttk.Button(box, text="Usuń", command=_delete).grid(row=1, column=2, padx=(5, 0), pady=(5, 0))
    ttk.Button(box, text="↑", width=3, command=lambda: _move(-1)).grid(row=1, column=3, padx=(5, 0), pady=(5, 0))
    ttk.Button(box, text="↓", width=3, command=lambda: _move(1)).grid(row=1, column=4, padx=(2, 0), pady=(5, 0))
    setattr(group, f"_wm_{name}_editor", True)


def _alerts_editor(panel: Any) -> None:
    vars_map = getattr(panel, "_orders_vars", {})
    source_var = vars_map.get("alerts")
    if source_var is None:
        return
    group = _hide_order_field(panel, "alerts")
    if group is None or getattr(group, "_wm_alerts_editor", False):
        return
    try:
        data = dict(source_var.get() or {})
    except Exception:
        data = {}
    codes = list(_DEFAULT_CODES)
    for code in data:
        code = str(code).upper()
        if code not in codes:
            codes.append(code)

    box = ttk.Frame(group)
    box.pack(fill="x", padx=8, pady=(4, 8))
    vars_by_code: dict[str, tk.DoubleVar] = {}

    def _sync(*_args: Any) -> None:
        lines = []
        for code in codes:
            try:
                value = max(0.0, min(100.0, float(vars_by_code[code].get())))
            except Exception:
                value = 50.0
            lines.append(f"{code} = {value:g}")
        source_var.set("\n".join(lines))

    for idx, code in enumerate(codes):
        ttk.Label(box, text=code, width=8).grid(row=idx, column=0, sticky="w", pady=2)
        try:
            initial = float(data.get(code, 50))
        except Exception:
            initial = 50.0
        var = tk.DoubleVar(master=box, value=initial)
        vars_by_code[code] = var
        ttk.Spinbox(box, from_=0, to=100, increment=5, width=8, textvariable=var).grid(row=idx, column=1, sticky="w", pady=2)
        ttk.Label(box, text="%").grid(row=idx, column=2, sticky="w", padx=(3, 0))
        var.trace_add("write", _sync)
    setattr(group, "_wm_alerts_editor", True)


def _move_technical_to_advanced(panel: Any) -> None:
    root = _module_tab(panel, "Zlecenia")
    advanced = getattr(panel, "_advanced_container", None)
    general = _module_tab(panel, "Główne")
    if root is None or advanced is None:
        return

    links_var = getattr(panel, "_orders_vars", {}).get("links")
    defaults_var = getattr(panel, "_orders_vars", {}).get("defaults")
    links_group = _label_frame(root, "Powiązania modułowe")
    defaults_group = _label_frame(root, "Domyślne wartości")
    if links_group is not None:
        _hide(links_group)
    if defaults_group is not None:
        _hide(defaults_group)

    if general is not None and links_var is not None and not getattr(general, "_wm_orders_links_info", False):
        info = ttk.LabelFrame(general, text="Zlecenia — powiązania z modułami")
        info.pack(fill="x", padx=10, pady=6)
        try:
            links = dict(links_var.get() or {})
        except Exception:
            links = {}
        text = "\n".join(f"{key} → {value}" for key, value in links.items()) or "Brak zdefiniowanych powiązań."
        ttk.Label(info, text=text, wraplength=900, justify="left").pack(anchor="w", padx=8, pady=8)
        ttk.Label(info, text="To zależności między modułami, dlatego są pokazane w Moduły → Główne. Edycja techniczna jest w Zaawansowane.", wraplength=900).pack(anchor="w", padx=8, pady=(0, 8))
        setattr(general, "_wm_orders_links_info", True)

    if getattr(advanced, "_wm_orders_technical", False):
        return
    box = ttk.LabelFrame(advanced, text="Zlecenia — ustawienia techniczne")
    box.pack(fill="x", padx=8, pady=8)

    def _dict_editor(label: str, var: tk.Variable | None, row: int) -> None:
        ttk.Label(box, text=label).grid(row=row, column=0, sticky="nw", padx=8, pady=5)
        text = tk.Text(box, height=4, width=70, wrap="word")
        text.grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        if var is not None:
            try:
                data = dict(var.get() or {})
                initial = "\n".join(f"{k} = {v}" for k, v in data.items())
            except Exception:
                initial = _raw_text(var)
            text.insert("1.0", initial)
            def _sync(_event=None, target=var, widget=text):
                try:
                    target.set(widget.get("1.0", "end").strip())
                except Exception:
                    pass
            text.bind("<KeyRelease>", _sync)

    box.columnconfigure(1, weight=1)
    _dict_editor("Powiązania modułowe:", links_var, 0)
    _dict_editor("Domyślne wartości:", defaults_var, 1)
    ttk.Label(box, text="Pola techniczne. Zwykle nie wymagają ręcznej zmiany.").grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
    setattr(advanced, "_wm_orders_technical", True)


def _decorate(panel: Any) -> None:
    for action in (
        _rename_groups,
        _type_editor,
        _status_editor,
        lambda p: _simple_list_editor(p, "tasks"),
        _alerts_editor,
        _move_technical_to_advanced,
    ):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_orders_runtime(settings_panel_cls: type) -> None:
    if getattr(settings_panel_cls, "_wm_settings_orders_runtime", False):
        return
    original = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original):
        return

    def _build_ui_with_orders(self, *args: Any, **kwargs: Any):
        result = original(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_orders
    settings_panel_cls._wm_settings_orders_runtime = True
