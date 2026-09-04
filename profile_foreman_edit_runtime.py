# version: 1.0
"""Minimalna warstwa edycyjna Profile dla brygadzisty.

Nie przebudowuje głównej karty Profilu. Dodaje realną edycję do istniejących
wejść: Zespół, Użytkownicy, Urlopy i Szczegóły pracownika.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from config_manager import ConfigManager
from core import root_paths
from services import attendance_service, leave_balance_service, workforce_profile_service
from ui_context_help import add_help_button

_INSTALLED = False


def _active_login(owner=None) -> str:
    try:
        from services.profile_service import ProfileService
        value = str(ProfileService.ensure_active_user_or_none() or "").strip()
        if value:
            return value
    except Exception:
        pass
    return str(getattr(owner, "login", "") or getattr(getattr(owner, "owner", None), "login", "") or "").strip()


def _is_foreman(owner=None) -> bool:
    return workforce_profile_service.is_foreman(_active_login(owner))


def _audit_path() -> Path:
    try:
        return root_paths.get_data_root() / "profile_admin_audit.json"
    except Exception:
        return Path("data") / "profile_admin_audit.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _audit(login: str, action: str, actor: str, *, before: Any = None, after: Any = None, note: str = "") -> None:
    rows = _read_json(_audit_path(), [])
    if not isinstance(rows, list):
        rows = []
    user = workforce_profile_service.get_user(login) or {}
    rows.append({
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "user_id": str(user.get("user_id") or ""),
        "login": str(login or ""),
        "action": str(action or ""),
        "actor": str(actor or ""),
        "before": before,
        "after": after,
        "note": str(note or "").strip(),
    })
    _write_json(_audit_path(), rows[-5000:])


def _profile_audit(login: str, limit: int = 250) -> list[dict]:
    user = workforce_profile_service.get_user(login) or {}
    uid = str(user.get("user_id") or "").strip().casefold()
    key = str(login or "").strip().casefold()
    rows = _read_json(_audit_path(), [])
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_uid = str(row.get("user_id") or "").strip().casefold()
        row_login = str(row.get("login") or "").strip().casefold()
        if (uid and row_uid == uid) or row_login == key:
            out.append(dict(row))
    return out[-max(1, int(limit)):]


def _float(value: Any, label: str) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception as exc:
        raise ValueError(f"Pole '{label}' musi być liczbą.") from exc


def _parse_carryover(text: str, year: int) -> dict[int, float]:
    """Format: 2024=2; 2025=4."""
    raw = str(text or "").strip()
    if not raw:
        return {}
    out: dict[int, float] = {}
    for part in raw.replace(",", ";").split(";"):
        item = part.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("Zaległy urlop wpisz np. 2025=4; 2024=2")
        source, amount = item.split("=", 1)
        source_year = int(source.strip())
        if source_year >= int(year):
            raise ValueError("Rok urlopu zaległego musi być wcześniejszy od roku rozliczenia.")
        value = _float(amount.strip(), "zaległy urlop")
        if value < 0:
            raise ValueError("Zaległy urlop nie może być ujemny.")
        if value:
            out[source_year] = value
    return out


def _format_carryover(balance: dict, year: int) -> str:
    buckets = balance.get("buckets") if isinstance(balance, dict) else {}
    if not isinstance(buckets, dict):
        return ""
    parts = []
    for source, value in sorted(buckets.items(), key=lambda item: int(item[0])):
        try:
            source_year = int(source)
            amount = float(value)
        except Exception:
            continue
        if source_year < int(year) and amount > 0:
            parts.append(f"{source_year}={amount:g}")
    return "; ".join(parts)


def _migrate_shift_login(old_login: str, new_login: str) -> None:
    old = str(old_login or "").strip()
    new = str(new_login or "").strip()
    if not old or not new or old.casefold() == new.casefold():
        return
    cfg = ConfigManager()
    changed = False
    for key in ("shifts.modes", "shifts.user_anchor"):
        raw = cfg.get(key, {})
        if not isinstance(raw, dict):
            continue
        data = dict(raw)
        value = None
        matched_key = None
        for item_key in list(data):
            if str(item_key).casefold() == old.casefold():
                matched_key = item_key
                value = data[item_key]
                break
        if matched_key is not None:
            data.pop(matched_key, None)
            data[new] = value
            cfg.set(key, data)
            changed = True
    if changed:
        cfg.save_all()


def _save_profile(login: str, values: dict, actor: str) -> str:
    current = workforce_profile_service.get_user(login)
    if not current:
        raise ValueError("Nie znaleziono profilu pracownika.")
    before = dict(current)
    new_login = str(values.get("login") or login).strip()
    if not new_login:
        raise ValueError("Login jest wymagany.")
    other = workforce_profile_service.get_user(new_login)
    if other and str(other.get("user_id") or "") != str(current.get("user_id") or ""):
        raise ValueError("Taki login już istnieje.")

    updated = dict(current)
    updated.update(values)
    updated["login"] = new_login
    updated["user_id"] = current.get("user_id")
    status = str(updated.get("status") or "aktywny").strip().casefold()
    updated["active"] = status not in {"zablokowany", "nieaktywny", "dezaktywowany"}
    saved = workforce_profile_service.save_user(updated, actor=actor)
    _migrate_shift_login(login, new_login)
    _audit(new_login, "profil", actor, before=before, after=saved, note="Edycja danych pracownika")
    return new_login


def _reset_pin(login: str, new_pin: str, actor: str) -> None:
    pin = str(new_pin or "").strip()
    if not pin.isdigit() or len(pin) < 4:
        raise ValueError("Nowy PIN musi mieć co najmniej 4 cyfry.")
    users = workforce_profile_service.list_users()
    target = workforce_profile_service.get_user(login) or {}
    target_uid = str(target.get("user_id") or "")
    found = False
    for row in users:
        if target_uid and str(row.get("user_id") or "") == target_uid:
            row["pin"] = pin
            found = True
            break
        if str(row.get("login") or "").strip().casefold() == str(login).strip().casefold():
            row["pin"] = pin
            found = True
            break
    if not found:
        raise ValueError("Nie znaleziono użytkownika.")
    workforce_profile_service.write_users(users)
    _audit(login, "reset_pin", actor, before="***", after="***", note="Reset PIN")


def _field(parent, row: int, label: str, variable: tk.Variable, *, readonly: bool = False, help_text: str = "") -> ttk.Entry:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
    entry = ttk.Entry(parent, textvariable=variable, state="readonly" if readonly else "normal")
    entry.grid(row=row, column=1, sticky="ew", pady=4)
    if help_text:
        add_help_button(parent, help_text, row=row, column=2, padx=(6, 0), sticky="w")
    return entry


def _actor_or_error(owner) -> str:
    actor = _active_login(owner)
    if not actor or not workforce_profile_service.is_foreman(actor):
        raise PermissionError("Tę operację może wykonać tylko Brygadzista.")
    return actor


def open_employee_editor(owner, login: str, *, initial_tab: str = "Dane", on_saved: Callable[[], None] | None = None) -> None:
    actor = _actor_or_error(owner)
    state = {"login": str(login or "").strip()}
    user = workforce_profile_service.get_user(state["login"])
    if not user:
        messagebox.showerror("Profil", "Nie znaleziono pracownika.", parent=owner.winfo_toplevel())
        return

    win = tk.Toplevel(owner)
    win.title(f"Profil pracownika — {workforce_profile_service.display_name(user)}")
    win.geometry("980x650")
    try:
        win.transient(owner.winfo_toplevel())
    except Exception:
        pass

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    frames: dict[str, ttk.Frame] = {}
    for name in ("Dane", "Obecność", "Urlopy", "Grafik", "Uprawnienia", "Historia", "Więcej"):
        frame = ttk.Frame(nb, padding=12)
        nb.add(frame, text=name)
        frames[name] = frame

    # DANE
    data = frames["Dane"]
    data.columnconfigure(1, weight=1)
    v_uid = tk.StringVar(value=str(user.get("user_id") or ""))
    v_login = tk.StringVar(value=str(user.get("login") or ""))
    v_first = tk.StringVar(value=str(user.get("imie") or ""))
    v_last = tk.StringVar(value=str(user.get("nazwisko") or ""))
    v_role = tk.StringVar(value=str(user.get("rola") or user.get("role") or "operator"))
    v_status = tk.StringVar(value=str(user.get("status") or ("aktywny" if user.get("active", True) else "zablokowany")))
    v_from = tk.StringVar(value=str(user.get("zatrudniony_od") or ""))
    v_to = tk.StringVar(value=str(user.get("zatrudniony_do") or ""))
    v_phone = tk.StringVar(value=str(user.get("telefon") or ""))
    v_email = tk.StringVar(value=str(user.get("email") or ""))
    _field(data, 0, "User ID:", v_uid, readonly=True, help_text="Techniczny identyfikator pracownika jest stały. Brygadzista może zmieniać dane profilu, ale nie ten identyfikator.")
    _field(data, 1, "Login:", v_login, help_text="Login może zmienić Brygadzista. WM zachowuje stały User ID i przenosi ustawienia grafiku na nowy login.")
    _field(data, 2, "Imię:", v_first)
    _field(data, 3, "Nazwisko:", v_last)
    ttk.Label(data, text="Rola:").grid(row=4, column=0, sticky="w", pady=4)
    ttk.Combobox(data, textvariable=v_role, values=("administrator", "kierownik", "brygadzista", "operator", "student", "sezonowiec", "guest"), state="readonly").grid(row=4, column=1, sticky="ew", pady=4)
    ttk.Label(data, text="Status:").grid(row=5, column=0, sticky="w", pady=4)
    ttk.Combobox(data, textvariable=v_status, values=("aktywny", "zablokowany", "nieaktywny"), state="readonly").grid(row=5, column=1, sticky="ew", pady=4)
    _field(data, 6, "Zatrudniony od:", v_from, help_text="Data w formacie RRRR-MM-DD. Pozostaw puste, jeśli data nie jest znana.")
    _field(data, 7, "Zatrudniony do:", v_to, help_text="Uzupełnij przy zakończeniu zatrudnienia. Historia pracownika pozostanie w WM.")
    _field(data, 8, "Telefon:", v_phone)
    _field(data, 9, "E-mail:", v_email)

    def save_data() -> None:
        old_login = state["login"]
        try:
            new_login = _save_profile(old_login, {
                "login": v_login.get().strip(), "imie": v_first.get().strip(), "nazwisko": v_last.get().strip(),
                "rola": v_role.get().strip(), "status": v_status.get().strip(),
                "zatrudniony_od": v_from.get().strip(), "zatrudniony_do": v_to.get().strip(),
                "telefon": v_phone.get().strip(), "email": v_email.get().strip(),
            }, actor)
        except Exception as exc:
            messagebox.showerror("Profil", f"Nie udało się zapisać danych:\n{exc}", parent=win)
            return
        state["login"] = new_login
        v_login.set(new_login)
        messagebox.showinfo("Profil", "Zapisano dane pracownika.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    row_actions = ttk.Frame(data)
    row_actions.grid(row=10, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(row_actions, text="Zapisz dane", command=save_data).pack(side="right")
    add_help_button(row_actions, "Zapisuje dane tego pracownika. Każda zmiana wykonana przez Brygadzistę trafia do Historii.").pack(side="right", padx=(0, 6))

    # OBECNOŚĆ
    att = frames["Obecność"]
    att.columnconfigure(1, weight=1)
    a_date = tk.StringVar(value=date.today().isoformat())
    a_slot = tk.StringVar(value="RANO")
    a_day = tk.StringVar(value="1")
    a_ot_on = tk.BooleanVar(value=False)
    a_ot_hours = tk.StringVar(value="0")
    a_ot_type = tk.StringVar(value="zwykle")
    a_note = tk.StringVar(value="")
    _field(att, 0, "Data:", a_date)
    ttk.Label(att, text="Zmiana:").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Combobox(att, textvariable=a_slot, values=("RANO", "POPO"), state="readonly").grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Label(att, text="Dniówka:").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Combobox(att, textvariable=a_day, values=("0", "0.5", "1"), state="readonly").grid(row=2, column=1, sticky="ew", pady=4)
    add_help_button(att, "Brygadzista może ustawić 0, 0,5 lub 1 dniówki. Ręczna korekta nie tworzy licznika spóźnień.", row=2, column=2, padx=(6, 0))
    ttk.Checkbutton(att, text="Zapisz nadgodziny", variable=a_ot_on).grid(row=3, column=0, sticky="w", pady=4)
    ot_box = ttk.Frame(att); ot_box.grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Entry(ot_box, textvariable=a_ot_hours, width=8).pack(side="left")
    ttk.Label(ot_box, text=" h  ").pack(side="left")
    ttk.Combobox(ot_box, textvariable=a_ot_type, values=("zwykle", "sobota", "niedziela", "swieto"), state="readonly", width=14).pack(side="left")
    _field(att, 4, "Powód / uwaga:", a_note)

    def save_attendance() -> None:
        try:
            date.fromisoformat(a_date.get().strip())
            attendance_service.set_manual_day(a_date.get().strip(), a_slot.get(), state["login"], _float(a_day.get(), "dniówka"), actor, a_note.get())
            if a_ot_on.get():
                attendance_service.set_overtime(a_date.get().strip(), a_slot.get(), state["login"], _float(a_ot_hours.get(), "nadgodziny"), actor, overtime_type=a_ot_type.get(), note=a_note.get())
            _audit(state["login"], "obecnosc", actor, after={"date": a_date.get(), "slot": a_slot.get(), "day": a_day.get(), "overtime": a_ot_hours.get() if a_ot_on.get() else 0}, note=a_note.get())
        except Exception as exc:
            messagebox.showerror("Obecność", f"Nie udało się zapisać korekty:\n{exc}", parent=win)
            return
        messagebox.showinfo("Obecność", "Zapisano korektę obecności.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    ttk.Button(att, text="Zapisz korektę", command=save_attendance).grid(row=5, column=1, sticky="e", pady=(12, 0))
    add_help_button(att, "Sobota jest liczona osobno od zwykłych dniówek. Nadgodziny zapisuje Brygadzista, nie czas pozostawienia WM otwartego.", row=5, column=2, padx=(6, 0))

    # URLOPY
    leaves = frames["Urlopy"]
    leaves.columnconfigure(1, weight=1)
    current_year = date.today().year
    balance = leave_balance_service.get_balance(state["login"], current_year)
    l_year = tk.StringVar(value=str(current_year))
    l_ent = tk.StringVar(value=f"{float(balance.get('entitlement') or 0):g}")
    l_adj = tk.StringVar(value=f"{float(balance.get('adjustment') or 0):g}")
    l_carry = tk.StringVar(value=_format_carryover(balance, current_year))
    _field(leaves, 0, "Rok:", l_year)
    _field(leaves, 1, "Urlop należny:", l_ent, help_text="Roczny wymiar urlopu dla pracownika, np. 20 lub 26 dni.")
    _field(leaves, 2, "Korekta:", l_adj, help_text="Ręczna korekta salda na dany rok. Może być dodatnia albo ujemna.")
    _field(leaves, 3, "Zaległy wg roku:", l_carry, help_text="Format np. 2024=2; 2025=4. Przy wykorzystaniu WM zawsze pobiera najpierw najstarszy zaległy urlop.")
    leave_status = tk.StringVar(value=(f"🟡 Zaległy: {balance.get('carryover',0):g}   🔵 Wykorzystano: {balance.get('used',0):g}   🟠 Oczekuje: {balance.get('pending',0):g}   🟢 Pozostało: {balance.get('remaining',0):g}"))
    ttk.Label(leaves, textvariable=leave_status).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 4))

    def save_balance() -> None:
        try:
            year = int(l_year.get())
            before = leave_balance_service.get_balance(state["login"], year)
            carry = _parse_carryover(l_carry.get(), year)
            leave_balance_service.set_year_values(state["login"], year, entitlement=_float(l_ent.get(), "urlop należny"), adjustment=_float(l_adj.get(), "korekta"), carryover=carry)
            after = leave_balance_service.get_balance(state["login"], year)
            _audit(state["login"], "saldo_urlopu", actor, before=before, after=after)
            leave_status.set(f"🟡 Zaległy: {after.get('carryover',0):g}   🔵 Wykorzystano: {after.get('used',0):g}   🟠 Oczekuje: {after.get('pending',0):g}   🟢 Pozostało: {after.get('remaining',0):g}")
        except Exception as exc:
            messagebox.showerror("Urlopy", f"Nie udało się zapisać salda:\n{exc}", parent=win)
            return
        messagebox.showinfo("Urlopy", "Zapisano saldo urlopu.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    ttk.Button(leaves, text="Zapisz saldo", command=save_balance).grid(row=5, column=1, sticky="e", pady=(8, 14))

    abs_start = tk.StringVar(value=date.today().isoformat())
    abs_end = tk.StringVar(value=date.today().isoformat())
    abs_note = tk.StringVar(value="")
    _field(leaves, 6, "Nieobecność od:", abs_start)
    _field(leaves, 7, "Nieobecność do:", abs_end)
    _field(leaves, 8, "Uwagi:", abs_note)

    def add_absence(kind: str) -> None:
        try:
            from services import leave_workflow_service as lw
            days = lw.dates_from_range(abs_start.get(), abs_end.get(), include_sundays=True)
            if kind == "L4":
                count = lw.add_l4(state["login"], days, actor, abs_note.get())
            else:
                count = lw.add_nn(state["login"], days, actor, abs_note.get())
            _audit(state["login"], kind.lower(), actor, after={"dates": days, "count": count}, note=abs_note.get())
        except Exception as exc:
            messagebox.showerror("Nieobecność", f"Nie udało się zapisać {kind}:\n{exc}", parent=win)
            return
        messagebox.showinfo("Nieobecność", f"Zapisano {kind}: {count} dni.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    abs_actions = ttk.Frame(leaves); abs_actions.grid(row=9, column=0, columnspan=3, sticky="e")
    ttk.Button(abs_actions, text="Dodaj L4", command=lambda: add_absence("L4")).pack(side="left", padx=(0, 6))
    ttk.Button(abs_actions, text="Dodaj NN", command=lambda: add_absence("NN")).pack(side="left")
    add_help_button(abs_actions, "L4 i NN trafiają do tej samej ewidencji nieobecności co kalendarz i obecność. WM nie będzie oczekiwał logowania w zapisanym dniu.").pack(side="left", padx=(6, 0))

    # GRAFIK
    schedule = frames["Grafik"]
    schedule.columnconfigure(1, weight=1)
    try:
        from grafiki import shifts_schedule as shifts
        mode_now, anchor_now = shifts.get_user_schedule(state["login"], "111")
    except Exception:
        mode_now, anchor_now = "111", date.today().isoformat()
    g_mode = tk.StringVar(value=str(mode_now or "111"))
    g_anchor = tk.StringVar(value=str(anchor_now or date.today().isoformat()))
    ttk.Label(schedule, text="Tryb zmian:").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Combobox(schedule, textvariable=g_mode, values=("111", "222", "121", "212"), state="readonly").grid(row=0, column=1, sticky="ew", pady=4)
    add_help_button(schedule, "111 = stała I zmiana, 222 = stała II zmiana, 121/212 = rotacja. Godziny zmian pozostają 06–14 i 14–22.", row=0, column=2, padx=(6, 0))
    _field(schedule, 1, "Tydzień bazowy:", g_anchor, help_text="Data służy jako punkt odniesienia dla rotacji zmian.")
    day_vars: list[tk.BooleanVar] = []
    workdays = set(int(x) for x in (user.get("workdays") or [0,1,2,3,4]) if str(x).isdigit())
    days_wrap = ttk.Frame(schedule); days_wrap.grid(row=2, column=1, sticky="w", pady=6)
    for idx, label in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):
        var = tk.BooleanVar(value=idx in workdays); day_vars.append(var)
        ttk.Checkbutton(days_wrap, text=label, variable=var).pack(side="left", padx=(0, 6))
    ttk.Label(schedule, text="Dni pracy:").grid(row=2, column=0, sticky="w", pady=4)

    def save_schedule() -> None:
        try:
            date.fromisoformat(g_anchor.get().strip()[:10])
            from grafiki import shifts_schedule as shifts
            before = {"mode": mode_now, "anchor": anchor_now, "workdays": sorted(workdays)}
            shifts.set_user_schedule(state["login"], g_mode.get(), g_anchor.get().strip())
            current = workforce_profile_service.get_user(state["login"]) or {}
            current["workdays"] = [idx for idx, var in enumerate(day_vars) if var.get()]
            workforce_profile_service.save_user(current, actor=actor)
            after = {"mode": g_mode.get(), "anchor": g_anchor.get().strip(), "workdays": current["workdays"]}
            _audit(state["login"], "grafik", actor, before=before, after=after)
        except Exception as exc:
            messagebox.showerror("Grafik", f"Nie udało się zapisać grafiku:\n{exc}", parent=win)
            return
        messagebox.showinfo("Grafik", "Zapisano grafik pracownika.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    ttk.Button(schedule, text="Zapisz grafik", command=save_schedule).grid(row=3, column=1, sticky="e", pady=(10, 0))

    # UPRAWNIENIA
    perms = frames["Uprawnienia"]
    ttk.Label(perms, text="Wyłączone moduły dla tego pracownika:").pack(anchor="w", pady=(0, 8))
    try:
        from ustawienia_uzytkownicy import MODULE_LABELS
    except Exception:
        MODULE_LABELS = []
    current_disabled = {str(x) for x in (user.get("disabled_modules") or [])}
    module_vars: dict[str, tk.BooleanVar] = {}
    for key, label in MODULE_LABELS:
        var = tk.BooleanVar(value=str(key) in current_disabled)
        module_vars[str(key)] = var
        ttk.Checkbutton(perms, text=f"Wyłącz: {label}", variable=var).pack(anchor="w", pady=2)

    def save_permissions() -> None:
        try:
            current = workforce_profile_service.get_user(state["login"]) or {}
            before = list(current.get("disabled_modules") or [])
            current["disabled_modules"] = [key for key, var in module_vars.items() if var.get()]
            workforce_profile_service.save_user(current, actor=actor)
            _audit(state["login"], "uprawnienia", actor, before=before, after=current["disabled_modules"])
        except Exception as exc:
            messagebox.showerror("Uprawnienia", f"Nie udało się zapisać uprawnień:\n{exc}", parent=win)
            return
        messagebox.showinfo("Uprawnienia", "Zapisano uprawnienia pracownika.", parent=win)
        if callable(on_saved):
            try: on_saved()
            except Exception: pass

    per_actions = ttk.Frame(perms); per_actions.pack(fill="x", pady=(12, 0))
    ttk.Button(per_actions, text="Zapisz uprawnienia", command=save_permissions).pack(side="right")
    add_help_button(per_actions, "Te zaznaczenia wyłączają wybrane moduły dla konkretnego pracownika. Uprawnienia całej rangi nadal można ustawiać w Użytkownicy → Rangi.").pack(side="right", padx=(0, 6))

    # HISTORIA
    history = frames["Historia"]
    htree = ttk.Treeview(history, columns=("ts", "action", "actor", "note"), show="headings", height=18)
    for key, label, width in (("ts", "Data", 155), ("action", "Akcja", 150), ("actor", "Kto", 110), ("note", "Informacja", 470)):
        htree.heading(key, text=label); htree.column(key, width=width, anchor="w")
    htree.pack(fill="both", expand=True)

    def refresh_history() -> None:
        htree.delete(*htree.get_children())
        rows = []
        for row in _profile_audit(state["login"], 250):
            item = dict(row); item["_source"] = "profil"; rows.append(item)
        try:
            for row in attendance_service.audit_for_login(state["login"], 250):
                item = dict(row); item["_source"] = "obecność"; rows.append(item)
        except Exception:
            pass
        rows.sort(key=lambda row: str(row.get("ts") or ""), reverse=True)
        for row in rows[:400]:
            note = str(row.get("note") or "")
            if not note and row.get("_source") == "profil":
                note = "Zmiana danych"
            htree.insert("", "end", values=(str(row.get("ts") or "").replace("T", " ")[:19], row.get("action") or row.get("_source"), row.get("actor") or "—", note))

    refresh_history()
    h_actions = ttk.Frame(history); h_actions.pack(fill="x", pady=(8, 0))
    ttk.Button(h_actions, text="Odśwież historię", command=refresh_history).pack(side="left")
    add_help_button(h_actions, "Historia jest tylko do odczytu. Brygadzista może poprawić dane, ale nie usuwa śladu wcześniejszej zmiany.").pack(side="left", padx=(6, 0))

    # WIĘCEJ
    more = frames["Więcej"]
    ttk.Label(more, text="Dodatkowe dane pracownika pozostają w profilu i nie są usuwane przez ten edytor.").pack(anchor="w", pady=(0, 8))
    for label, key in (("Umiejętności", "umiejetnosci"), ("Kursy / certyfikaty", "kursy"), ("Nagrody / pochwały", "nagrody"), ("Ostrzeżenia", "ostrzezenia")):
        ttk.Label(more, text=f"{label}: {user.get(key) or '—'}", wraplength=880, justify="left").pack(anchor="w", pady=4)

    try:
        nb.select(frames.get(initial_tab, frames["Dane"]))
    except Exception:
        pass
    bottom = ttk.Frame(win); bottom.pack(fill="x", padx=10, pady=(0, 10))
    ttk.Button(bottom, text="Zamknij", command=win.destroy).pack(side="right")


def _find_tree(parent) -> ttk.Treeview | None:
    try:
        children = parent.winfo_children()
    except Exception:
        return None
    for child in children:
        if isinstance(child, ttk.Treeview):
            return child
        found = _find_tree(child)
        if found is not None:
            return found
    return None


def _patch_users_admin() -> None:
    try:
        import profile_admin_ui as admin_ui
        cls = admin_ui.UsersAdminPanel
    except Exception:
        return
    if getattr(cls, "_wm_foreman_edit_v094", False):
        return
    original_build = cls._build

    def build(self) -> None:
        original_build(self)
        toolbar = None
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                toolbar = child
                break
        if toolbar is not None:
            ttk.Button(toolbar, text="Resetuj PIN", command=lambda: reset_pin_selected(self)).pack(side="left", padx=(6, 0))
            add_help_button(toolbar, "Istniejący PIN nigdy nie jest wyświetlany. Brygadzista może wyłącznie ustawić nowy PIN.").pack(side="left", padx=(4, 0))

    def refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for user in self.users:
            self.tree.insert("", "end", values=(
                user.get("login", ""), "••••" if str(user.get("pin") or "") else "—",
                user.get("rola", "operator"), user.get("zatrudniony_od", "—"), user.get("status", "aktywny"),
            ))

    def edit_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Profil", "Wybierz profil do edycji.", parent=self)
            return
        login = str(self.users[index].get("login") or "")
        open_employee_editor(self, login, initial_tab="Dane", on_saved=self.reload)

    def reset_pin_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("PIN", "Wybierz użytkownika.", parent=self)
            return
        login = str(self.users[index].get("login") or "")
        first = simpledialog.askstring("Reset PIN", f"Nowy PIN dla {login}:", show="•", parent=self)
        if first is None:
            return
        second = simpledialog.askstring("Reset PIN", "Powtórz nowy PIN:", show="•", parent=self)
        if second is None:
            return
        if first != second:
            messagebox.showerror("PIN", "Podane PIN-y są różne.", parent=self)
            return
        try:
            _reset_pin(login, first, _actor_or_error(self))
        except Exception as exc:
            messagebox.showerror("PIN", f"Nie udało się zresetować PIN:\n{exc}", parent=self)
            return
        self.reload()
        messagebox.showinfo("PIN", "PIN został zresetowany.", parent=self)

    cls._build = build
    cls._refresh_tree = refresh_tree
    cls._edit_selected = edit_selected
    cls._wm_foreman_edit_v094 = True


def _patch_foreman_panel() -> None:
    try:
        import gui_profile_foreman as foreman
        cls = foreman.ForemanProfilePanel
    except Exception:
        return
    if getattr(cls, "_wm_foreman_edit_v094", False):
        return

    original_build = cls._build
    original_team = cls._render_team
    original_leaves = cls._render_leaves

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        notebook = getattr(self, "notebook", None)
        tabs = getattr(self, "_tabs", {})
        if notebook is not None and isinstance(tabs, dict):
            for hidden in ("Zadania", "Sprzęt", "Profile"):
                tab = tabs.get(hidden)
                if tab is not None:
                    try: notebook.hide(tab)
                    except Exception: pass
            tabs.pop("Profile", None)
            order = ("Pulpit", "Zespół", "Obecność", "Urlopy", "Użytkownicy", "Opinie", "Statystyki")
            for index, name in enumerate(order):
                tab = tabs.get(name)
                if tab is not None:
                    try: notebook.insert(index, tab)
                    except Exception: pass
        return result

    def render_team(self) -> None:
        original_team(self)
        parent = self._tabs.get("Zespół")
        if parent is None:
            return
        tree = _find_tree(parent)
        if tree is None:
            return
        rows = list(self.snapshot.get("team") or [])
        mapping = {iid: str(row.get("login") or "") for iid, row in zip(tree.get_children(), rows)}

        def selected_login() -> str:
            selected = tree.selection()
            return mapping.get(selected[0], "") if selected else ""

        def edit(tab: str = "Dane") -> None:
            login = selected_login()
            if not login:
                messagebox.showinfo("Zespół", "Wybierz pracownika.", parent=self.winfo_toplevel())
                return
            open_employee_editor(self, login, initial_tab=tab, on_saved=self.refresh_data)

        actions = ttk.Frame(parent, style="WM.Container.TFrame")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Edytuj pracownika", command=lambda: edit("Dane")).pack(side="left")
        ttk.Button(actions, text="Obecność / dniówki", command=lambda: edit("Obecność")).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Urlop / L4 / NN", command=lambda: edit("Urlopy")).pack(side="left", padx=(6, 0))
        add_help_button(actions, "Brygadzista może edytować dane, obecność, urlopy, grafik i uprawnienia wybranego pracownika. Zmiany zapisują się w Historii.").pack(side="left", padx=(6, 0))
        tree.bind("<Double-1>", lambda _event: edit("Dane"), add="+")

    def render_leaves(self) -> None:
        original_leaves(self)
        parent = self._tabs.get("Urlopy")
        if parent is None:
            return
        tree = _find_tree(parent)
        if tree is None:
            return
        users = []
        for user in workforce_profile_service.list_users(active_only=True):
            if str(user.get("rola") or user.get("role") or "").casefold() == "guest":
                continue
            users.append(user)
        mapping = {iid: str(user.get("login") or "") for iid, user in zip(tree.get_children(), users)}

        def edit_leave() -> None:
            selected = tree.selection()
            login = mapping.get(selected[0], "") if selected else ""
            if not login:
                messagebox.showinfo("Urlopy", "Wybierz pracownika.", parent=self.winfo_toplevel())
                return
            open_employee_editor(self, login, initial_tab="Urlopy", on_saved=self.refresh_data)

        actions = ttk.Frame(parent, style="WM.Container.TFrame")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Edytuj saldo / L4 / NN", command=edit_leave).pack(side="left")
        add_help_button(actions, "Pozwala skorygować roczny wymiar, zaległy urlop oraz dodać L4 lub NN. Zaległy urlop nadal jest pobierany od najstarszego roku.").pack(side="left", padx=(6, 0))

    cls._build = build
    cls._render_team = render_team
    cls._render_leaves = render_leaves
    cls._wm_foreman_edit_v094 = True


def _patch_details_entry() -> None:
    try:
        import profile_workforce_runtime as runtime
    except Exception:
        return
    if getattr(runtime, "_wm_foreman_details_v094", False):
        return
    original = runtime.open_employee_details

    def open_details(owner, login: str) -> None:
        if _is_foreman(owner):
            open_employee_editor(owner, login, initial_tab="Dane")
        else:
            original(owner, login)

    runtime.open_employee_details = open_details
    runtime._wm_foreman_details_v094 = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_users_admin()
    _patch_foreman_panel()
    _patch_details_entry()
    _INSTALLED = True


__all__ = ["install", "open_employee_editor", "_parse_carryover"]
