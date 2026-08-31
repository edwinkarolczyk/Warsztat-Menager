# version: 1.0
# Plik: foreman_shift_profiles_runtime.py
"""Spina grafik zmian, L4, aktualną pracę i Profile panelu brygadzisty.

Jedno źródło prawdy dla zmian:
- shifts.modes[login]
- shifts.user_anchor[login] (poniedziałek tygodnia bazowego)

Stare tryb_zmian / zmiana_plan w profiles.json są tylko wejściem migracyjnym
oraz są usuwane przy kolejnym zapisie profili.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import tkinter as tk
from tkinter import ttk

from calendar_ui_runtime import open_date_picker
from config_manager import ConfigManager

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
    from grafiki import shifts_schedule as shifts

    if getattr(shifts, "_wm_user_anchor_installed", False):
        return

    original_load_modes = shifts._load_modes

    def _load_modes() -> dict:
        data = dict(original_load_modes() or {})
        raw = ConfigManager().get("shifts.user_anchor", {})
        data["user_anchor"] = dict(raw) if isinstance(raw, dict) else {}
        return data

    def _user_anchor_monday(user_id: str) -> date:
        data = _load_modes()
        anchors = data.get("user_anchor") or {}
        raw = anchors.get(str(user_id)) or data.get("anchor_monday") or "2025-01-06"
        return _monday(raw, fallback=date(2025, 1, 6))

    def _user_week_idx(user_id: str, day: date) -> int:
        week_start = day - timedelta(days=day.weekday())
        return (week_start - _user_anchor_monday(user_id)).days // 7

    def get_user_schedule(user_id: str, fallback_mode: str = "") -> tuple[str, str]:
        uid = str(user_id or "").strip()
        data = _load_modes()
        modes = data.get("modes") or {}
        mode = str(modes.get(uid) or fallback_mode or "").strip()
        if not mode:
            try:
                mode = str(shifts._user_mode(uid) or "111").strip()
            except Exception:
                mode = "111"
        if mode not in shifts._available_patterns(data):
            mode = "111"
        return mode, _user_anchor_monday(uid).isoformat()

    def set_user_schedule(user_id: str, mode: str, anchor_date: str | date) -> None:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id is required")
        data = _load_modes()
        patterns = shifts._available_patterns(data)
        if mode not in patterns:
            raise ValueError(f"mode must be one of: {', '.join(sorted(patterns))}")
        modes = dict(data.get("modes") or {})
        anchors = dict(data.get("user_anchor") or {})
        monday = _monday(anchor_date)
        modes[uid] = mode
        anchors[uid] = monday.isoformat()
        cfg = ConfigManager()
        cfg.set("shifts.modes", modes)
        cfg.set("shifts.user_anchor", anchors)
        cfg.save_all()
        print(f"[WM-DBG][SHIFTS] schedule saved: {uid} -> {mode}, anchor={monday.isoformat()}")

    def set_user_mode(user_id: str, mode: str) -> None:
        _old_mode, anchor = get_user_schedule(user_id)
        set_user_schedule(user_id, mode, anchor)

    def who_is_on_now(now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        times = shifts._shift_times()
        slot = None
        if times["R_START"] <= now.time() < times["R_END"]:
            slot = "RANO"
        elif times["P_START"] <= now.time() < times["P_END"]:
            slot = "POPO"
        if slot is None:
            return {"slot": None, "users": []}
        users = []
        for user in shifts._load_users():
            if not user.get("active"):
                continue
            uid = user["id"]
            widx = _user_week_idx(uid, now.date())
            if shifts._slot_for_mode(shifts._user_mode(uid), widx) == slot:
                users.append(user["name"])
        return {"slot": slot, "users": users}

    def week_matrix(start_date: date) -> dict[str, Any]:
        week_start = start_date - timedelta(days=start_date.weekday())
        times = shifts._shift_times()
        rows: list[dict] = []
        for user in shifts._load_users():
            if not user.get("active"):
                continue
            uid = user["id"]
            mode = shifts._user_mode(uid)
            slot = shifts._slot_for_mode(mode, _user_week_idx(uid, week_start))
            days = []
            for idx in range(7):
                current = week_start + timedelta(days=idx)
                weekday = current.weekday()
                if weekday == 6:
                    continue
                if weekday == 5:
                    code = "R"
                else:
                    code = "R" if slot == "RANO" else "P"
                start = times["R_START"] if code == "R" else times["P_START"]
                end = times["R_END"] if code == "R" else times["P_END"]
                days.append({
                    "date": current.strftime("%Y-%m-%d"),
                    "dow": current.strftime("%a"),
                    "shift": code,
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                })
            rows.append({
                "user": user["name"], "user_id": uid, "mode": mode,
                "slot": slot, "days": days,
            })
        return {"week_start": week_start.strftime("%Y-%m-%d"), "rows": rows}

    shifts._load_modes = _load_modes
    shifts._user_anchor_monday = _user_anchor_monday
    shifts._user_week_idx = _user_week_idx
    shifts.get_user_schedule = get_user_schedule
    shifts.set_user_schedule = set_user_schedule
    shifts.set_user_mode = set_user_mode
    shifts.who_is_on_now = who_is_on_now
    shifts.week_matrix = week_matrix
    shifts._wm_user_anchor_installed = True
    exported = list(getattr(shifts, "__all__", []))
    for name in ("get_user_schedule", "set_user_schedule"):
        if name not in exported:
            exported.append(name)
    shifts.__all__ = exported


def _install_profile_settings() -> None:
    import ustawienia_uzytkownicy as profiles
    from grafiki import shifts_schedule as shifts

    if getattr(profiles, "_wm_shift_source_installed", False):
        return

    original_save_users = profiles._save_users
    original_dialog_init = profiles.ProfileEditDialog.__init__
    original_save_now = profiles.SettingsProfilesTab._save_now

    def _explicit_anchor(login: str) -> str:
        anchors = shifts._load_modes().get("user_anchor") or {}
        return str(anchors.get(login) or "").strip() if login else ""

    def _save_users(items: list[dict[str, Any]]) -> None:
        cfg = ConfigManager()
        data = shifts._load_modes()
        modes = dict(data.get("modes") or {})
        anchors = dict(data.get("user_anchor") or {})
        patterns = shifts._available_patterns(data)
        default_anchor = str(data.get("anchor_monday") or "2025-01-06")
        cleaned: list[dict[str, Any]] = []
        for source in items:
            row = dict(source)
            login = str(row.get("login") or "").strip()
            old_login = str(row.pop("_wm_shift_old_login", "") or "").strip()
            mode = str(
                row.pop("_wm_shift_mode", "")
                or row.get("tryb_zmian")
                or row.get("zmiana_plan")
                or modes.get(login)
                or "111"
            ).strip()
            anchor_raw = row.pop("_wm_shift_anchor", "") or anchors.get(login) or default_anchor
            if login:
                if mode not in patterns:
                    mode = "111"
                modes[login] = mode
                anchors[login] = _monday(anchor_raw).isoformat()
            if old_login and old_login.casefold() != login.casefold():
                modes.pop(old_login, None)
                anchors.pop(old_login, None)
            row.pop("tryb_zmian", None)
            row.pop("zmiana_plan", None)
            cleaned.append(row)
        cfg.set("shifts.modes", modes)
        cfg.set("shifts.user_anchor", anchors)
        cfg.save_all()
        original_save_users(cleaned)

    def _dialog_init(self, master: tk.Misc, seed=None, on_ok=None) -> None:
        original_seed = dict(seed or {})
        login = str(original_seed.get("login") or "").strip()
        fallback_mode = str(
            original_seed.get("_wm_shift_mode")
            or original_seed.get("tryb_zmian")
            or original_seed.get("zmiana_plan")
            or ""
        ).strip()
        mode, _stored_anchor = shifts.get_user_schedule(login, fallback_mode or "111")
        prepared = dict(original_seed)
        prepared["tryb_zmian"] = mode
        prepared["zmiana_plan"] = mode
        anchor_for_dialog = str(
            original_seed.get("_wm_shift_anchor")
            or _explicit_anchor(login)
            or date.today().isoformat()
        ).strip()

        def _wrapped_ok(item: dict[str, Any]):
            result = dict(item)
            selected_mode = str(
                result.pop("tryb_zmian", "")
                or result.pop("zmiana_plan", "")
                or mode
            ).strip()
            result.pop("zmiana_plan", None)
            result["_wm_shift_mode"] = selected_mode or "111"
            result["_wm_shift_anchor"] = str(self.v_shift_anchor.get() or anchor_for_dialog).strip()
            new_login = str(result.get("login") or "").strip()
            if login and new_login.casefold() != login.casefold():
                result["_wm_shift_old_login"] = login
            return on_ok(result) if on_ok else None

        original_dialog_init(self, master, seed=prepared, on_ok=_wrapped_ok)
        self.v_shift_anchor = tk.StringVar(value=anchor_for_dialog)
        try:
            self.geometry("500x350")
        except Exception:
            pass
        frames = [child for child in self.winfo_children() if hasattr(child, "grid_slaves")]
        if not frames:
            return
        frame = frames[0]
        for child in frame.winfo_children():
            try:
                if str(child.cget("text")) == "Tryb zmian:":
                    child.configure(text="Jak pracuje w tym tygodniu:")
            except Exception:
                pass
        for child in frame.winfo_children():
            try:
                info = child.grid_info()
                if info and int(info.get("row", -1)) == 6 and isinstance(child, ttk.Frame):
                    child.grid_configure(row=7)
            except Exception:
                pass
        ttk.Label(frame, text="Data z tego tygodnia:").grid(row=6, column=0, sticky="w", pady=4)
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
            open_date_picker(
                self, initial=initial,
                on_select=lambda picked: self.v_shift_anchor.set(picked.isoformat()),
                title="Tydzień bazowy zmiany",
            )

        entry.bind("<Button-1>", lambda _event: _pick_anchor())
        ttk.Button(holder, text="📅", width=3, command=_pick_anchor).grid(row=0, column=1, padx=(4, 0))

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
            cal.ttk.Button(holder, text="📅", width=3, command=_pick).grid(row=0, column=1, padx=(4, 0))

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
            cal.messagebox.showinfo("L4", f"Dodano L4: {added} dni kalendarzowych.", parent=win)
            win.destroy()
            panel.refresh_data()
            cal._emit_leaves_update(panel)

        actions = cal.ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        cal.ttk.Button(actions, text="Anuluj", command=win.destroy).pack(side="right")
        cal.ttk.Button(actions, text="Dodaj L4", command=save).pack(side="right", padx=(0, 8))

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
    print("[WM-DBG][FOREMAN] shifts source, L4 calendar, machine work and Profile tab installed")


__all__ = ["install"]
