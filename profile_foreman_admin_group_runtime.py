# version: 1.2
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
_FEEDBACK_STATUSES = ("Nowa", "W trakcie", "Zamknięta")


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
    value = str(row.get("status") or "").strip()
    return value or "Nowa"


def _build_feedback_tab(panel) -> None:
    parent = getattr(panel, "_tabs", {}).get("Opinie")
    if parent is None:
        return

    for child in list(parent.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    header = ttk.Frame(parent, style="WM.Container.TFrame")
    header.pack(fill="x", padx=8, pady=(8, 6))
    ttk.Label(
        header,
        text="Opinie przesłane z modułu „Wyślij opinię”.",
        style="WM.Muted.TLabel",
    ).pack(side="left")

    info_var = tk.StringVar(value="")
    ttk.Label(parent, textvariable=info_var, style="WM.Muted.TLabel").pack(
        anchor="w", padx=8, pady=(0, 6)
    )

    columns = ("ts", "login", "rola", "status", "message")
    tree = ttk.Treeview(
        parent,
        columns=columns,
        show="headings",
        style="Foreman.Treeview",
        height=13,
    )
    tree.heading("ts", text="Data")
    tree.heading("login", text="Login")
    tree.heading("rola", text="Rola")
    tree.heading("status", text="Status")
    tree.heading("message", text="Opinia")
    tree.column("ts", width=155, anchor="w")
    tree.column("login", width=115, anchor="w")
    tree.column("rola", width=110, anchor="w")
    tree.column("status", width=110, anchor="center")
    tree.column("message", width=620, anchor="w")

    tree_wrap = ttk.Frame(parent, style="WM.Container.TFrame")
    tree_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    tree.grid(in_=tree_wrap, row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)
    tree_wrap.grid_rowconfigure(0, weight=1)
    tree_wrap.grid_columnconfigure(0, weight=1)

    actions = ttk.Frame(parent, style="WM.Container.TFrame")
    actions.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Label(actions, text="Status:").pack(side="left")

    status_var = tk.StringVar(value="Nowa")
    status_box = ttk.Combobox(
        actions,
        textvariable=status_var,
        values=_FEEDBACK_STATUSES,
        state="readonly",
        width=14,
    )
    status_box.pack(side="left", padx=(6, 4))
    add_help_button(
        actions,
        "Status opisuje etap obsługi opinii: Nowa, W trakcie albo Zamknięta. "
        "Przy zamknięciu WM zapisuje login i datę osoby zamykającej.",
    ).pack(side="left", padx=(0, 8))

    details_box = ttk.LabelFrame(
        parent,
        text="Treść i historia opinii",
        style="WM.Section.TLabelframe",
        padding=8,
    )
    details_box.pack(fill="x", padx=8, pady=(0, 8))
    details = tk.Text(details_box, height=8, wrap="word")
    details.pack(fill="x", expand=True)
    details.configure(state="disabled")

    rows_cache: dict[str, dict] = {}

    def _set_details(value: str) -> None:
        try:
            details.configure(state="normal")
            details.delete("1.0", "end")
            details.insert("1.0", value)
            details.configure(state="disabled")
        except Exception:
            pass

    def _selected_cached() -> tuple[str, dict] | None:
        selected = tree.selection()
        if not selected:
            return None
        iid = str(selected[0])
        row = rows_cache.get(iid)
        if row is None:
            return None
        return iid, row

    def _render_details(row: dict) -> None:
        lines = [
            f"Data: {row.get('ts', '')}",
            f"Login: {row.get('login', '')}",
            f"Rola: {row.get('rola', '')}",
            f"Status: {_feedback_status(row)}",
        ]
        closed_by = str(row.get("closed_by") or "").strip()
        closed_at = str(row.get("closed_at") or "").strip()
        if closed_by or closed_at:
            lines.append(
                "Ostatnie zamknięcie: "
                f"{closed_at or '—'} | przez: {closed_by or '—'}"
            )

        history = row.get("status_history")
        if isinstance(history, list) and history:
            lines.append("")
            lines.append("Historia statusu:")
            for item in history[-8:]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"- {item.get('ts', '')} | {item.get('status', '')} "
                    f"| {item.get('by', '')}"
                )

        lines.extend(["", str(row.get("message") or "")])
        _set_details("\n".join(lines))

    def _show_selected(_event=None) -> None:
        cached = _selected_cached()
        if cached is None:
            return
        _iid, row = cached
        status_var.set(_feedback_status(row))
        _render_details(row)

    def _refresh(*, select_iid: str | None = None) -> None:
        rows_cache.clear()
        tree.delete(*tree.get_children())
        path = _feedback_path()

        try:
            rows = _load_feedback_rows(path)
        except Exception as exc:
            info_var.set(f"Błąd odczytu opinii: {exc}")
            _set_details("")
            return

        indexed = list(enumerate(rows))
        indexed.sort(
            key=lambda item: str(item[1].get("ts") or ""),
            reverse=True,
        )

        for source_index, row in indexed:
            iid = str(source_index)
            rows_cache[iid] = dict(row)
            message = str(row.get("message") or "")
            short = message.replace("\n", " ").strip()
            if len(short) > 140:
                short = short[:140] + "…"
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    str(row.get("ts") or ""),
                    str(row.get("login") or ""),
                    str(row.get("rola") or ""),
                    _feedback_status(row),
                    short,
                ),
            )

        info_var.set(f"Wczytano opinii: {len(rows)} | Plik: {path}")
        _set_details("")
        status_var.set("Nowa")

        if select_iid is not None and tree.exists(select_iid):
            tree.selection_set(select_iid)
            tree.focus(select_iid)
            tree.see(select_iid)
            _show_selected()

    def _save_status() -> None:
        cached = _selected_cached()
        if cached is None:
            messagebox.showinfo(
                "Opinie",
                "Wybierz opinię z listy.",
                parent=panel.winfo_toplevel(),
            )
            return

        iid, cached_row = cached
        new_status = str(status_var.get() or "").strip()
        if new_status not in _FEEDBACK_STATUSES:
            messagebox.showerror(
                "Opinie",
                "Wybierz prawidłowy status opinii.",
                parent=panel.winfo_toplevel(),
            )
            return

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
        old_status = _feedback_status(row)
        if old_status == new_status and str(row.get("status") or "").strip():
            messagebox.showinfo(
                "Opinie",
                "Ta opinia ma już wybrany status.",
                parent=panel.winfo_toplevel(),
            )
            return

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

        if new_status == "Zamknięta":
            row["closed_at"] = now
            row["closed_by"] = actor

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

    ttk.Button(actions, text="Zapisz status", command=_save_status).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(actions, text="Odśwież", command=_refresh).pack(side="right")
    tree.bind("<<TreeviewSelect>>", _show_selected)

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
