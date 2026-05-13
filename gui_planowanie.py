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

ETAPY_DOMYSLNE = [
    ("ciecie", "cięcie", "#3b82f6"),
    ("przygotowanie", "przygotowanie", "#facc15"),
    ("zgrzewanie", "zgrzewanie", "#fb923c"),
    ("malowanie", "malowanie", "#a855f7"),
    ("pakowanie", "pakowanie", "#22c55e"),
    ("wysylka", "wysyłka", "#374151"),
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
        "employees": [],
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


class PlanowanieUI:
    def __init__(self, root, frame, login=None, rola=None):
        self.root = root
        self.frame = frame
        self.login = login
        self.role = str(rola or "").strip().lower()
        self.access = RoleAccess(self.role in EDIT_ROLES, self.role in EDIT_ROLES or self.role in ASSIGN_ONLY_ROLES)
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
        if not self.access.can_assign:
            return self._notify_no_access()

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
        ttk.Label(top, text="Filtr:").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.search_var)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ent.bind("<KeyRelease>", lambda _e: self._refresh_orders_list())
        if self.access.can_edit:
            ttk.Button(top, text="Dodaj zlecenie", command=self._add_order).pack(side="left", padx=6)
            ttk.Button(top, text="Blokada dnia", command=self._block_day).pack(side="left")

        self.orders_tree = ttk.Treeview(tab, columns=("client", "ship", "status"), show="headings", height=12)
        self.orders_tree.heading("client", text="Klient")
        self.orders_tree.heading("ship", text="Termin wysyłki")
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
            ttk.Label(week_hdr, text=day_name, width=16).pack(side="left")

        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(self.calendar_year, self.calendar_month)
        for week in month_matrix:
            row = ttk.Frame(self.cal_frame)
            row.pack(fill="x", pady=2)
            for day in week:
                tile = tk.Frame(row, relief="groove", borderwidth=1, bg="#1f2937")
                tile.pack(side="left", padx=1, ipadx=2, ipady=2)
                tk.Label(tile, text=f"{day.day}", fg="white", bg="#1f2937", width=14, anchor="w").pack()
                for order in self.store.data.get("orders", []):
                    for st in order.get("stages", []):
                        s = _parse_dt(st.get("start"))
                        e = _parse_dt(st.get("end"))
                        if s and e and s <= day <= e:
                            color = st.get("color", "#64748b")
                            txt = f"{order.get('number')} {st.get('name')}"
                            tk.Label(tile, text=txt[:16], bg=color, fg="black").pack(fill="x")

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
            self.orders_tree.insert("", "end", iid=order["id"], values=(order.get("client"), order.get("ship_date"), order.get("status", "aktywne")))
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

    def _add_order(self):
        if not self.access.can_edit:
            return
        number = simpledialog.askstring("Planowanie", "Numer zlecenia:", parent=self.frame)
        if not number:
            return
        client = simpledialog.askstring("Planowanie", "Klient/Nazwa:", parent=self.frame) or ""
        start = simpledialog.askstring("Planowanie", "Data startu (YYYY-MM-DD):", parent=self.frame) or _today()
        ship = simpledialog.askstring("Planowanie", "Termin wysyłki (YYYY-MM-DD):", parent=self.frame) or start
        stages = []
        for key, label, color in ETAPY_DOMYSLNE:
            stages.append({"id": key, "name": label, "color": color, "enabled": True, "duration_days": 1, "status": "oczekuje", "employees": [], "notes": "", "shift": "1"})
        order = {
            "id": f"ord-{int(datetime.now().timestamp() * 1000)}",
            "number": number,
            "client": client,
            "start_date": start,
            "ship_date": ship,
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


def panel_planowanie(root, frame, login=None, rola=None):
    PlanowanieUI(root, frame, login=login, rola=rola)
