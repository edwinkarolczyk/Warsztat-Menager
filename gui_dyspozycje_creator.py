# version: 1.0
"""Wspólny kreator Dyspozycji z dynamicznymi listami obiektów."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
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
    load_dyspozycje,
    make_dyspozycja,
    update_dyspozycja,
)

try:
    from profiles_store import load_profiles_users, resolve_profiles_path
except Exception:  # pragma: no cover
    load_profiles_users = None  # type: ignore
    resolve_profiles_path = None  # type: ignore


def _normalize_object_id(value: str) -> set[str]:
    raw = str(value or "").strip()
    out = {raw} if raw else set()
    if raw.isdigit():
        out.add(raw.zfill(3))
        out.add(str(int(raw)))
    return {item for item in out if item}


def _dysp_date_text(row: dict[str, Any]) -> str:
    return str(
        row.get("updated_at")
        or row.get("created_at")
        or row.get("utworzono")
        or row.get("data")
        or ""
    ).strip()


def _dysp_title_text(row: dict[str, Any]) -> str:
    return str(row.get("tytul") or row.get("opis") or "Dyspozycja").strip()


def _dysp_assignee_text(row: dict[str, Any]) -> str:
    if bool(row.get("dla_wszystkich")):
        return "wszyscy"
    return str(row.get("przypisane_do") or "—").strip() or "—"


def _find_recent_dyspozycje_for_object(
    typ: str,
    object_id: str,
    *,
    limit: int = 5,
    skip_id: str = "",
) -> list[dict[str, Any]]:
    typ_norm = str(typ or "").strip().lower()
    variants = _normalize_object_id(object_id)
    if not typ_norm or not variants:
        return []

    try:
        rows = load_dyspozycje()
    except Exception:
        rows = []

    matched: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue

        row_id = str(row.get("id") or "").strip()
        if skip_id and row_id == skip_id:
            continue

        row_typ = str(
            row.get("typ_dyspozycji") or row.get("typ") or ""
        ).strip().lower()
        if row_typ != typ_norm:
            continue

        row_object_id = str(
            row.get("obiekt_id")
            or row.get("object_id")
            or row.get("narzedzie_id")
            or row.get("maszyna_id")
            or ""
        ).strip()
        if not variants.intersection(_normalize_object_id(row_object_id)):
            continue

        matched.append(row)

    matched.sort(key=_dysp_date_text, reverse=True)
    return matched[:limit]


def _format_dyspozycje_history(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Brak wcześniejszych dyspozycji dla tego obiektu"

    lines: list[str] = []
    for row in rows:
        date_text = _dysp_date_text(row)
        if len(date_text) >= 10:
            date_text = date_text[:10]
        priority = str(row.get("priorytet") or "normalny").strip()
        status = str(row.get("status") or "—").strip()
        title = _dysp_title_text(row)
        assignee = _dysp_assignee_text(row)

        lines.append(
            f"{date_text or '—'} | {priority} | {status}\n"
            f"{title}\n"
            f"Przypisane: {assignee}"
        )

    return "\n\n".join(lines)


def _task_title(task: Any) -> str:
    if isinstance(task, dict):
        return str(
            task.get("tytul")
            or task.get("title")
            or task.get("text")
            or task.get("nazwa")
            or task.get("opis")
            or ""
        ).strip()
    return str(task or "").strip()


def _task_done(task: Any) -> bool:
    if isinstance(task, dict):
        return bool(task.get("done") or task.get("wykonane"))
    return False


def _extract_tool_tasks(tool: dict[str, Any]) -> list[str]:
    raw = tool.get("zadania")
    tasks: list[Any] = []
    if isinstance(raw, list):
        tasks = raw
    elif isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list):
                tasks.extend(value)
            elif isinstance(value, dict):
                for title, done in value.items():
                    tasks.append({"tytul": str(title), "done": bool(done)})
            elif isinstance(value, str) and value.strip():
                tasks.append(value.strip())
    elif isinstance(raw, str) and raw.strip():
        tasks = [line.strip() for line in raw.splitlines() if line.strip()]

    out: list[str] = []
    for task in tasks:
        title = _task_title(task)
        if not title:
            continue
        mark = "☑" if _task_done(task) else "☐"
        out.append(f"{mark} {title}")
    return out


def _format_machine_months(value: Any) -> str:
    months = {
        1: "Styczeń",
        2: "Luty",
        3: "Marzec",
        4: "Kwiecień",
        5: "Maj",
        6: "Czerwiec",
        7: "Lipiec",
        8: "Sierpień",
        9: "Wrzesień",
        10: "Październik",
        11: "Listopad",
        12: "Grudzień",
    }
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return str(value)
    out: list[str] = []
    for item in value:
        try:
            out.append(months.get(int(item), str(item)))
        except (TypeError, ValueError):
            out.append(str(item))
    return ", ".join(out) if out else "—"


def _find_tool_preview(tool_id: str) -> dict[str, str]:
    variants = _normalize_object_id(tool_id)
    if not variants:
        return {}
    try:
        from gui_narzedzia import _external_load_tools_rows
    except Exception:
        return {}
    try:
        rows = _external_load_tools_rows()
    except Exception:
        rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("nr") or row.get("numer") or "").strip()
        rid_variants = _normalize_object_id(rid)
        if not variants.intersection(rid_variants):
            continue
        preview = {
            "ID": rid or tool_id,
            "Nazwa": str(row.get("nazwa") or row.get("name") or "—"),
            "Typ": str(row.get("typ") or row.get("type") or "—"),
            "Status": str(row.get("status") or "—"),
        }
        tasks = _extract_tool_tasks(row)
        if tasks:
            preview["Zadania narzędzia"] = "\n".join(tasks[:12])
            if len(tasks) > 12:
                preview["Zadania narzędzia"] += (
                    f"\n… oraz {len(tasks) - 12} więcej"
                )
        else:
            preview["Zadania narzędzia"] = (
                "Brak zadań przypisanych do narzędzia"
            )
        return preview
    return {}


def _find_machine_preview(machine_id: str) -> dict[str, str]:
    variants = _normalize_object_id(machine_id)
    if not variants:
        return {}
    try:
        rows = load_machine_choices()
    except Exception:
        rows = []
    for object_id, label in rows or []:
        oid = str(object_id or "").strip()
        if variants.intersection(_normalize_object_id(oid)):
            return {
                "ID": oid or machine_id,
                "Nazwa": str(label or "—"),
                "Typ": "—",
                "Status": "—",
                "Lokalizacja": "—",
            }
    try:
        from gui_maszyny import load_machines_rows
        machines = load_machines_rows()
    except Exception:
        machines = []
    for row in machines or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("nr_ewid") or "").strip()
        if not variants.intersection(_normalize_object_id(rid)):
            continue
        workers = row.get("review_workers") or []
        if isinstance(workers, list):
            workers_text = ", ".join(
                str(item) for item in workers if str(item).strip()
            )
        else:
            workers_text = str(workers or "—")
        return {
            "ID": rid or machine_id,
            "Nazwa": str(row.get("nazwa") or row.get("name") or "—"),
            "Typ": str(row.get("typ") or row.get("type") or "—"),
            "Status": str(row.get("status") or "—"),
            "Lokalizacja": str(row.get("lokalizacja") or row.get("hala") or "—"),
            "Domyślny typ przeglądu": str(
                row.get("default_review_type") or "—"
            ),
            "Miesiące przeglądu": _format_machine_months(
                row.get("review_months")
            ),
            "Sugerowani serwisanci": workers_text or "—",
            "Wpisy serwisowe": str(
                len(row.get("reviews") or row.get("zadania") or [])
            ),
        }
    return {}


def _tool_data_for_card(tool_id: str) -> dict[str, Any]:
    variants = _normalize_object_id(tool_id)
    if not variants:
        return {}
    try:
        from gui_narzedzia import _external_load_tools_rows
        rows = _external_load_tools_rows()
    except Exception:
        rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("nr") or row.get("numer") or "").strip()
        if variants.intersection(_normalize_object_id(rid)):
            return dict(row)
    return {}


def _machine_data_for_card(machine_id: str) -> dict[str, Any]:
    variants = _normalize_object_id(machine_id)
    if not variants:
        return {}
    try:
        from gui_maszyny import load_machines_rows
        rows = load_machines_rows()
    except Exception:
        rows = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("nr_ewid") or "").strip()
        if variants.intersection(_normalize_object_id(rid)):
            return dict(row)
    return {}


def _cards_output_dir() -> Path:
    base = Path.cwd() / "wydruki" / "karty"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _print_tool_card_from_dyspo(
    master: tk.Widget,
    object_id: str,
    dyspozycja: dict[str, Any] | None = None,
) -> None:
    tool_id = str(object_id or "").strip()
    if not tool_id:
        messagebox.showwarning("Dyspozycje", "Brak numeru narzędzia.", parent=master)
        return
    tool = _tool_data_for_card(tool_id)
    if not tool:
        messagebox.showwarning(
            "Dyspozycje",
            f"Nie znaleziono danych narzędzia: {tool_id}",
            parent=master,
        )
        return
    try:
        from tool_card_pdf import generate_tool_card
        generate_tool_card(
            tool,
            _cards_output_dir(),
            dyspozycja=dyspozycja,
            open_after=True,
        )
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się wygenerować karty narzędzia:\n{exc}",
            parent=master,
        )


def _print_machine_card_from_dyspo(
    master: tk.Widget,
    object_id: str,
    dyspozycja: dict[str, Any] | None = None,
) -> None:
    machine_id = str(object_id or "").strip()
    if not machine_id:
        messagebox.showwarning("Dyspozycje", "Brak numeru maszyny.", parent=master)
        return
    machine = _machine_data_for_card(machine_id)
    if not machine:
        messagebox.showwarning(
            "Dyspozycje",
            f"Nie znaleziono danych maszyny: {machine_id}",
            parent=master,
        )
        return
    try:
        from machine_card_pdf import generate_machine_card
        generate_machine_card(
            machine,
            _cards_output_dir(),
            dyspozycja=dyspozycja,
            open_after=True,
        )
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się wygenerować karty maszyny:\n{exc}",
            parent=master,
        )


def _print_blank_tool_card_from_dyspo(
    master: tk.Widget,
    dyspozycja: dict[str, Any] | None = None,
) -> None:
    try:
        from tool_card_pdf import generate_blank_tool_card

        generate_blank_tool_card(
            _cards_output_dir(),
            dyspozycja=dyspozycja,
            open_after=True,
        )
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się wygenerować pustej karty narzędzia:\n{exc}",
            parent=master,
        )


def _print_blank_machine_card_from_dyspo(
    master: tk.Widget,
    dyspozycja: dict[str, Any] | None = None,
) -> None:
    try:
        from machine_card_pdf import generate_blank_machine_card

        generate_blank_machine_card(
            _cards_output_dir(),
            dyspozycja=dyspozycja,
            open_after=True,
        )
    except Exception as exc:
        messagebox.showerror(
            "Dyspozycje",
            f"Nie udało się wygenerować pustej karty maszyny:\n{exc}",
            parent=master,
        )


def _try_open_tool_editor(master: tk.Widget, object_id: str) -> None:
    """Otwiera normalny widok narzędzia używany przez moduł Narzędzia."""
    tool_id = str(object_id or "").strip()
    if not tool_id:
        messagebox.showwarning("Dyspozycje", "Brak numeru narzędzia.", parent=master)
        return

    try:
        from gui_narzedzia import open_tool_from_external_context

        opened = open_tool_from_external_context(
            master.winfo_toplevel(),
            tool_id,
        )
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
    object_panel.rowconfigure(1, weight=1)

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

    object_card = ttk.Frame(object_panel)
    object_card.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
    object_card.columnconfigure(1, weight=1)

    object_panel_buttons = ttk.Frame(object_panel)
    object_panel_buttons.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))

    options_map: dict[str, str] = {}
    all_labels: list[str] = []
    source_module = {"value": ""}

    def _current_dyspozycja_for_print() -> dict[str, Any]:
        return {
            "opis": txt_desc.get("1.0", "end").strip(),
            "termin": var_deadline.get().strip(),
            "przypisane_do": (
                "" if var_all.get() else var_assigned.get().strip()
            ),
            "priorytet": var_priority.get().strip(),
            "autor": str(autor or ctx.get("autor") or "").strip(),
        }

    def _clear_object_card() -> None:
        for child in object_card.winfo_children():
            child.destroy()

    def _render_object_card(title: str, data: dict[str, str]) -> None:
        _clear_object_card()
        ttk.Label(
            object_card,
            text=title,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        if not data:
            ttk.Label(
                object_card,
                text="Nie znaleziono danych powiązanego obiektu.",
            ).grid(row=1, column=0, columnspan=2, sticky="w")
            return
        for idx, (label, value) in enumerate(data.items(), start=1):
            ttk.Label(object_card, text=f"{label}:").grid(
                row=idx, column=0, sticky="e", padx=(0, 8), pady=2
            )
            ttk.Label(
                object_card, text=value, justify="left", wraplength=900
            ).grid(row=idx, column=1, sticky="w", pady=2)

    btn_open_tool = ttk.Button(
        object_panel_buttons,
        text="Otwórz edytor narzędzia",
        command=lambda: _try_open_tool_editor(
            win,
            options_map.get(var_object_display.get().strip(), ""),
        ),
    )
    btn_print_tool_card = ttk.Button(
        object_panel_buttons,
        text="Drukuj kartę narzędzia",
        command=lambda: _print_tool_card_from_dyspo(
            win,
            options_map.get(var_object_display.get().strip(), ""),
            _current_dyspozycja_for_print(),
        ),
    )
    btn_print_blank_tool_card = ttk.Button(
        object_panel_buttons,
        text="Drukuj pustą kartę narzędzia",
        command=lambda: _print_blank_tool_card_from_dyspo(
            win,
            _current_dyspozycja_for_print(),
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

    btn_print_machine_card = ttk.Button(
        object_panel_buttons,
        text="Drukuj kartę maszyny",
        command=lambda: _print_machine_card_from_dyspo(
            win,
            options_map.get(var_object_display.get().strip(), ""),
            _current_dyspozycja_for_print(),
        ),
    )

    btn_print_blank_machine_card = ttk.Button(
        object_panel_buttons,
        text="Drukuj pustą kartę maszyny",
        command=lambda: _print_blank_machine_card_from_dyspo(
            win,
            _current_dyspozycja_for_print(),
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
        _clear_object_card()

        if typ == "narzedzie":
            var_object_panel_info.set(
                "Narzędzie powiązane z dyspozycją: "
                f"{selected_label or object_id or 'brak wyboru'}"
            )
            tool_preview = _find_tool_preview(object_id)
            history = _find_recent_dyspozycje_for_object(
                "narzedzie",
                object_id,
                skip_id=existing_id,
            )
            tool_preview["Ostatnie dyspozycje"] = _format_dyspozycje_history(
                history
            )
            _render_object_card(
                "Karta narzędzia",
                tool_preview,
            )
            btn_open_tool.pack(side="left")
            btn_print_tool_card.pack(side="left", padx=(8, 0))
            btn_print_blank_tool_card.pack(side="left", padx=(8, 0))
        elif typ == "maszyna":
            var_object_panel_info.set(
                "Maszyna powiązana z dyspozycją: "
                f"{selected_label or object_id or 'brak wyboru'}"
            )
            machine_preview = _find_machine_preview(object_id)
            history = _find_recent_dyspozycje_for_object(
                "maszyna",
                object_id,
                skip_id=existing_id,
            )
            machine_preview["Ostatnie dyspozycje"] = (
                _format_dyspozycje_history(history)
            )
            _render_object_card(
                "Karta maszyny",
                machine_preview,
            )
            btn_open_machine.pack(side="left")
            btn_print_machine_card.pack(side="left", padx=(8, 0))
            btn_print_blank_machine_card.pack(side="left", padx=(8, 0))
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
            "przypisane_do": (
                "" if var_all.get() else var_assigned.get().strip()
            ),
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
