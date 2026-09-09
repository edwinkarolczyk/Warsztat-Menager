# version: 1.0
"""Końcowe, wąskie poprawki po audycie logów z 2026-09-07.

Zakres:
- bezpieczne callbacki panelu, które mogą zostać wywołane także bez obiektu event,
- leniwe renderowanie wewnętrznych zakładek Brygadzisty,
- status aktywnej sesji WM w Obecności,
- migający alert oczekujących wniosków urlopowych dla brygadzisty,
- kanonizacja starych wpisów Opinii do trwałego user_id,
- wyciszenie nieaktywnych ścieżek legacy, gdy kanoniczne źródło już istnieje.

Runtime nie usuwa żadnych danych ani starych plików.
"""
from __future__ import annotations

import inspect
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

_INSTALLED = False
_LAST_LEAVE_ALERT: tuple[str, tuple[str, ...], float] | None = None


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _install_safe_panel_bindings() -> None:
    """Uruchom_panel ma kilka lambd eventowych; pozwól im bezpiecznie przyjąć brak eventu."""
    if getattr(tk.Misc, "_wm_safe_panel_bind_v1", False):
        return
    original_bind = tk.Misc.bind

    def bind(self, sequence=None, func=None, add=None):
        wrapped = func
        if callable(func):
            qualname = str(getattr(func, "__qualname__", "") or "")
            if "uruchom_panel.<locals>.<lambda>" in qualname:
                try:
                    params = list(inspect.signature(func).parameters.values())
                    required = [
                        p
                        for p in params
                        if p.default is inspect._empty
                        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                    ]
                except Exception:
                    required = []
                if len(required) == 1:
                    original_func = func

                    def safe_callback(event=None, *args, **kwargs):
                        return original_func(event)

                    wrapped = safe_callback
        return original_bind(self, sequence, wrapped, add)

    tk.Misc.bind = bind
    tk.Misc._wm_safe_panel_bind_v1 = True


def _pending_leave_rows() -> list[dict]:
    try:
        from services.leave_workflow_service import read_requests

        return [dict(row) for row in (read_requests(status="pending") or []) if isinstance(row, dict)]
    except Exception:
        return []


def _format_pending_leave_message(rows: list[dict]) -> str:
    from services import workforce_profile_service

    lines = [f"🔴 WNIOSKI URLOPOWE DO AKCEPTACJI: {len(rows)}"]
    for row in rows[:4]:
        login = str(row.get("login") or "").strip()
        user = workforce_profile_service.get_user(login) or {"login": login}
        name = workforce_profile_service.display_name(user) or login or "Pracownik"
        start = str(row.get("date_start") or "").strip()
        end = str(row.get("date_end") or "").strip()
        if not start:
            dates = row.get("dates") if isinstance(row.get("dates"), list) else []
            start = str(dates[0])[:10] if dates else ""
            end = str(dates[-1])[:10] if dates else ""
        term = start if not end or end == start else f"{start}–{end}"
        lines.append(f"• {name}: {term or 'brak terminu'}")
    if len(rows) > 4:
        lines.append(f"• +{len(rows) - 4} kolejnych")
    lines.append("Profil → Brygadzista → Urlopy")
    return "\n".join(lines)


def _notify_pending_leaves(login: str, role: str) -> None:
    global _LAST_LEAVE_ALERT
    if _key(role) != "brygadzista":
        return
    rows = _pending_leave_rows()
    if not rows:
        return
    ids = tuple(
        sorted(
            str(row.get("id") or row.get("request_id") or f"{row.get('login')}:{row.get('created_at')}")
            for row in rows
        )
    )
    now = time.monotonic()
    previous = _LAST_LEAVE_ALERT
    if previous and previous[0] == _key(login) and previous[1] == ids and now - previous[2] < 5.0:
        return
    _LAST_LEAVE_ALERT = (_key(login), ids, now)
    try:
        from gui_notifications import show_notification

        show_notification(
            _format_pending_leave_message(rows),
            level="error",
            duration=30.0,
            blink=True,
        )
    except Exception:
        pass


