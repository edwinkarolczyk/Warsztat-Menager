# version: 1.1
# Plik: foreman_shift_profiles_runtime.py
"""Spina grafik zmian, L4, aktualną pracę i Profile panelu brygadzisty.

Jedno źródło prawdy dla grafiku:
- shifts.modes[user_id]
- shifts.user_anchor[user_id] (poniedziałek pierwszego tygodnia cyklu)

Login jest tylko aliasem migracyjnym. Stare tryb_zmian / zmiana_plan /
rotacja_start w profiles.json są wejściem migracyjnym i są usuwane przy
kolejnym zapisie profili.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import tkinter as tk
from tkinter import ttk

from calendar_ui_runtime import open_date_picker
from config_manager import ConfigManager
from ui_context_help import add_help_button

logger = logging.getLogger(__name__)
_INSTALLED = False


def _monday(value: Any, *, fallback: date | None = None) -> date:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        raw = str(value or "").strip()
        try:
            parsed = date.fromisoformat(raw[:10])
        except Exception:
            parsed = fallback or date.today()
    return parsed - timedelta(days=parsed.weekday())


def _install_shifts() -> None:
    """Oznacz nowy silnik jako zainstalowany; logika mieszka już w core."""
    from grafiki import shifts_schedule as shifts

    if getattr(shifts, "_wm_user_anchor_installed", False):
        return
    if not all(
        hasattr(shifts, name)
        for name in ("get_user_schedule", "set_user_schedule", "_week_idx_for_user")
    ):
        raise RuntimeError("Brak kanonicznego silnika grafiku 3-tygodniowego.")
    shifts._user_week_idx = shifts._week_idx_for_user
    shifts._wm_user_anchor_installed = True


def _install_profile_settings() -> None:
    import ustawienia_uzytkownicy as profiles
    from grafiki import shifts_schedule as shifts
    from services import workforce_profile_service as workforce

    if getattr(profiles, "_wm_shift_source_installed", False):
        return

    original_save_users = profiles._save_users
    original_dialog_init = profiles.ProfileEditDialog.__init__
    original_save_now = profiles.SettingsProfilesTab._save_now

    profiles.ProfileEditDialog.SHIFT_MODES = [
        ("111", "111 — I / I / I (stała I zmiana)"),
        ("222", "222 — II / II / II (stała II zmiana)"),
        ("121", "121 — I / II / I (cykl 3 tygodnie)"),
        ("212", "212 — II / I / II (cykl 3 tygodnie)"),
    ]
    profiles.ProfileEditDialog.LEGACY_SHIFT_ALIASES = {
        "1111": "111",
        "2222": "222",
        "1212": "121",
        "2121": "212",
        "I": "111",
        "1": "111",
        "II": "222",
        "2": "222",
    }

    def _seed_user_id(seed: dict[str, Any], login: str) -> str:
        uid = str(seed.get("user_id") or "").strip()
        if not uid:
            legacy_id = str(seed.get("id") or "").strip()
            if legacy_id.upper().startswith("USR-"):
                uid = legacy_id
        if uid:
            return uid
        if login:
            try:
                current = workforce.get_user(login) or {}
                return str(current.get("user_id") or "").strip()
            except Exception:
                pass
        return login

    def _save_users(items: list[dict[str, Any]]) -> None:
        cleaned: list[dict[str, Any]] = []
        schedules: list[dict[str, str]] = []
        for source in items:
            row = dict(source)
            login = str(row.get("login") or "").strip()
            old_login = str(row.pop("_wm_shift_old_login", "") or "").strip()
            requested_mode = str(
                row.pop("_wm_shift_mode", "")
                or row.get("tryb_zmian")
                or row.get("zmiana_plan")
                or ""
            ).strip()
            requested_anchor = str(
                row.pop("_wm_shift_anchor", "")
                or row.get("rotacja_start")
                or row.get("shift_start")
                or ""
            ).strip()
            uid_hint = str(row.pop("_wm_shift_user_id", "") or row.get("user_id") or "").strip()
            schedules.append(
                {
                    "login": login,
                    "old_login": old_login,
                    "user_id": uid_hint,
                    "mode": requested_mode,
                    "anchor": requested_anchor,
                }
            )
            row.pop("tryb_zmian", None)
            row.pop("zmiana_plan", None)
            row.pop("rotacja_start", None)
            row.pop("shift_start", None)
            cleaned.append(row)

        original_save_users(cleaned)

        try:
            normalized = workforce.ensure_profile_schema()
        except Exception:
            normalized = cleaned
        id_by_login = {
            str(row.get("login") or "").strip().casefold(): str(row.get("user_id") or "").strip()
            for row in normalized
            if isinstance(row, dict)
        }

        data = shifts._load_modes()
        modes = dict(data.get("modes") or {})
        anchors = dict(data.get("user_anchor") or {})
        default_anchor = str(data.get("anchor_monday") or "2025-01-06")

        for request in schedules:
            login = request["login"]
            old_login = request["old_login"]
            stable_id = (
                id_by_login.get(login.casefold(), "")
                or request["user_id"]
                or login
            )
            if not stable_id:
                continue

            raw_mode = (
                request["mode"]
                or modes.get(stable_id)
                or (modes.get(login) if login else None)
                or (modes.get(old_login) if old_login else None)
                or "111"
            )
            mode = shifts._normalize_mode(raw_mode)
            raw_anchor = (
                request["anchor"]
                or anchors.get(stable_id)
                or (anchors.get(login) if login else None)
                or (anchors.get(old_login) if old_login else None)
                or default_anchor
            )
            modes[stable_id] = mode
            anchors[stable_id] = _monday(raw_anchor, fallback=date(2025, 1, 6)).isoformat()

            for legacy_key in (login, old_login):
                if legacy_key and legacy_key != stable_id:
                    modes.pop(legacy_key, None)
                    anchors.pop(legacy_key, None)

        cfg = ConfigManager()
        cfg.set("shifts.patterns", shifts._available_patterns())
        cfg.set("shifts.modes", modes)
        cfg.set("shifts.user_anchor", anchors)
        cfg.save_all()

    def _dialog_init(self, master: tk.Misc, seed=None, on_ok=None) -> None:
        original_seed = dict(seed or {})
        login = str(original_seed.get("login") or "").strip()
        schedule_key = _seed_user_id(original_seed, login)
        fallback_mode = str(
            original_seed.get("_wm_shift_mode")
            or original_seed.get("tryb_zmian")
            or original_seed.get("zmiana_plan")
            or "111"
        ).strip()
        mode, stored_anchor = shifts.get_user_schedule(schedule_key or login, fallback_mode)
        prepared = dict(original_seed)
        prepared["tryb_zmian"] = mode
        prepared["zmiana_plan"] = mode
        anchor_for_dialog = _monday(
            original_seed.get("_wm_shift_anchor")
            or stored_anchor
            or original_seed.get("rotacja_start")
            or original_seed.get("shift_start")
            or date.today()
        ).isoformat()

        def _wrapped_ok(item: dict[str, Any]):
            result = dict(item)
            selected_mode = str(
                result.pop("tryb_zmian", "")
                or result.pop("zmiana_plan", "")
                or mode
            ).strip()
            result.pop("zmiana_plan", None)
            result.pop("rotacja_start", None)
            result.pop("shift_start", None)
            result["_wm_shift_mode"] = shifts._normalize_mode(selected_mode)
            result["_wm_shift_anchor"] = _monday(
                self.v_shift_anchor.get(), fallback=date.today()
            ).isoformat()
            if schedule_key:
                result["_wm_shift_user_id"] = schedule_key
            new_login = str(result.get("login") or "").strip()
            if login and new_login.casefold() != login.casefold():
                result["_wm_shift_old_login"] = login
            return on_ok(result) if on_ok else None

        original_dialog_init(self, master, seed=prepared, on_ok=_wrapped_ok)
        self.v_shift_anchor = tk.StringVar(value=anchor_for_dialog)
        try:
            self.geometry("560x350")
        except Exception:
            pass

        frames = [child for child in self.winfo_children() if hasattr(child, "grid_slaves")]
        if not frames:
            return
        frame = frames[0]
        frame.columnconfigure(1, weight=1)

        for child in frame.winfo_children():
            try:
                info = child.grid_info()
                if info and int(info.get("row", -1)) == 6 and isinstance(child, ttk.Frame):
                    child.grid_configure(row=7)
            except Exception:
                pass

        add_help_button(
            frame,
            "Wzorzec ma dokładnie trzy tygodnie i potem zaczyna się od początku. "
            "121 oznacza I → II → I, a 212 oznacza II → I → II.",
            row=5,
            column=2,
            sticky="w",
            padx=(5, 0),
        )

        ttk.Label(frame, text="Data kotwiczna:").grid(row=6, column=0, sticky="w", pady=4)
        holder = ttk.Frame(frame)
        holder.grid(row=6, column=1, sticky="ew", pady=4)
        holder.columnconfigure(0, weight=1)
        entry = ttk.Entry(holder, textvariable=self.v_shift_anchor, state="readonly")
        entry.grid(row=0, column=0, sticky="ew")

        def _pick_anchor() -> None:
            try:
                initial = date.fromisoformat(str(self.v_shift_anchor.get())[:10])
            except Exception:
                initial = date.today()

            def _selected(picked: date) -> None:
                self.v_shift_anchor.set(_monday(picked).isoformat())

            open_date_picker(
                self,
                initial=initial,
                on_select=_selected,
                title="Data kotwiczna — tydzień 1",
            )

        entry.bind("<Button-1>", lambda _event: _pick_anchor())
        ttk.Button(holder, text="📅", width=3, command=_pick_anchor).grid(
            row=0, column=1, padx=(4, 0)
        )
        add_help_button(
            frame,
            "Poniedziałek pierwszego tygodnia cyklu tego pracownika. "
            "Każdy pracownik ma własną datę kotwiczną.",
            row=6,
            column=2,
            sticky="w",
            padx=(5, 0),
        )

    def _save_now(self) -> None:
        original_save_now(self)
        try:
            self._load_from_storage()
        except Exception:
            pass

    profiles._save_users = _save_users
    profiles.ProfileEditDialog.__init__ = _dialog_init
    profiles.SettingsProfilesTab._save_now = _save_now
    profiles._wm_shift_source_installed = True


def _install_l4_calendar() -> None:
    import gui_profile_calendar as cal

    if getattr(cal, "_wm_l4_calendar_installed", False):
        return

    def _open_l4_dialog(panel) -> None:
        win = cal.tk.Toplevel(panel)
        win.title("Dodaj L4")
        try:
            win.transient(panel.winfo_toplevel())
            win.grab_set()
        except Exception:
            pass
        frame = cal.ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        labels: list[str] = []
        login_by_label: dict[str, str] = {}
        for user in cal._users():
            login = str(user.get("login") or "").strip()
            label = f"{cal._display_name(user)} (@{login})"
            labels.append(label)
            login_by_label[label] = login
        worker_var = cal.tk.StringVar(value=labels[0] if labels else "")
        start_var = cal.tk.StringVar(value=date.today().isoformat())
        end_var = cal.tk.StringVar(value=date.today().isoformat())
        note_var = cal.tk.StringVar(value="")
        cal.ttk.Label(frame, text="Pracownik:").grid(row=0, column=0, sticky="w", pady=4)
        cal.ttk.Combobox(
            frame, textvariable=worker_var, values=labels,
            state="readonly", width=34,
        ).grid(row=0, column=1, sticky="ew", pady=4)

        def _date_control(row: int, label: str, variable, title: str) -> None:
            cal.ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            holder = cal.ttk.Frame(frame)
            holder.grid(row=row, column=1, sticky="ew", pady=4)
            holder.columnconfigure(0, weight=1)
            entry = cal.ttk.Entry(holder, textvariable=variable, state="readonly")
            entry.grid(row=0, column=0, sticky="ew")

            def _pick() -> None:
                try:
                    initial = date.fromisoformat(str(variable.get())[:10])
                except Exception:
                    initial = date.today()
                open_date_picker(
                    win, initial=initial,
                    on_select=lambda picked: variable.set(picked.isoformat()),
                    title=title,
                )

            entry.bind("<Button-1>", lambda _event: _pick())
            cal.ttk.Button(holder, text="📅", width=3, command=_pick).grid(
                row=0, column=1, padx=(4, 0)
            )

        _date_control(1, "Od:", start_var, "L4 — data od")
        _date_control(2, "Do:", end_var, "L4 — data do")
        cal.ttk.Label(frame, text="Uwagi:").grid(row=3, column=0, sticky="w", pady=4)
        cal.ttk.Entry(frame, textvariable=note_var).grid(row=3, column=1, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)

        def save() -> None:
            login = login_by_label.get(worker_var.get(), "")
            try:
                days = cal.dates_from_range(start_var.get(), end_var.get(), include_sundays=True)
                added = cal.add_l4(login, days, cal._actor_login(panel), note_var.get())
            except Exception as exc:
                cal.messagebox.showerror("L4", f"Nie udało się dodać L4:\n{exc}", parent=win)
                return
            cal.messagebox.showinfo(
                "L4", f"Dodano L4: {added} dni kalendarzowych.", parent=win
            )
            win.destroy()
            panel.refresh_data()
            cal._emit_leaves_update(panel)

        actions = cal.ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        cal.ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
        cal.ttk.Button(actions, text="Dodaj L4", command=save).pack(
            side="right", padx=(0, 8)
        )

    cal._open_l4_dialog = _open_l4_dialog
    cal._wm_l4_calendar_installed = True


def _install_foreman_stats() -> None:
    import services.foreman_stats_service as stats
    from grafiki import shifts_schedule as shifts

    if getattr(stats, "_wm_shift_work_installed", False):
        return
    original_build_snapshot = stats.build_snapshot

    def _shift_for_login(login: str, today: date) -> str:
        try:
            if today.weekday() == 6:
                return "Wolne"
            mode = shifts._user_mode(login)
            slot = shifts._slot_for_mode(mode, shifts._user_week_idx(login, today))
            if today.weekday() == 5:
                slot = "RANO"
            times = shifts._shift_times()
            if slot == "RANO":
                return f"1 ({times['R_START'].strftime('%H:%M')}–{times['R_END'].strftime('%H:%M')})"
            return f"2 ({times['P_START'].strftime('%H:%M')}–{times['P_END'].strftime('%H:%M')})"
        except Exception:
            return "—"

    def _machine_current_work() -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for machine in stats._machine_records():
            mid = stats._text(
                machine.get("nr_ewid") or machine.get("nr")
                or machine.get("numer") or machine.get("id")
            )
            reviews = machine.get("reviews") if isinstance(machine.get("reviews"), list) else []
            for review in reviews:
                if not isinstance(review, dict):
                    continue
                if stats._norm(review.get("status")) not in stats._IN_PROGRESS:
                    continue
                workers = stats._as_people(review.get("started_by"))
                if not workers:
                    continue
                kind = stats._text(review.get("type")) or "Przegląd / serwis"
                work = f"Maszyna {mid} — {kind}" if mid else f"Maszyna — {kind}"
                for worker in workers:
                    key = stats._norm(worker)
                    if key:
                        bucket = result.setdefault(key, [])
                        if work not in bucket:
                            bucket.append(work)
        return result

    def build_snapshot(period: str = "month") -> dict[str, Any]:
        snapshot = original_build_snapshot(period)
        machine_work = _machine_current_work()
        for row in snapshot.get("team") or []:
            items = list(machine_work.get(stats._norm(row.get("login")), []))
            existing = stats._text(row.get("current_work"))
            if existing and existing != "—":
                items.append(existing)
            unique: list[str] = []
            seen: set[str] = set()
            for item in items:
                key = item.casefold()
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            if not unique:
                row["current_work"] = "—"
            elif len(unique) == 1:
                row["current_work"] = unique[0]
            else:
                row["current_work"] = f"{unique[0]} + {len(unique) - 1} inne"
        return snapshot

    stats._shift_for_login = _shift_for_login
    stats.build_snapshot = build_snapshot
    stats._wm_shift_work_installed = True


def _install_foreman_profiles() -> None:
    import gui_profile_foreman as foreman
    from services.profile_service import ProfileService
    from ustawienia_uzytkownicy import SettingsProfilesTab

    if getattr(foreman.ForemanProfilePanel, "_wm_profiles_tab_installed", False):
        return
    original_build = foreman.ForemanProfilePanel._build

    def _build(self) -> None:
        original_build(self)
        if "Profile" in self._tabs:
            return
        try:
            active_login = str(ProfileService.ensure_active_user_or_none() or "").strip()
        except Exception:
            active_login = ""
        try:
            self.notebook.login = active_login
        except Exception:
            pass
        profiles_tab = SettingsProfilesTab(self.notebook)
        self.notebook.add(profiles_tab, text="Profile")
        self._tabs["Profile"] = profiles_tab
        self._wm_profiles_tab = profiles_tab

    foreman.ForemanProfilePanel._build = _build
    foreman.ForemanProfilePanel._wm_profiles_tab_installed = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _install_shifts()
    _install_profile_settings()
    _install_l4_calendar()
    _install_foreman_stats()
    _install_foreman_profiles()
    _INSTALLED = True
    print("[WM-DBG][FOREMAN] shifts, L4 calendar, machine work and Profile tab installed")


__all__ = ["install"]
