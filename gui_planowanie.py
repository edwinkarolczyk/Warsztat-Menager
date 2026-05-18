# =========================================================
# WM - PLANOWANIE PRODUKCJI (ROZBUDOWA MVP)
# =========================================================
# Zmiany:
# - pełnoekranowy kalendarz
# - edycja zleceń
# - workflow elementów
# - etapy opcjonalne
# - pracownicy + stanowiska
# - ilości wykonane na zmianach
# - analiza archiwum pod czasy etapów
# =========================================================

import calendar
import json
import os
import shutil
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog

from config_manager import ConfigManager

DEFAULT_WORKFLOW = [
    {
        "id": "laser",
        "name": "Laser",
        "color": "#3498db",
        "enabled": True,
        "optional": True,
        "station": "Laser",
        "min_workers": 1,
        "max_workers": 2,
    },
    {
        "id": "gilotyna",
        "name": "Gilotyna",
        "color": "#5dade2",
        "enabled": False,
        "optional": True,
        "station": "Gilotyna",
        "min_workers": 1,
        "max_workers": 2,
    },
    {
        "id": "giecie",
        "name": "Gięcie",
        "color": "#f1c40f",
        "enabled": True,
        "optional": True,
        "station": "Giętarka 1",
        "min_workers": 1,
        "max_workers": 2,
    },
    {
        "id": "zgrzewanie",
        "name": "Zgrzewanie",
        "color": "#e67e22",
        "enabled": True,
        "optional": True,
        "station": "Zgrzewanie",
        "min_workers": 1,
        "max_workers": 6,
    },
    {
        "id": "malowanie",
        "name": "Malowanie",
        "color": "#9b59b6",
        "enabled": True,
        "optional": True,
        "station": "Malarnia",
        "min_workers": 2,
        "max_workers": 4,
    },
    {
        "id": "pakowanie",
        "name": "Pakowanie",
        "color": "#2ecc71",
        "enabled": True,
        "optional": True,
        "station": "Pakowanie",
        "min_workers": 1,
        "max_workers": 3,
    },
]

DEFAULT_STATIONS = [
    "Laser",
    "Gilotyna",
    "Giętarka 1",
    "Zgrzewanie",
    "Malarnia",
    "Pakowanie",
]

DEFAULT_SHIFTS = [
    "06:00-14:00",
    "14:00-22:00",
]

STATUSY = ["oczekuje", "w trakcie", "zakończone", "problem"]
BLOCK_REASONS = ["awaria", "brak ludzi", "inwentaryzacja", "święto", "własny opis"]
SHIFTS = {"1": "06:00-14:00", "2": "14:00-22:00", "S": "06:00-14:00 (sobota)"}
EDIT_ROLES = {"admin", "administrator", "kierownik"}
ASSIGN_ONLY_ROLES = {"brygadzista"}


def _today() -> str:
    return date.today().isoformat()