def _install_profile_session_bridge() -> None:
    """Po poprawnym logowaniu rozpocznij heartbeat i kolejkuj alert urlopowy."""
    from services.profile_service import ProfileService
    from services import workforce_profile_service

    if getattr(ProfileService, "_wm_live_session_v1", False):
        return

    original_set = ProfileService.set_active_user
    original_clear = ProfileService.clear_active_user

    @classmethod
    def set_active_user(cls, login: str) -> None:
        original_set(login)
        login_text = str(login or "").strip()
        if not login_text or _key(login_text) in {"guest", "gość", "gosc"}:
            return
        try:
            user = workforce_profile_service.get_user(login_text) or {}
            role = str(user.get("rola") or user.get("role") or "")
        except Exception:
            role = ""
        try:
            import presence

            presence.start_session(login_text, role)
        except Exception:
            pass
        _notify_pending_leaves(login_text, role)

    @classmethod
    def clear_active_user(cls) -> None:
        try:
            active = str(cls.get_active_user() or "").strip()
            if active:
                import presence
                presence.end_session(active)
        except Exception:
            pass
        original_clear()

    ProfileService.set_active_user = set_active_user
    ProfileService.clear_active_user = clear_active_user
    ProfileService._wm_live_session_v1 = True


def _online_logins() -> set[str]:
    try:
        import presence

        rows, _path = presence.read_presence()
    except Exception:
        return set()
    return {
        _key(row.get("login"))
        for row in rows
        if isinstance(row, dict) and bool(row.get("online")) and _key(row.get("login"))
    }


def _decorate_online_column(panel) -> None:
    tree = getattr(panel, "_wm_attendance_tree", None)
    mapping = getattr(panel, "_wm_attendance_user_by_iid", {})
    if tree is None:
        return
    try:
        old_columns = list(tree.cget("columns") or ())
    except Exception:
        return
    if "wm_online" in old_columns:
        return
    insert_at = old_columns.index("today") + 1 if "today" in old_columns else min(3, len(old_columns))
    new_columns = list(old_columns)
    new_columns.insert(insert_at, "wm_online")
    try:
        tree.configure(columns=new_columns, displaycolumns=new_columns)
        tree.heading("wm_online", text="Aktywny WM")
        tree.column("wm_online", width=90, minwidth=82, anchor="center", stretch=False)
    except Exception:
        return

    online = _online_logins()
    for iid in tree.get_children(""):
        try:
            values = list(tree.item(iid, "values") or ())
            if len(values) != len(old_columns):
                continue
            login = str(mapping.get(iid, "") or "")
            values.insert(insert_at, "● online" if _key(login) in online else "—")
            tree.item(iid, values=values)
        except Exception:
            continue


