# version: 1.0
"""Wspólny kreator Dyspozycji z dynamicznymi listami obiektów."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from dyspozycje_sources import (
    load_magazyn_choices,
    load_machine_choices,
    load_tool_choices,
    load_zlecenie_wykonania_choices,
)
from dyspozycje_store import (
    add_dyspozycja,
    close_dyspozycja,
    make_dyspozycja,
    update_dyspozycja,
)

try:
    from profiles_store import load_profiles_users, resolve_profiles_path
except Exception:  # pragma: no cover
    load_profiles_users = None  # type: ignore
    resolve_profiles_path = None  # type: ignore


def _try_open_tool_editor(master: tk.Widget, object_id: str) -> None:
    """Otwiera istniejący edytor narzędzia dla obiektu z dyspozycji."""
    tool_id = str(object_id or "").strip()
    if not tool_id:
        messagebox.showwarning("Dyspozycje", "Brak numeru narzędzia.", parent=master)
        return

    try:
        from gui_narzedzia import open_tool_editor_by_id

        opened = open_tool_editor_by_id(master.winfo_toplevel(), tool_id)
        if not opened:
            messagebox.showwarning(
                "Dyspozycje",
                f"Nie znaleziono narzędzia: {tool_id}",
                parent=master,
            )
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się otworzyć edytora narzędzia:\n{exc}",
            parent=master,
        )


def _load_user_logins() -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if callable(load_profiles_users) and callable(resolve_profiles_path):
        try:
            rows = load_profiles_users(path=resolve_profiles_path(None))
        except Exception:
            rows = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            login = str(row.get("login") or "").strip()
            if not login:
                continue
            key = login.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(login)
    out.sort(key=str.lower)
    return out


def _options_for_type(typ: str) -> tuple[str, str, list[tuple[str, str]]]:
    key = str(typ or "").strip().lower()
    if key == "narzedzie":
        return ("narzedzia", "Narzędzie:", load_tool_choices())
    if key == "maszyna":
        return ("maszyny", "Maszyna:", load_machine_choices())
    if key == "magazyn":
        return ("magazyn", "Pozycja magazynowa:", load_magazyn_choices())
    if key == "zlecenie_wykonania":
        return ("zlecenia", "Zlecenie wykonania:", load_zlecenie_wykonania_choices())
    return ("", "Obiekt:", [])


def _try_open_machine_usage(
    master: tk.Widget, object_id: str, object_label: str = ""
) -> None:
    """Otwiera istniejący moduł maszyn z kontekstem wybranej maszyny."""
    machine_id = str(object_id or "").strip()
    label = str(object_label or "").strip()
    if not machine_id and not label:
        messagebox.showwarning("Dyspozycje", "Brak wybranej maszyny.", parent=master)
        return

    try:
        from gui_maszyny import open_machine_usage

        open_machine_usage(master.winfo_toplevel(), machine_id, label=label)
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się otworzyć użytkowania maszyny:\n{exc}",
            parent=master,
        )


def open_dyspozycje_creator(
    master: tk.Widget | None = None,
    *,
    autor: str = "",
    context: dict[str, Any] | None = None,
) -> tk.Toplevel:
    ctx = dict(context or {})
    edit_mode = bool(ctx.get("edit_mode"))
    existing_id = str(ctx.get("id") or "").strip()
    root = master.winfo_toplevel() if master else None
    win = tk.Toplevel(root)
    win.title("Kreator – Edytuj Dyspozycję" if edit_mode else "Kreator – Dodaj Dyspozycję")
    win.geometry("1200x800")
    win.resizable(True, True)
    try:
        win.state("zoomed")
    except Exception:
        win.attributes("-zoomed", True)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(9, weight=1)

    ttk.Label(
        frame,
        text="Edycja Dyspozycji" if edit_mode else "Nowa Dyspozycja",
        style="WM.H1.TLabel",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

    ttk.Label(frame, text="Typ Dyspozycji:").grid(row=1, column=0, sticky="w", pady=4)
    var_type = tk.StringVar(value=str(ctx.get("typ_dyspozycji") or "narzedzie"))
    cb_type = ttk.Combobox(
        frame,
        textvariable=var_type,
        values=["narzedzie", "maszyna", "magazyn", "zlecenie_wykonania"],
        state="readonly",
        width=24,
    )
    cb_type.grid(row=1, column=1, sticky="w", pady=4)

    var_object_label = tk.StringVar(value="Obiekt:")
    lbl_object = ttk.Label(frame, textvariable=var_object_label)
    lbl_object.grid(row=3, column=0, sticky="w", pady=4)

    var_object_display = tk.StringVar()
    cb_object = ttk.Combobox(
        frame,
        textvariable=var_object_display,
        values=[],
        state="readonly",
        width=48,
    )
    cb_object.grid(row=3, column=1, sticky="ew", pady=4)

    var_object_search = tk.StringVar()
    ent_object_search = ttk.Entry(frame, textvariable=var_object_search)
    ent_object_search.grid(row=2, column=1, sticky="ew", pady=4)
    ent_object_search.grid_remove()

    ttk.Label(frame, text="Opis:").grid(row=4, column=0, sticky="nw", pady=4)
    txt_desc = tk.Text(frame, height=6, width=54)
    txt_desc.grid(row=4, column=1, sticky="ew", pady=4)
    if ctx.get("opis"):
        txt_desc.insert("1.0", str(ctx.get("opis")))

    ttk.Label(frame, text="Priorytet:").grid(row=5, column=0, sticky="w", pady=4)
    var_priority = tk.StringVar(value=str(ctx.get("priorytet") or "normalny"))
    cb_priority = ttk.Combobox(
        frame,
        textvariable=var_priority,
        values=["niski", "normalny", "wysoki", "krytyczny"],
        state="readonly",
        width=24,
    )
    cb_priority.grid(row=5, column=1, sticky="w", pady=4)

    ttk.Label(frame, text="Termin (YYYY-MM-DD):").grid(row=6, column=0, sticky="w", pady=4)
    var_deadline = tk.StringVar(value=str(ctx.get("termin") or ""))
    ent_deadline = ttk.Entry(frame, textvariable=var_deadline, width=24)
    ent_deadline.grid(row=6, column=1, sticky="w", pady=4)

    var_all = tk.BooleanVar(value=bool(ctx.get("dla_wszystkich", False)))
    chk_all = ttk.Checkbutton(frame, text="Dyspozycja dla wszystkich", variable=var_all)
    chk_all.grid(row=7, column=1, sticky="w", pady=(8, 4))

    ttk.Label(frame, text="Przypisane do:").grid(row=8, column=0, sticky="w", pady=4)
    var_assigned = tk.StringVar(value=str(ctx.get("przypisane_do") or ""))
    cb_assigned = ttk.Combobox(
        frame,
        textvariable=var_assigned,
        values=_load_user_logins(),
        state="normal",
        width=24,
    )
    cb_assigned.grid(row=8, column=1, sticky="w", pady=4)

    object_panel = ttk.LabelFrame(frame, text="Powiązany obiekt dyspozycji")
    object_panel.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
    object_panel.columnconfigure(0, weight=1)

    var_object_panel_info = tk.StringVar(
        value="Wybierz typ i obiekt dyspozycji, aby zobaczyć powiązany element."
    )
    lbl_object_panel_info = ttk.Label(
        object_panel,
        textvariable=var_object_panel_info,
        wraplength=900,
        justify="left",
    )
    lbl_object_panel_info.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

    object_panel_buttons = ttk.Frame(object_panel)
    object_panel_buttons.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

    options_map: dict[str, str] = {}
    all_labels: list[str] = []
    source_module = {"value": ""}

    btn_open_tool = ttk.Button(
        object_panel_buttons,
        text="Otwórz edytor narzędzia",
        command=lambda: _try_open_tool_editor(
            win,
            options_map.get(var_object_display.get().strip(), ""),
        ),
    )
    btn_open_machine = ttk.Button(
        object_panel_buttons,
        text="Otwórz użytkowanie maszyny",
        command=lambda: _try_open_machine_usage(
            win,
            options_map.get(var_object_display.get().strip(), ""),
            var_object_display.get().strip(),
        ),
    )

    if not edit_mode:
        object_panel.grid_remove()

    def _refresh_object_panel(*_args) -> None:
        if not edit_mode:
            return
        typ = var_type.get().strip().lower()
        selected_label = var_object_display.get().strip()
        object_id = options_map.get(selected_label, "").strip()

        for child in object_panel_buttons.winfo_children():
            child.pack_forget()

        if typ == "narzedzie":
            var_object_panel_info.set(
                "Narzędzie powiązane z dyspozycją: "
                f"{selected_label or object_id or 'brak wyboru'}"
            )
            btn_open_tool.pack(side="left")
        elif typ == "maszyna":
            var_object_panel_info.set(
                "Maszyna powiązana z dyspozycją: "
                f"{selected_label or object_id or 'brak wyboru'}"
            )
            btn_open_machine.pack(side="left")
        else:
            var_object_panel_info.set(
                "Dla tego typu dyspozycji nie ma jeszcze edytora "
                "kontekstowego w dolnym panelu."
            )

    def _toggle_assigned(*_args) -> None:
        if var_all.get():
            try:
                cb_assigned.configure(state="disabled")
            except Exception:
                pass
        else:
            try:
                cb_assigned.configure(state="normal")
            except Exception:
                pass

    def _refresh_object_choices(*_args) -> None:
        nonlocal options_map, all_labels
        source_key, label_text, options = _options_for_type(var_type.get())
        source_module["value"] = source_key
        var_object_label.set(label_text)
        options_map = {label: object_id for object_id, label in options}
        all_labels = [label for _object_id, label in options]
        labels = list(all_labels)
        cb_object.configure(values=labels)
        var_object_search.set("")
        if source_key in {"narzedzia", "maszyny"}:
            ent_object_search.grid()
        else:
            ent_object_search.grid_remove()

        ctx_object_id = str(ctx.get("obiekt_id") or "").strip()
        picked = ""
        if ctx_object_id:
            for object_id, label in options:
                if str(object_id) == ctx_object_id:
                    picked = label
                    break
        if not picked and labels:
            picked = labels[0]
        var_object_display.set(picked)
        _refresh_object_panel()

    _toggle_assigned()
    var_all.trace_add("write", _toggle_assigned)
    cb_type.bind("<<ComboboxSelected>>", _refresh_object_choices)
    _refresh_object_choices()

    def _filter_objects(*_args) -> None:
        if source_module["value"] not in {"narzedzia", "maszyny"}:
            return
        query = var_object_search.get().strip().lower()
        if not query:
            filtered = list(all_labels)
        else:
            filtered = [
                label
                for label in all_labels
                if query in label.lower()
            ]
        cb_object.configure(values=filtered)
        if filtered:
            current = var_object_display.get().strip()
            if current not in filtered:
                var_object_display.set(filtered[0])
        else:
            var_object_display.set("")
        _refresh_object_panel()

    var_object_search.trace_add("write", _filter_objects)
    cb_object.bind("<<ComboboxSelected>>", _refresh_object_panel)
    _refresh_object_panel()

    btns = ttk.Frame(win, padding=(12, 0, 12, 12))
    btns.pack(fill="x")

    def _event_updated() -> None:
        try:
            win.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            pass

    def _actor_login() -> str:
        for candidate in (
            autor,
            ctx.get("autor"),
            getattr(root, "active_login", ""),
            getattr(root, "_wm_login", ""),
            getattr(root, "login", ""),
        ):
            text = str(candidate or "").strip()
            if text:
                return text
        return ""

    def _close_current() -> None:
        if not edit_mode or not existing_id:
            return
        if not messagebox.askyesno(
            "Dyspozycje",
            "Zamknąć tę dyspozycję?",
            parent=win,
        ):
            return
        changed = close_dyspozycja(existing_id, closed_by=_actor_login())
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Nie udało się zamknąć Dyspozycji.",
                parent=win,
            )
            return
        _event_updated()
        messagebox.showinfo("Dyspozycje", "Dyspozycja została zamknięta.", parent=win)
        win.destroy()

    def _save() -> None:
        selected_label = var_object_display.get().strip()
        object_id = options_map.get(selected_label, "").strip()
        if not object_id:
            messagebox.showwarning(
                "Dyspozycje",
                "Wybierz obiekt z listy.",
                parent=win,
            )
            return

        title = str(ctx.get("tytul") or "").strip() or selected_label or var_type.get().strip()
        payload = {
            "typ_dyspozycji": var_type.get().strip(),
            "tytul": title,
            "opis": txt_desc.get("1.0", "end").strip(),
            "autor": str(autor or ctx.get("autor") or "").strip(),
            "przypisane_do": "" if var_all.get() else var_assigned.get().strip(),
            "dla_wszystkich": bool(var_all.get()),
            "termin": var_deadline.get().strip(),
            "priorytet": var_priority.get().strip(),
            "modul_zrodlowy": source_module["value"],
            "obiekt_id": object_id,
            "meta": {"object_label": selected_label},
        }

        if edit_mode and existing_id:
            changed = update_dyspozycja(existing_id, payload)
            if not changed:
                messagebox.showerror(
                    "Dyspozycje",
                    "Nie udało się zapisać zmian Dyspozycji.",
                    parent=win,
                )
                return
        else:
            item = make_dyspozycja(**payload)
            add_dyspozycja(item)

        _event_updated()
        messagebox.showinfo(
            "Dyspozycje",
            "Dyspozycja została zaktualizowana." if edit_mode else "Dyspozycja została zapisana.",
            parent=win,
        )
        win.destroy()

    ttk.Button(btns, text="Anuluj", command=win.destroy).pack(side="right", padx=(8, 0))
    ttk.Button(btns, text="Zapisz", command=_save).pack(side="right")
    if edit_mode and existing_id:
        ttk.Button(btns, text="Zamknij dyspozycję", command=_close_current).pack(
            side="left"
        )

    cb_object.focus_set()
    win.transient(root)
    win.grab_set()
    return win
