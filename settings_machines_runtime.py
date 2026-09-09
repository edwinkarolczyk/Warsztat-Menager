# version: 1.0
# Moduł: settings_machines_runtime
# UI-only: porządkowanie Ustawienia → Moduły → Maszyny bez zmiany logiki Maszyn.

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any


_MAP_LABELS = {
    "id": "Numer",
    "typ": "Typ",
    "nazwa": "Nazwa",
}

_BG_FIT_LABELS = {
    "contain": "Dopasuj cały obraz",
    "cover": "Wypełnij obszar",
    "stretch": "Rozciągnij",
    "none": "Oryginalny rozmiar",
}


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
            if str(nb.tab(tab_id, "text") or "").strip().lower() != wanted:
                continue
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


def _hide_widget(widget: tk.Misc) -> None:
    try:
        info = widget.grid_info()
        if info:
            widget.grid_remove()
            return
    except Exception:
        pass
    try:
        info = widget.pack_info()
        if info:
            widget.pack_forget()
            return
    except Exception:
        pass


def _variable_from_widget(widget: tk.Misc, cls: type[tk.Variable] = tk.StringVar):
    try:
        name = str(widget.cget("textvariable") or "").strip()
    except Exception:
        return None
    if not name:
        return None
    try:
        return cls(master=widget, name=name)
    except Exception:
        return None


def _rename_machine_groups(panel: Any) -> None:
    root = _module_tab(panel, "Maszyny")
    if root is None:
        return

    mapping = {
        "widok i siatka": "Wygląd — plan hali",
        "zaznaczanie": "Logika — zaznaczanie i pozycjonowanie",
        "pomieszczenia i ściany (ustawienia)": "Logika — pomieszczenia i ściany",
        "tło hali (renderer)": "Wygląd — tło hali",
        "mapa hali – etykieta i rozmiar kropki": "Wygląd — znaczniki maszyn",
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

    # Źródło danych jest informacją techniczną, nie ustawieniem modułu.
    source = _label_frame(root, "Źródło danych (jedno źródło prawdy)")
    if source is not None:
        _hide_widget(source)

    # Drugi techniczny opis ścieżki dokładany przez handler Maszyn również ukrywamy.
    for child in list(_all_descendants(root)):
        if not isinstance(child, ttk.Label):
            continue
        try:
            text = str(child.cget("text") or "")
        except Exception:
            continue
        if "Pliki danych są ustalane relatywnie względem Folderu WM" in text:
            _hide_widget(child.master)


def _simplify_machine_background(panel: Any) -> None:
    root = _module_tab(panel, "Maszyny")
    if root is None:
        return
    box = _label_frame(root, "Wygląd — tło hali", "Tło hali (renderer)")
    if box is None or getattr(box, "_wm_machine_bg_simplified", False):
        return

    bg_entry = None
    old_save = None
    technical_rows: set[int] = set()

    for child in box.winfo_children():
        if isinstance(child, ttk.Label):
            try:
                text = str(child.cget("text") or "").strip().lower()
            except Exception:
                text = ""
            if text in {
                "wymagana szerokość (px):",
                "wymagana wysokość (px):",
                "dozwolone rozszerzenia (csv):",
            }:
                try:
                    technical_rows.add(int(child.grid_info().get("row", -1)))
                except Exception:
                    pass

    for child in box.winfo_children():
        try:
            info = child.grid_info()
            row = int(info.get("row", -1)) if info else -1
        except Exception:
            row = -1
        if row in technical_rows:
            if isinstance(child, ttk.Button):
                try:
                    if "zapisz" in str(child.cget("text") or "").lower():
                        old_save = child
                except Exception:
                    pass
            _hide_widget(child)
            continue
        if row == 0 and isinstance(child, ttk.Entry):
            bg_entry = child

    # Stary przycisk zapisywał także techniczne limity wymiarów/rozszerzeń.
    # W normalnych Ustawieniach Maszyn zapisujemy tylko wybrany plik tła.
    if old_save is not None:
        _hide_widget(old_save)

    bg_var = _variable_from_widget(bg_entry) if bg_entry is not None else None
    if bg_var is not None:
        cfg = getattr(panel, "cfg", None)

        def _save_background() -> None:
            if cfg is None:
                return
            path = str(bg_var.get() or "").strip()
            try:
                cfg.set("machines.background_image", path)
                saver = getattr(cfg, "save_all", None) or getattr(cfg, "save", None)
                if callable(saver):
                    saver()
                messagebox.showinfo(
                    "Maszyny — tło hali",
                    "Zapisano tło hali.",
                    parent=box.winfo_toplevel(),
                )
            except Exception as exc:
                messagebox.showerror(
                    "Maszyny — tło hali",
                    f"Nie udało się zapisać tła hali:\n{exc}",
                    parent=box.winfo_toplevel(),
                )

        ttk.Button(box, text="Zapisz tło", command=_save_background).grid(
            row=0, column=3, sticky="w", padx=(4, 8), pady=2
        )

    ttk.Label(
        box,
        text="Wybierz obraz planu hali. Parametry techniczne obrazu są w Zaawansowanych.",
    ).grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(4, 6))

    setattr(box, "_wm_machine_bg_simplified", True)