def _install_attendance_online_column() -> None:
    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_attendance_online_v1", False):
        return
    original = cls._render_attendance

    def render_attendance(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        _decorate_online_column(self)
        return result

    cls._render_attendance = render_attendance
    cls._wm_attendance_online_v1 = True


def _selected_foreman_tab(panel) -> str:
    notebook = getattr(panel, "notebook", None)
    if notebook is None:
        return "Pulpit"
    try:
        return str(notebook.tab(notebook.select(), "text") or "Pulpit")
    except Exception:
        return "Pulpit"


def _render_selected_foreman_tab(panel) -> None:
    label = _selected_foreman_tab(panel)
    methods = {
        "Pulpit": "_render_dashboard",
        "Ruch WM": "_render_team",
        "Zespół": "_render_team",
        "Obecność": "_render_attendance",
        "Urlopy": "_render_leaves",
        "Użytkownicy": "_render_users",
        "Opinie": "_render_feedback",
        "Statystyki": "_render_stats",
        "Zadania": "_render_tasks",
        "Sprzęt": "_render_equipment",
    }
    method = getattr(panel, methods.get(label, "_render_dashboard"), None)
    if callable(method):
        method()


def _install_foreman_lazy_render() -> None:
    """Snapshot pozostaje wspólny, ale ciężkie GUI buduj tylko dla aktywnej podzakładki."""
    import gui_profile_foreman as foreman

    cls = foreman.ForemanProfilePanel
    if getattr(cls, "_wm_lazy_inner_tabs_v1", False):
        return
    original_build = cls._build

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            def on_tab(_event=None):
                try:
                    _render_selected_foreman_tab(self)
                except Exception as exc:
                    print(f"[WM-DBG][PROFILE][WARN] lazy foreman tab render failed: {exc!r}")

            notebook.bind("<<NotebookTabChanged>>", on_tab, add="+")
        return result

    def render_all(self) -> None:
        _render_selected_foreman_tab(self)

    cls._build = build
    cls._render_all = render_all
    cls._wm_lazy_inner_tabs_v1 = True


def _canonicalize_feedback_storage() -> bool:
    """Utrwal user_id/ID/status także dla starych opinii zapisanych przez gui_panel."""
    from services import feedback_service

    raw = feedback_service._read([])
    if isinstance(raw, dict):
        items = raw.get("items") or raw.get("opinie") or list(raw.values())
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    normalized = [
        feedback_service._normalize(item, idx)
        for idx, item in enumerate(items)
        if isinstance(item, dict)
    ]
    plain_items = [dict(item) for item in items if isinstance(item, dict)]
    if normalized == plain_items:
        return False
    feedback_service._write(normalized)
    return True


def _install_feedback_canonicalization() -> None:
    from services import feedback_service

    if getattr(feedback_service, "_wm_canonical_storage_v1", False):
        return
    original_list = feedback_service.list_feedback

    def list_feedback(*, login: str | None = None, status: str | None = None) -> list[dict]:
        try:
            _canonicalize_feedback_storage()
        except Exception:
            pass
        return original_list(login=login, status=status)

    feedback_service.list_feedback = list_feedback
    feedback_service._wm_canonical_storage_v1 = True


def _install_legacy_path_quieting() -> None:
    """Jeśli kanoniczne źródło istnieje, stare ścieżki są tylko archiwalne i nie są skanowane."""
    try:
        import dyspozycje_store

        if not getattr(dyspozycje_store, "_wm_skip_inert_legacy_v1", False):
            original_migrate = dyspozycje_store._migrate_legacy_if_needed

            def migrate_legacy_if_needed(target):
                try:
                    if target.exists():
                        return
                except Exception:
                    pass
                return original_migrate(target)

            dyspozycje_store._migrate_legacy_if_needed = migrate_legacy_if_needed
            dyspozycje_store._wm_skip_inert_legacy_v1 = True
    except Exception:
        pass

    try:
        from core import root_paths

        if not getattr(root_paths, "_wm_external_root_diag_v1", False):
            original_diag = root_paths.print_root_diagnostics
            original_get_app_root = root_paths.get_app_root

            def print_root_diagnostics(snapshot=None):
                if snapshot is None:
                    return original_diag(snapshot)
                # Snapshot już ma prawdziwy APP_ROOT. Podmieniamy get_app_root tylko
                # dla końcowego testu legacy APP/data, aby nie drukować trzech
                # ostrzeżeń o katalogu, który przy zewnętrznym WM_ROOT jest celowo nieaktywny.
                root_paths.get_app_root = lambda: root_paths.get_root_anchor()
                try:
                    return original_diag(snapshot)
                finally:
                    root_paths.get_app_root = original_get_app_root

            root_paths.print_root_diagnostics = print_root_diagnostics
            root_paths._wm_external_root_diag_v1 = True
    except Exception:
        pass


def install() -> None:
    global _INSTALLED
    _install_safe_panel_bindings()
    _install_profile_session_bridge()
    _install_feedback_canonicalization()
    _install_attendance_online_column()
    _install_foreman_lazy_render()
    _install_legacy_path_quieting()
    _INSTALLED = True


__all__ = [
    "install",
    "_format_pending_leave_message",
    "_canonicalize_feedback_storage",
    "_online_logins",
    "_decorate_online_column",
    "_render_selected_foreman_tab",
]
