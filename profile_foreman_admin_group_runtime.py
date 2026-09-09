# version: 1.3
"""Grupuje rzadziej używane zakładki Brygadzisty w jedną Administrację.

Na głównym poziomie pozostają tylko codzienne widoki: Pulpit, Ruch WM,
Obecność i Urlopy. Użytkownicy, Opinie i Statystyki są dostępne wewnątrz
Administracji. Zakładka Opinie obsługuje status zgłoszenia bez zmiany
istniejącego pliku data/opinie.json ani starszych rekordów.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from config_manager import ConfigManager
from services.profile_service import ProfileService
from ui_context_help import add_help_button

_INSTALLED = False
_ADMIN_NAMES = ("Użytkownicy", "Opinie", "Statystyki")
_FEEDBACK_OPEN = "Do zrobienia"
_FEEDBACK_DONE = "Zrobione"
_FEEDBACK_FILTERS = ("Otwarte", "Zrobione", "Wszystkie")


def _feedback_path() -> str:
    try:
        data_root = ConfigManager().path_data()
    except Exception:
        data_root = "data"
    return os.path.join(str(data_root), "opinie.json")


def _load_feedback_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Plik opinii musi zawierać listę wpisów.")
    return [item if isinstance(item, dict) else {} for item in payload]


def _save_feedback_rows(path: str, rows: list[dict]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise


def _active_login(panel) -> str:
    try:
        login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        if login:
            return login
    except Exception:
        pass

    for owner in (
        panel,
        getattr(panel, "owner", None),
        getattr(panel, "master", None),
    ):
        if owner is None:
            continue
        for attr in ("login", "current_login", "logged_login", "uzytkownik"):
            try:
                login = str(getattr(owner, attr, "") or "").strip()
            except Exception:
                login = ""
            if login:
                return login
    return "—"


def _feedback_signature(row: dict) -> tuple[str, str, str]:
    return (
        str(row.get("ts") or ""),
        str(row.get("login") or ""),
        str(row.get("message") or ""),
    )


def _feedback_status(row: dict) -> str:
    """Zwróć prosty status, zachowując zgodność ze starszymi wpisami."""
    value = str(row.get("status") or "").strip().casefold()
    if value in {
        "zrobione",
        "zamknięta",
        "zamknieta",
        "zamknięte",
        "zamkniete",
        "done",
        "closed",
    }:
        return _FEEDBACK_DONE
    return _FEEDBACK_OPEN


def _feedback_month_year(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%m:%y")
    except Exception:
        if len(raw) >= 7 and raw[4:5] == "-":
            return f"{raw[5:7]}:{raw[2:4]}"
        return raw[:5]


def _feedback_closed_label(row: dict) -> str:
    actor = str(row.get("closed_by") or "").strip()
    raw = str(row.get("closed_at") or "").strip()
    if not actor and not raw:
        return ""
    shown = raw
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            shown = parsed.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass
    return f"Zrobione: {actor or '—'} — {shown or '—'}"


def _feedback_two_lines(value) -> str:
    """Pokaż całą opinię w dwóch logicznych wierszach bez wielokropka."""
    text = " ".join(str(value or "").replace("\n", " ").split())
    if len(text) <= 115:
        return text

    middle = len(text) // 2
    left = text.rfind(" ", 0, middle + 1)
    right = text.find(" ", middle)
    candidates = [pos for pos in (left, right) if pos > 0]
    if candidates:
        split_at = min(candidates, key=lambda pos: abs(pos - middle))
    else:
        split_at = middle
    return f"{text[:split_at].strip()}\n{text[split_at:].strip()}"


def _build_feedback_tab(panel) -> None:
    parent = getattr(panel, "_tabs", {}).get("Opinie")
    if parent is None:
        return

    for child in list(parent.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    style = ttk.Style(panel)
    style.configure("Feedback.Treeview", font=("Segoe UI", 10), rowheight=46)
    style.configure("Feedback.Treeview.Heading", font=("Segoe UI", 10, "bold"))

    header = ttk.Frame(parent, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(
        header,
        text="Opinie przesłane z modułu „Wyślij opinię”.",
        style="WM.Muted.TLabel",
    ).pack(side="left")

    info_var = tk.StringVar(value="")
    ttk.Label(parent, textvariable=info_var, style="WM.Muted.TLabel").pack(
        anchor="w", padx=8, pady=(0, 5)
    )

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 6))

    filter_var = tk.StringVar(value="Otwarte")
    ttk.Label(actions, text="Pokaż:").pack(side="left")
    for label in _FEEDBACK_FILTERS:
        ttk.Radiobutton(
            actions,
            text=label,
            value=label,
            variable=filter_var,
            command=lambda: _refresh(),
        ).pack(side="left", padx=(6, 0))

    add_help_button(
        actions,
        "Status określa, czy zgłoszona opinia została już obsłużona. "
        "Zrobione opinie pozostają w historii.",
    ).pack(side="right", padx=(6, 0))

    action_var = tk.StringVar(value="✓ Oznacz jako zrobione")
    action_button = ttk.Button(actions, textvariable=action_var)
    action_button.pack(side="right", padx=(6, 0))
    refresh_button = ttk.Button(actions, text="Odśwież")
    refresh_button.pack(side="right", padx=(6, 0))

    selected_info_var = tk.StringVar(value="")
    ttk.Label(
        parent,
        textvariable=selected_info_var,
        style="WM.Muted.TLabel",
    ).pack(anchor="w", padx=8, pady=(0, 5))

    columns = ("ts", "login", "rola", "status", "message")
    tree_wrap = ttk.Frame(parent, style="WM.Container.TFrame")
    tree_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    tree = ttk.Treeview(
        tree_wrap,
        columns=columns,
        show="headings",
        style="Feedback.Treeview",
        height=8,
    )
    tree.heading("ts", text="Data")
    tree.heading("login", text="Login")
    tree.heading("rola", text="Rola")
    tree.heading("status", text="Status")
    tree.heading("message", text="Opinia")
    tree.column("ts", width=58, minwidth=58, anchor="center", stretch=False)
    tree.column("login", width=90, minwidth=70, anchor="w", stretch=False)
    tree.column("rola", width=90, minwidth=70, anchor="w", stretch=False)
    tree.column("status", width=105, minwidth=95, anchor="center", stretch=False)
    tree.column("message", width=850, minwidth=500, anchor="w", stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")

    y_scrollbar = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
    y_scrollbar.grid(row=0, column=1, sticky="ns")
    x_scrollbar = ttk.Scrollbar(tree_wrap, orient="horizontal", command=tree.xview)
    x_scrollbar.grid(row=1, column=0, sticky="ew")
    tree.configure(
        yscrollcommand=y_scrollbar.set,
        xscrollcommand=x_scrollbar.set,
    )
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    tree.tag_configure("feedback_open", foreground="#f59e0b")
    tree.tag_configure("feedback_done", foreground="#22c55e")

    rows_cache: dict[str, dict] = {}

    def _selected_cached() -> tuple[str, dict] | None:
        selected = tree.selection()
        if not selected:
            return None
        iid = str(selected[0])
        row = rows_cache.get(iid)
        if row is None:
            return None
        return iid, row

    def _update_selection_ui(_event=None) -> None:
        cached = _selected_cached()
        if cached is None:
            action_button.state(["disabled"])
            action_var.set("✓ Oznacz jako zrobione")
            selected_info_var.set("")
            return

        action_button.state(["!disabled"])
        _iid, row = cached
        status = _feedback_status(row)
        if status == _FEEDBACK_DONE:
            action_var.set("↶ Przywróć do otwartych")
            selected_info_var.set(_feedback_closed_label(row))
        else:
            action_var.set("✓ Oznacz jako zrobione")
            selected_info_var.set("Do zrobienia")

    def _refresh(*, select_iid: str | None = None) -> None:
        rows_cache.clear()
        tree.delete(*tree.get_children())
        path = _feedback_path()

        try:
            rows = _load_feedback_rows(path)
        except Exception as exc:
            info_var.set(f"Błąd odczytu opinii: {exc}")
            selected_info_var.set("")
            action_button.state(["disabled"])
            return

        open_count = sum(1 for row in rows if _feedback_status(row) == _FEEDBACK_OPEN)
        done_count = len(rows) - open_count
        selected_filter = filter_var.get()

        indexed = list(enumerate(rows))
        indexed.sort(
            key=lambda item: str(item[1].get("ts") or ""),
            reverse=True,
        )

        shown_count = 0
        for source_index, row in indexed:
            status = _feedback_status(row)
            if selected_filter == "Otwarte" and status != _FEEDBACK_OPEN:
                continue
            if selected_filter == "Zrobione" and status != _FEEDBACK_DONE:
                continue

            iid = str(source_index)
            rows_cache[iid] = dict(row)
            tag = "feedback_done" if status == _FEEDBACK_DONE else "feedback_open"
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    _feedback_month_year(row.get("ts")),
                    str(row.get("login") or ""),
                    str(row.get("rola") or ""),
                    status,
                    _feedback_two_lines(row.get("message")),
                ),
                tags=(tag,),
            )
            shown_count += 1

        info_var.set(
            f"Opinie: {len(rows)} | Do zrobienia: {open_count} | "
            f"Zrobione: {done_count} | Pokazano: {shown_count}"
        )
        selected_info_var.set("")
        action_button.state(["disabled"])
        action_var.set("✓ Oznacz jako zrobione")

        if select_iid is not None and tree.exists(select_iid):
            tree.selection_set(select_iid)
            tree.focus(select_iid)
            tree.see(select_iid)
            _update_selection_ui()

    def _toggle_status() -> None:
        cached = _selected_cached()
        if cached is None:
            messagebox.showinfo(
                "Opinie",
                "Wybierz opinię z listy.",
                parent=panel.winfo_toplevel(),
            )
            return

        iid, cached_row = cached
        path = _feedback_path()
        try:
            rows = _load_feedback_rows(path)
        except Exception as exc:
            messagebox.showerror(
                "Opinie",
                f"Nie udało się odczytać pliku opinii:\n{exc}",
                parent=panel.winfo_toplevel(),
            )
            return

        try:
            source_index = int(iid)
        except Exception:
            source_index = -1

        target_index = -1
        signature = _feedback_signature(cached_row)
        if 0 <= source_index < len(rows):
            if _feedback_signature(rows[source_index]) == signature:
                target_index = source_index
        if target_index < 0:
            for index, row in enumerate(rows):
                if _feedback_signature(row) == signature:
                    target_index = index
                    break
        if target_index < 0:
            messagebox.showerror(
                "Opinie",
                "Wybrana opinia zmieniła się na dysku. Odśwież listę i spróbuj ponownie.",
                parent=panel.winfo_toplevel(),
            )
            _refresh()
            return

        row = rows[target_index]
        new_status = (
            _FEEDBACK_OPEN
            if _feedback_status(row) == _FEEDBACK_DONE
            else _FEEDBACK_DONE
        )
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        actor = _active_login(panel)

        row["status"] = new_status
        row["status_changed_at"] = now
        row["status_changed_by"] = actor

        history = row.get("status_history")
        if not isinstance(history, list):
            history = []
        history.append({"ts": now, "status": new_status, "by": actor})
        row["status_history"] = history

        if new_status == _FEEDBACK_DONE:
            row["closed_at"] = now
            row["closed_by"] = actor
        else:
            row.pop("closed_at", None)
            row.pop("closed_by", None)

        try:
            _save_feedback_rows(path, rows)
        except Exception as exc:
            messagebox.showerror(
                "Opinie",
                f"Nie udało się zapisać statusu opinii:\n{exc}",
                parent=panel.winfo_toplevel(),
            )
            return

        _refresh(select_iid=str(target_index))

    action_button.configure(command=_toggle_status)
    refresh_button.configure(command=_refresh)
    tree.bind("<<TreeviewSelect>>", _update_selection_ui)

    panel._wm_feedback_tree = tree
    panel._wm_feedback_refresh = _refresh
    _refresh()


def _group_admin_tabs(panel) -> None:
    if getattr(panel, "_wm_admin_group_built", False):
        return

    notebook = getattr(panel, "notebook", None)
    tabs = getattr(panel, "_tabs", None)
    if notebook is None or not isinstance(tabs, dict):
        return

    old_tabs = {name: tabs.get(name) for name in _ADMIN_NAMES}

    admin = ttk.Frame(notebook, style="WM.Container.TFrame")
    notebook.add(admin, text="Administracja")
    tabs["Administracja"] = admin

    header = ttk.Frame(admin, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 4))
    ttk.Label(header, text="Administracja profili", style="WM.Muted.TLabel").pack(side="left")
    add_help_button(
        header,
        "Tutaj są ustawienia kont, Opinie i Statystyki. "
        "Codzienna praca brygadzisty pozostaje w Pulpit, Ruch WM, "
        "Obecność i Urlopy.",
    ).pack(side="left", padx=(6, 0))

    inner = ttk.Notebook(admin)
    inner.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    for name in _ADMIN_NAMES:
        frame = ttk.Frame(inner, style="WM.Container.TFrame")
        inner.add(frame, text=name)
        tabs[name] = frame

    # Nie tylko ukrywamy stare karty, ale usuwamy ich zawartość. Dzięki temu
    # nie istnieją dwa równoległe panele Użytkowników ani zbędne bindingi GUI.
    for old in old_tabs.values():
        if old is None:
            continue
        for child in list(old.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        try:
            notebook.hide(old)
        except Exception:
            pass

    try:
        from profile_foreman_flat_users_runtime import _flatten_users_tab
        _flatten_users_tab(panel)
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][WARN] admin users rebuild failed: {exc!r}")

    _build_feedback_tab(panel)

    for index, key in enumerate(("Pulpit", "Zespół", "Obecność", "Urlopy", "Administracja")):
        tab = tabs.get(key)
        if tab is None:
            continue
        try:
            notebook.insert(index, tab)
        except Exception:
            pass

    panel._wm_admin_notebook = inner
    panel._wm_admin_group_built = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        import gui_profile_foreman as foreman
        cls = foreman.ForemanProfilePanel
    except Exception:
        return

    if getattr(cls, "_wm_admin_group_runtime", False):
        _INSTALLED = True
        return

    original_build = cls._build

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        _group_admin_tabs(self)
        return result

    cls._build = build
    cls._wm_admin_group_runtime = True
    _INSTALLED = True


__all__ = ["install"]