def _parse_dt(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _default_data() -> dict:
    return {
        "meta": {"version": 1, "updated_at": datetime.now().isoformat()},
        "workers": [],
        "stations": deepcopy(DEFAULT_STATIONS),
        "workflow_templates": deepcopy(DEFAULT_WORKFLOW),
        "blocked_days": [],
        "orders": [],
        "archive": [],
    }


def _is_workday(day: date, saturdays_working: set[str]) -> bool:
    if day.weekday() < 5:
        return True
    if day.weekday() == 5 and day.isoformat() in saturdays_working:
        return True
    return False


def _next_workday(day: date, saturdays_working: set[str]) -> date:
    current = day
    while not _is_workday(current, saturdays_working):
        current += timedelta(days=1)
    return current


def _build_schedule(order: dict, saturdays_working: set[str]) -> None:
    start = _parse_dt(order.get("start_date")) or date.today()
    cursor = _next_workday(start, saturdays_working)
    for step in order.get("stages", []):
        if not step.get("enabled", True):
            step["start"] = None
            step["end"] = None
            continue
        duration = max(1, int(step.get("duration_days", 1)))
        step_start = cursor
        days_left = duration
        while days_left > 0:
            if _is_workday(cursor, saturdays_working):
                days_left -= 1
                if days_left == 0:
                    break
            cursor += timedelta(days=1)
        step_end = cursor
        step["start"] = step_start.isoformat()
        step["end"] = step_end.isoformat()
        cursor = _next_workday(step_end + timedelta(days=1), saturdays_working)


class PlanStore:
    def __init__(self, cfg: ConfigManager | None = None):
        self.cfg = cfg or ConfigManager()
        self.data_path = self._resolve_data_path()
        self.backup_dir = Path(self.cfg.path_backup("planowanie"))
        self.lock_path = Path(str(self.data_path) + ".lock")
        self.data = _default_data()
        self.load()

    def _resolve_data_path(self) -> Path:
        configured = self.cfg.expanded("planowanie.data_path", default="data/planowanie/plan.json")
        if not isinstance(configured, str) or not configured.strip():
            configured = "data/planowanie/plan.json"
        if os.path.isabs(configured):
            return Path(configured)
        rel = configured.replace("\\", "/")
        if rel.startswith("data/"):
            rel = rel[len("data/"):]
        return Path(self.cfg.path_data(*[p for p in rel.split("/") if p]))

    def load(self) -> None:
        if self.data_path.exists():
            with self.data_path.open("r", encoding="utf-8") as fh:
                self.data = json.load(fh)
        else:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.save(force=True)

    def _create_daily_backup(self) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = date.today().strftime("%Y%m%d")
        dst = self.backup_dir / f"plan_{stamp}.json"
        if not dst.exists() and self.data_path.exists():
            shutil.copy2(self.data_path, dst)

    def save(self, force: bool = False) -> bool:
        if self.lock_path.exists() and not force:
            return False
        try:
            self.lock_path.write_text(str(os.getpid()), encoding="utf-8")
            self._create_daily_backup()
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.data["meta"] = {"version": 1, "updated_at": datetime.now().isoformat()}
            with self.data_path.open("w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            return True
        finally:
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass


@dataclass
class RoleAccess:
    can_edit: bool
    can_assign: bool
    can_delete: bool
    can_archive: bool


class PlanowanieUI:
    def __init__(self, root, frame, login=None, rola=None):
        self.root = root
        self.frame = frame
        self.login = login
        self.role = str(rola or "").strip().lower()
        self.is_manager = self.role in {"admin", "kierownik"}
        self.is_bryg = self.role == "brygadzista"
        can_edit = self.role in EDIT_ROLES or self.is_manager
        self.access = RoleAccess(
            can_edit=can_edit,
            can_assign=True,
            can_delete=can_edit,
            can_archive=can_edit,
        )
        self.store = PlanStore()
        self.calendar_year = date.today().year
        self.calendar_month = date.today().month
        self.search_var = tk.StringVar(value="")
        self.filter_status = tk.StringVar(value="")
        self._build_ui()

    def _notify_no_access(self):
        ttk.Label(self.frame, text="Brak dostępu do modułu Planowanie.").pack(padx=12, pady=12)

    def _build_ui(self):
        for w in self.frame.winfo_children():
            w.destroy()
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill="x", padx=8, pady=8)
        ttk.Button(toolbar, text="Otwórz okno planisty", command=self._open_planner_window).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Eksport PDF", command=lambda: messagebox.showinfo("Planowanie", "Funkcja eksportu będzie dodana później")).pack(side="left")
        ttk.Button(toolbar, text="Eksport Excel", command=lambda: messagebox.showinfo("Planowanie", "Funkcja eksportu będzie dodana później")).pack(side="left", padx=6)

        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        tab_cal = ttk.Frame(notebook)
        tab_ord = ttk.Frame(notebook)
        notebook.add(tab_cal, text="KALENDARZ")
        notebook.add(tab_ord, text="ZLECENIA")
        self._build_calendar_tab(tab_cal)
        self._build_orders_tab(tab_ord)

    def _open_planner_window(self):
        win = tk.Toplevel(self.root)
        win.title("Planista produkcji")
        win.geometry("1200x800")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True)
        PlanowanieUI(win, frm, self.login, self.role)

    def _build_orders_tab(self, tab):
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Szukaj:").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.search_var)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ent.bind("<KeyRelease>", lambda _e: self._refresh_orders_list())
        ttk.Button(top, text="Dodaj", command=self._add_order).pack(side="left", padx=6)
        ttk.Button(top, text="Edytuj", command=self._edit_selected_order).pack(side="left", padx=3)
        ttk.Button(top, text="Usuń", command=self._delete_selected_order).pack(side="left", padx=3)
        ttk.Button(top, text="Archiwum", command=self._archive_selected_order).pack(side="left", padx=3)
        if self.access.can_edit:
            ttk.Button(top, text="Blokada dnia", command=self._block_day).pack(side="left", padx=6)

        self.orders_tree = ttk.Treeview(tab, columns=("number", "symbol", "client", "qty", "ship", "status"), show="headings", height=12)
        self.orders_tree.heading("number", text="Nr")
        self.orders_tree.heading("symbol", text="Symbol")
        self.orders_tree.heading("client", text="Klient")
        self.orders_tree.heading("qty", text="Ilość")
        self.orders_tree.heading("ship", text="Termin")
        self.orders_tree.heading("status", text="Status")
        self.orders_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.orders_tree.bind("<<TreeviewSelect>>", lambda _e: self._show_order_detail())

        detail = ttk.LabelFrame(tab, text="Szczegóły zlecenia")
        detail.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.detail_text = tk.Text(detail, height=12)
        self.detail_text.pack(fill="both", expand=True)

        stats = ttk.LabelFrame(tab, text="Statystyki")
        stats.pack(fill="x", padx=8, pady=(0, 8))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(stats, textvariable=self.stats_var).pack(anchor="w", padx=8, pady=8)

        self._refresh_orders_list()

    def _build_calendar_tab(self, tab):
        nav = ttk.Frame(tab)
        nav.pack(fill="x", padx=8, pady=8)
        ttk.Button(nav, text="<", command=lambda: self._move_month(-1)).pack(side="left")
        self.month_var = tk.StringVar(value="")
        ttk.Label(nav, textvariable=self.month_var).pack(side="left", padx=8)
        ttk.Button(nav, text=">", command=lambda: self._move_month(1)).pack(side="left")
        ttk.Label(nav, text="Tryb TV/monitor hali: podgląd").pack(side="right")

        self.cal_frame = ttk.Frame(tab)
        self.cal_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._render_calendar()

    def _move_month(self, step):
        m = self.calendar_month + step
        y = self.calendar_year
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        self.calendar_month, self.calendar_year = m, y
        self._render_calendar()

    def _render_calendar(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()
        self.month_var.set(f"{calendar.month_name[self.calendar_month]} {self.calendar_year}")
        week_hdr = ttk.Frame(self.cal_frame)
        week_hdr.pack(fill="x")
        for day_name in ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"]:
            ttk.Label(week_hdr, text=day_name).pack(side="left", fill="x", expand=True)

        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(self.calendar_year, self.calendar_month)
        today = date.today()
        for row_idx, week in enumerate(month_matrix):
            row = ttk.Frame(self.cal_frame)
            row.pack(fill="both", expand=True, pady=2)
            for day in week:
                is_today = day == today
                is_current_month = day.month == self.calendar_month
                bg = "#fff3b0" if is_today else ("#1f2937" if is_current_month else "#111827")
                fg = "#111827" if is_today else "white"
                border = 3 if is_today else 1
                highlight = "#f39c12" if is_today else "#374151"

                tile = tk.Frame(
                    row,
                    relief="solid" if is_today else "groove",
                    borderwidth=border,
                    bg=bg,
                    highlightthickness=2 if is_today else 0,
                    highlightbackground=highlight,
                )
                tile.pack(side="left", fill="both", expand=True, padx=1, pady=1)
                tile.bind("<Button-1>", lambda _e, d=day: self._open_day_plan(d))
                day_title = f"{day.day}  DZISIAJ" if is_today else f"{day.day}"
                tk.Label(tile, text=day_title, fg=fg, bg=bg, anchor="w", font=("Arial", 12, "bold")).pack(fill="x")
                for order in self.store.data.get("orders", []):
                    for st in order.get("stages", []):
                        s = _parse_dt(st.get("start"))
                        e = _parse_dt(st.get("end"))
                        if s and e and s <= day <= e:
                            color = st.get("color", "#64748b")
                            txt = f"{order.get('number')} {st.get('name')}"
                            lbl = tk.Label(tile, text=txt[:24], bg=color, fg="black")
                            lbl.pack(fill="x")
                            lbl.bind("<Button-1>", lambda _e, d=day: self._open_day_plan(d))

    def _filtered_orders(self):
        text = self.search_var.get().strip().lower()
        result = []
        for o in self.store.data.get("orders", []):
            blob = " ".join([
                str(o.get("number", "")),
                str(o.get("client", "")),
                str(o.get("status", "")),
                " ".join(s.get("name", "") for s in o.get("stages", [])),
                " ".join(",".join(s.get("employees", [])) for s in o.get("stages", [])),
            ]).lower()
            if text in blob:
                result.append(o)
        return result

    def _refresh_orders_list(self):
        for i in self.orders_tree.get_children():
            self.orders_tree.delete(i)
        for order in self._filtered_orders():
            self.orders_tree.insert("", "end", iid=order["id"], values=(order.get("number"), order.get("symbol"), order.get("client"), order.get("qty"), order.get("ship_date"), order.get("status", "aktywne")))
        self._refresh_stats()
        self._render_calendar()

    def _refresh_stats(self):
        orders = self.store.data.get("orders", [])
        delayed = sum(1 for o in orders if _parse_dt(o.get("ship_date")) and _parse_dt(o.get("ship_date")) < date.today())
        stage_counts = {}
        shifts = {"1": 0, "2": 0, "S": 0}
        for o in orders:
            for st in o.get("stages", []):
                stage_counts[st.get("name")] = stage_counts.get(st.get("name"), 0) + 1
                shifts[st.get("shift", "1")] = shifts.get(st.get("shift", "1"), 0) + 1
        self.stats_var.set(f"Aktywne: {len(orders)} | Opóźnione: {delayed} | Etapy: {stage_counts} | Obłożenie zmian: {shifts}")

    def _open_order_form(self, order=None, day_date=None):
        if not self.access.can_edit:
            return None
        win = tk.Toplevel(self.root)
        win.title("Dodaj/Edytuj zlecenie")
        default_date = day_date.isoformat() if day_date else _today()
        values = order or {}
        fields = {}
        form = ttk.Frame(win, padding=8)
        form.pack(fill="both", expand=True)
        for idx, (label, key, default) in enumerate([
            ("Nr zlecenia", "number", ""),
            ("Symbol elementu", "symbol", ""),
            ("Klient", "client", ""),
            ("Ilość", "qty", "1"),
            ("Termin wysyłki", "ship_date", default_date),
            ("Data startu", "start_date", default_date),
        ]):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(values.get(key, default)))
            ttk.Entry(form, textvariable=var, width=40).grid(row=idx, column=1, sticky="ew", pady=3)
            if key in {"ship_date", "start_date"}:
                ttk.Button(form, text="📅", command=lambda v=var: v.set(_today())).grid(row=idx, column=2, padx=4)
            fields[key] = var
        form.columnconfigure(1, weight=1)
        result = {"value": None}
        def save_form():
            result["value"] = {k: v.get().strip() for k, v in fields.items()}
            win.destroy()
        ttk.Button(form, text="Zapisz", command=save_form).grid(row=7, column=1, sticky="e", pady=8)
        win.grab_set()
        win.wait_window()
        return result["value"]

    def _build_stages(self, base_stages=None):
        stages = []
        for i, cfg in enumerate(DEFAULT_WORKFLOW):
            stage_in = (base_stages or [{}] * len(DEFAULT_WORKFLOW))[i] if base_stages else {}
            enabled = stage_in.get("enabled", cfg.get("enabled", True))
            stages.append({
                "id": cfg["id"],
                "name": cfg["name"],
                "color": stage_in.get("color", cfg["color"]),
                "enabled": enabled,
                "optional": cfg.get("optional", True),
                "station": stage_in.get("station", cfg.get("station", "")),
                "min_workers": int(stage_in.get("min_workers", cfg.get("min_workers", 1))),
                "max_workers": int(stage_in.get("max_workers", cfg.get("max_workers", 1))),
                "duration_days": int(stage_in.get("duration_days", 1)),
                "planned_days": int(stage_in.get("planned_days", 1)),
                "real_days": int(stage_in.get("real_days", 0)),
                "status": stage_in.get("status", "oczekuje"),
                "employees": stage_in.get("employees", []),
                "workers": stage_in.get("workers", []),
                "skills": stage_in.get("skills", []),
                "notes": stage_in.get("notes", ""),
                "planned_shift": stage_in.get("planned_shift", DEFAULT_SHIFTS[0]),
                "shift_history": stage_in.get("shift_history", []),
                "done_qty": int(stage_in.get("done_qty", 0)),
            })
        # Laser/Gilotyna jako alternatywa
        enabled_laser = stages[0]["enabled"]
        enabled_gilotyna = stages[1]["enabled"]
        if enabled_laser and enabled_gilotyna:
            stages[1]["enabled"] = False
        if not enabled_laser and not enabled_gilotyna:
            stages[0]["enabled"] = True
        return stages

    def _add_order(self, day_date=None):
        payload = self._open_order_form(day_date=day_date)
        if not payload:
            return
        qty = int(payload.get("qty") or 0)
        stages = self._build_stages()
        order = {
            "id": f"ord-{int(datetime.now().timestamp() * 1000)}",
            "number": payload.get("number"),
            "symbol": payload.get("symbol"),
            "client": payload.get("client"),
            "qty": qty,
            "start_date": payload.get("start_date") or _today(),
            "ship_date": payload.get("ship_date") or _today(),
            "status": "aktywne",
            "attachments": [],
            "stages": stages,
            "history": [],
        }
        sats = set(self.store.data.get("working_saturdays", []))
        _build_schedule(order, sats)
        self.store.data.setdefault("orders", []).append(order)
        self._persist_or_warn()
        self._refresh_orders_list()

    def _show_order_detail(self):
        sel = self.orders_tree.selection()
        if not sel:
            return
        order = next((o for o in self.store.data.get("orders", []) if o["id"] == sel[0]), None)
        if not order:
            return
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", json.dumps(order, ensure_ascii=False, indent=2))

    def _block_day(self):
        d = simpledialog.askstring("Blokada", "Data YYYY-MM-DD:", parent=self.frame)
        if not d:
            return
        reason = simpledialog.askstring("Blokada", "Powód (awaria/brak ludzi/inwentaryzacja/święto/opis):", parent=self.frame) or "własny opis"
        self.store.data.setdefault("blocked_days", []).append({"date": d, "reason": reason})
        self._persist_or_warn()

    def _persist_or_warn(self):
        if not self.store.save():
            messagebox.showwarning("Planowanie", "Ktoś edytuje plan — spróbuj ponownie.")

    def _selected_order(self):
        sel = self.orders_tree.selection()
        if not sel:
            return None
        return next((o for o in self.store.data.get("orders", []) if o["id"] == sel[0]), None)

    def _edit_selected_order(self):
        order = self._selected_order()
        if not order:
            return
        if not self.access.can_edit:
            return
        payload = self._open_order_form(order=order)
        if not payload:
            return
        order.update({
            "number": payload.get("number"),
            "symbol": payload.get("symbol"),
            "client": payload.get("client"),
            "qty": int(payload.get("qty") or order.get("qty") or 0),
            "ship_date": payload.get("ship_date") or order.get("ship_date"),
            "start_date": payload.get("start_date") or order.get("start_date"),
        })
        order["stages"] = self._build_stages(order.get("stages", []))
        _build_schedule(order, set(self.store.data.get("working_saturdays", [])))
        self._persist_or_warn()
        self._refresh_orders_list()

    def _delete_selected_order(self):
        order = self._selected_order()
        if not order or not self.access.can_delete:
            return
        self.store.data["orders"] = [o for o in self.store.data.get("orders", []) if o["id"] != order["id"]]
        self._persist_or_warn()
        self._refresh_orders_list()

    def _archive_selected_order(self):
        order = self._selected_order()
        if not order or not self.access.can_archive:
            return
        self.store.data.setdefault("archive", []).append(order)
        self.store.data["orders"] = [o for o in self.store.data.get("orders", []) if o["id"] != order["id"]]
        self._persist_or_warn()
        self._refresh_orders_list()

    def suggest_stage_days(self, symbol, stage_name):
        values = []
        for order in self.store.data.get("archive", []):
            if order.get("symbol") != symbol:
                continue
            for st in order.get("stages", []):
                if st.get("name") == stage_name and st.get("real_days"):
                    values.append(int(st.get("real_days")))
        return round(sum(values) / len(values), 2) if values else 1

    def _open_day_plan(self, day):
        win = tk.Toplevel(self.root)
        win.title(f"Plan dnia {day.isoformat()}")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Zlecenia na dzień: {day.isoformat()}", font=("Arial", 11, "bold")).pack(anchor="w")
        box = tk.Listbox(frm, height=12)
        box.pack(fill="both", expand=True, pady=8)
        for order in self.store.data.get("orders", []):
            for st in order.get("stages", []):
                s = _parse_dt(st.get("start"))
                e = _parse_dt(st.get("end"))
                if s and e and s <= day <= e:
                    box.insert("end", f"{order.get('number')} | {order.get('symbol')} | {st.get('name')} | {st.get('status')}")
        ttk.Button(frm, text="Dodaj zlecenie", command=lambda d=day: self._add_order(day_date=d)).pack(anchor="e")


def panel_planowanie(root, frame, login=None, rola=None):
    PlanowanieUI(root, frame, login=login, rola=rola)