def _friendly_background_fit(panel: Any) -> None:
    root = _module_tab(panel, "Maszyny")
    if root is None:
        return

    frame = None
    for label in _all_descendants(root):
        if not isinstance(label, ttk.Label):
            continue
        try:
            if str(label.cget("text") or "").strip().rstrip(":") == "Dopasowanie tła":
                frame = label.master
                break
        except Exception:
            continue
    if frame is None or getattr(frame, "_wm_bg_fit_friendly", False):
        return

    combo = next((x for x in _all_descendants(frame) if isinstance(x, ttk.Combobox)), None)
    source_var = getattr(panel, "vars", {}).get("hall.background_fit")
    if combo is None or source_var is None:
        return

    display = tk.StringVar(master=frame)

    def _from_source(*_args: Any) -> None:
        value = str(source_var.get() or "contain")
        display.set(_BG_FIT_LABELS.get(value, value))

    def _from_display(_event=None) -> None:
        chosen = str(display.get() or "")
        for value, label in _BG_FIT_LABELS.items():
            if label == chosen:
                source_var.set(value)
                return

    try:
        combo.unbind("<<ComboboxSelected>>")
    except Exception:
        pass
    combo.configure(
        textvariable=display,
        values=list(_BG_FIT_LABELS.values()),
        state="readonly",
    )
    combo.bind("<<ComboboxSelected>>", _from_display)
    source_var.trace_add("write", _from_source)
    _from_source()
    setattr(frame, "_wm_bg_fit_friendly", True)


def _friendly_machine_map(panel: Any) -> None:
    root = _module_tab(panel, "Maszyny")
    if root is None:
        return
    box = _label_frame(root, "Wygląd — znaczniki maszyn", "Mapa hali – etykieta i rozmiar kropki")
    if box is None or getattr(box, "_wm_machine_map_friendly", False):
        return

    combo = next((x for x in _all_descendants(box) if isinstance(x, ttk.Combobox)), None)
    if combo is not None:
        source = _variable_from_widget(combo)
        if source is not None:
            display = tk.StringVar(master=box)

            def _from_source(*_args: Any) -> None:
                value = str(source.get() or "id")
                display.set(_MAP_LABELS.get(value, value))

            def _from_display(_event=None) -> None:
                chosen = str(display.get() or "")
                for value, label in _MAP_LABELS.items():
                    if label == chosen:
                        source.set(value)
                        return

            try:
                combo.unbind("<<ComboboxSelected>>")
            except Exception:
                pass
            combo.configure(
                textvariable=display,
                values=list(_MAP_LABELS.values()),
                state="readonly",
            )
            combo.bind("<<ComboboxSelected>>", _from_display)
            source.trace_add("write", _from_source)
            _from_source()

    for label in box.winfo_children():
        if not isinstance(label, ttk.Label):
            continue
        try:
            text = str(label.cget("text") or "")
        except Exception:
            continue
        if text == "Etykieta w kropce:":
            label.configure(text="Tekst na znaczniku:")
        elif text == "Promień kropki (px):":
            label.configure(text="Promień znacznika (px):")

    setattr(box, "_wm_machine_map_friendly", True)


def _room_types_editor(panel: Any) -> None:
    root = _module_tab(panel, "Maszyny")
    if root is None:
        return
    source_var = getattr(panel, "vars", {}).get("hall.room_types")
    if source_var is None:
        return

    frame = None
    for label in _all_descendants(root):
        if not isinstance(label, ttk.Label):
            continue
        try:
            if str(label.cget("text") or "").strip().rstrip(":") == "Typy pomieszczeń":
                frame = label.master
                break
        except Exception:
            continue
    if frame is None or getattr(frame, "_wm_room_types_editor", False):
        return

    text_widget = next((x for x in frame.winfo_children() if isinstance(x, tk.Text)), None)
    if text_widget is None:
        return
    try:
        grid = text_widget.grid_info()
    except Exception:
        return
    _hide_widget(text_widget)

    editor = ttk.Frame(frame)
    editor.grid(
        row=grid.get("row", 0),
        column=grid.get("column", 1),
        sticky="ew",
        padx=grid.get("padx", 5),
        pady=grid.get("pady", 5),
    )
    editor.columnconfigure(0, weight=1)

    listbox = tk.Listbox(editor, height=5, exportselection=False)
    listbox.grid(row=0, column=0, columnspan=4, sticky="ew")

    try:
        current = source_var.get()
    except Exception:
        current = []
    if isinstance(current, str):
        items = [x.strip() for x in current.splitlines() if x.strip()]
    else:
        items = [str(x).strip() for x in (current or []) if str(x).strip()]
    for item in items:
        listbox.insert("end", item)

    new_var = tk.StringVar(master=editor)
    ttk.Entry(editor, textvariable=new_var).grid(row=1, column=0, sticky="ew", pady=(5, 0))

    def _sync() -> None:
        values = [str(listbox.get(i)).strip() for i in range(listbox.size())]
        source_var.set("\n".join(x for x in values if x))

    def _add() -> None:
        value = str(new_var.get() or "").strip()
        if not value:
            return
        existing = {str(listbox.get(i)).strip().lower() for i in range(listbox.size())}
        if value.lower() not in existing:
            listbox.insert("end", value)
            _sync()
        new_var.set("")

    def _delete() -> None:
        sel = listbox.curselection()
        if not sel:
            return
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

    ttk.Button(editor, text="Dodaj", command=_add).grid(row=1, column=1, padx=(5, 0), pady=(5, 0))
    ttk.Button(editor, text="Usuń", command=_delete).grid(row=1, column=2, padx=(5, 0), pady=(5, 0))

    arrows = ttk.Frame(editor)
    arrows.grid(row=1, column=3, padx=(5, 0), pady=(5, 0))
    ttk.Button(arrows, text="↑", width=3, command=lambda: _move(-1)).pack(side="left")
    ttk.Button(arrows, text="↓", width=3, command=lambda: _move(1)).pack(side="left", padx=(2, 0))

    new_var.trace_add("write", lambda *_: None)
    setattr(frame, "_wm_room_types_editor", True)


def _shared_review_setting(panel: Any) -> None:
    general = _module_tab(panel, "Główne")
    dysp = _module_tab(panel, "Dyspozycje")
    machines = _module_tab(panel, "Maszyny")
    if general is None or dysp is None:
        return
    if getattr(general, "_wm_shared_review_setting", False):
        return

    automation = _label_frame(
        dysp,
        "Logika — automatyzacja przeglądów maszyn",
        "Automatyzacja przeglądów maszyn",
    )
    source_spin = None
    if automation is not None:
        source_spin = next((x for x in _all_descendants(automation) if isinstance(x, ttk.Spinbox)), None)
    source_var = _variable_from_widget(source_spin, tk.IntVar) if source_spin is not None else None

    if source_var is None:
        try:
            value = int(getattr(panel, "cfg").get("dyspozycje.machine_cycle.days_before", 7))
        except Exception:
            value = 7
        source_var = tk.IntVar(master=general, value=value)

    if "dyspozycje.machine_cycle.days_before" not in getattr(panel, "vars", {}):
        try:
            panel._register_manual_var(
                "dyspozycje.machine_cycle.days_before",
                source_var,
                default=7,
                option_type="int",
            )
        except Exception:
            pass

    if automation is not None:
        _hide_widget(automation)

    box = ttk.LabelFrame(general, text="Maszyny ↔ Dyspozycje — przeglądy")
    box.pack(fill="x", padx=10, pady=(8, 6))
    box.columnconfigure(1, weight=1)

    ttk.Label(
        box,
        text="Dodaj automatyczną Dyspozycję [dni przed terminem]:",
    ).grid(row=0, column=0, sticky="w", padx=8, pady=6)
    ttk.Spinbox(
        box,
        from_=0,
        to=365,
        width=8,
        textvariable=source_var,
    ).grid(row=0, column=1, sticky="w", padx=8, pady=6)
    ttk.Label(
        box,
        text="To ustawienie łączy dwa moduły, dlatego jest tutaj. 0 = utwórz Dyspozycję dopiero w dniu przeglądu.",
        wraplength=900,
    ).grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

    if machines is not None and _label_frame(machines, "Przeglądy") is None:
        review_box = ttk.LabelFrame(machines, text="Przeglądy")
        review_box.pack(fill="x", padx=8, pady=8)
        summary_var = tk.StringVar(master=review_box)

        def _refresh(*_args: Any) -> None:
            try:
                days = int(source_var.get())
            except Exception:
                days = 7
            if days == 0:
                text = "Automatyczna Dyspozycja: w dniu przeglądu."
            elif days == 1:
                text = "Automatyczna Dyspozycja: 1 dzień przed przeglądem."
            else:
                text = f"Automatyczna Dyspozycja: {days} dni przed przeglądem."
            summary_var.set(text)

        ttk.Label(review_box, textvariable=summary_var).pack(anchor="w", padx=8, pady=(8, 3))
        ttk.Label(
            review_box,
            text="Miesiące i zakres przeglądu ustala się w karcie konkretnej maszyny. Ustawienie wspólne z Dyspozycjami znajduje się w Moduły → Główne.",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 8))
        source_var.trace_add("write", _refresh)
        _refresh()

    setattr(general, "_wm_shared_review_setting", True)


def _advanced_machine_background(panel: Any) -> None:
    parent = getattr(panel, "_advanced_container", None)
    if parent is None or getattr(parent, "_wm_machine_bg_advanced", False):
        return

    cfg = getattr(panel, "cfg", None)
    if cfg is None:
        return

    box = ttk.LabelFrame(parent, text="Maszyny — walidacja tła hali (techniczne)")
    box.pack(fill="x", padx=8, pady=8)
    box.columnconfigure(1, weight=1)

    try:
        width_value = int(cfg.get("machines.bg_required_w", 1920) or 0)
    except Exception:
        width_value = 1920
    try:
        height_value = int(cfg.get("machines.bg_required_h", 1080) or 0)
    except Exception:
        height_value = 1080
    ext_value = str(cfg.get("machines.bg_allowed_ext", ".jpg,.png") or ".jpg,.png")

    width_var = tk.IntVar(master=box, value=width_value)
    height_var = tk.IntVar(master=box, value=height_value)
    ext_var = tk.StringVar(master=box, value=ext_value)

    ttk.Label(box, text="Wymagana szerokość:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
    ttk.Spinbox(box, from_=0, to=10000, textvariable=width_var, width=8).grid(row=0, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(box, text="px").grid(row=0, column=2, sticky="w")

    ttk.Label(box, text="Wymagana wysokość:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
    ttk.Spinbox(box, from_=0, to=10000, textvariable=height_var, width=8).grid(row=1, column=1, sticky="w", padx=8, pady=4)
    ttk.Label(box, text="px").grid(row=1, column=2, sticky="w")

    ttk.Label(box, text="Dozwolone rozszerzenia:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
    ttk.Entry(box, textvariable=ext_var, width=32).grid(row=2, column=1, sticky="w", padx=8, pady=4)

    ttk.Label(
        box,
        text="0 oznacza brak wymuszania danego wymiaru. To ustawienia techniczne i zwykle nie trzeba ich zmieniać.",
        wraplength=900,
    ).grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 8))

    for key, var, default, typ in (
        ("machines.bg_required_w", width_var, 1920, "int"),
        ("machines.bg_required_h", height_var, 1080, "int"),
        ("machines.bg_allowed_ext", ext_var, ".jpg,.png", "string"),
    ):
        if key in getattr(panel, "vars", {}):
            continue
        try:
            panel._register_manual_var(key, var, default=default, option_type=typ)
        except Exception:
            pass

    setattr(parent, "_wm_machine_bg_advanced", True)


def _decorate(panel: Any) -> None:
    for action in (
        _rename_machine_groups,
        _simplify_machine_background,
        _friendly_background_fit,
        _friendly_machine_map,
        _room_types_editor,
        _shared_review_setting,
        _advanced_machine_background,
    ):
        try:
            action(panel)
        except Exception:
            pass


def install_settings_machines_runtime(settings_panel_cls: type) -> None:
    """Porządkuj Moduły → Maszyny po zbudowaniu podstawowych Ustawień."""
    if getattr(settings_panel_cls, "_wm_settings_machines_runtime", False):
        return

    original_build_ui = getattr(settings_panel_cls, "_build_ui", None)
    if not callable(original_build_ui):
        return

    def _build_ui_with_machines(self, *args: Any, **kwargs: Any):
        result = original_build_ui(self, *args, **kwargs)
        _decorate(self)
        return result

    settings_panel_cls._build_ui = _build_ui_with_machines
    settings_panel_cls._wm_settings_machines_runtime = True
