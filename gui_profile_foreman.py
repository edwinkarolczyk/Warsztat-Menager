# version: 1.0
"""Widok zakładki Brygadzista w aktywnym Profilu WM."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any, Callable

from logger import log_akcja
from services.foreman_stats_service import build_snapshot, period_labels

WM_BG = "#121415"
WM_BG_ELEV = "#1A1D1F"
WM_BG_ELEV_2 = "#212529"
WM_TEXT = "#E6E7E8"
WM_TEXT_MUTED = "#A7A9AB"
WM_ACCENT = "#FF6B1A"
WM_DIVIDER = "#2A2E31"

_ABSENT_STATUSES = {"urlop", "l4", "nn", "nieobecny"}


def _txt(value: Any, fallback: str = "—") -> str:
    raw = str(value or "").strip()
    return raw or fallback


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _days(value: Any) -> str:
    try:
        number = float(value or 0)
    except Exception:
        number = 0.0
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _short_dt(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%d-%m-%y %H:%M")
    except Exception:
        return raw[:16].replace("T", " ")


class ForemanProfilePanel(ttk.Frame):
    """Panel zarządczy dostępny wyłącznie dla roli brygadzista."""

    def __init__(self, master, *, owner=None, **kwargs) -> None:
        super().__init__(master, style="WM.Container.TFrame", **kwargs)
        self.owner = owner
        self.period = "month"
        self.snapshot: dict[str, Any] = {}
        self._tabs: dict[str, ttk.Frame] = {}
        self._task_worker = tk.StringVar(value="Wszyscy")
        self._task_status = tk.StringVar(value="Wszystkie")
        self._task_query = tk.StringVar(value="")
        labels = period_labels()
        self._period_label_to_key = {label: key for key, label in labels.items()}
        self._period_key_to_label = labels
        self._stats_period = tk.StringVar(value=labels.get(self.period, "Ten miesiąc"))
        self._status_var = tk.StringVar(value="")
        self._init_styles()
        self._build()
        self.refresh_data()

    def _init_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("Foreman.Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Foreman.Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure(
            "Foreman.Card.TFrame",
            background=WM_BG_ELEV,
            relief="flat",
        )
        style.configure(
            "Foreman.CardTitle.TLabel",
            background=WM_BG_ELEV,
            foreground=WM_TEXT_MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Foreman.CardValue.TLabel",
            background=WM_BG_ELEV,
            foreground=WM_TEXT,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Foreman.CardNote.TLabel",
            background=WM_BG_ELEV,
            foreground=WM_TEXT_MUTED,
            font=("Segoe UI", 9),
        )

    def _build(self) -> None:
        header = ttk.Frame(self, style="WM.Container.TFrame")
        header.pack(fill="x", padx=12, pady=(10, 6))
        left = ttk.Frame(header, style="WM.Container.TFrame")
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(
            left,
            text="PANEL BRYGADZISTY",
            style="WM.H1.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            left,
            text="Podgląd brygady, zadań, urlopów oraz stanu maszyn i narzędzi.",
            style="WM.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        right = ttk.Frame(header, style="WM.Container.TFrame")
        right.pack(side="right")
        ttk.Label(right, textvariable=self._status_var, style="WM.Muted.TLabel").pack(
            side="left", padx=(0, 10)
        )
        ttk.Button(right, text="Odśwież", command=self.refresh_data).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for name in ("Pulpit", "Zespół", "Urlopy", "Zadania", "Sprzęt", "Statystyki"):
            frame = ttk.Frame(self.notebook, style="WM.Container.TFrame")
            self.notebook.add(frame, text=name)
            self._tabs[name] = frame

    def _clear(self, parent: ttk.Frame) -> None:
        for child in parent.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: list[tuple[str, str, int, str]],
        *,
        height: int = 12,
    ) -> ttk.Treeview:
        wrap = ttk.Frame(parent, style="WM.TFrame")
        wrap.pack(fill="both", expand=True)
        keys = [key for key, _label, _width, _anchor in columns]
        tree = ttk.Treeview(
            wrap,
            columns=keys,
            show="headings",
            style="Foreman.Treeview",
            height=height,
        )
        for key, label, width, anchor in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=anchor, stretch=key in {"name", "task", "object", "info", "work"})
        y = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        tree.tag_configure("urgent", foreground="#ef4444")
        tree.tag_configure("warning", foreground="#f59e0b")
        tree.tag_configure("ok", foreground="#22c55e")
        tree.tag_configure("muted", foreground=WM_TEXT_MUTED)
        return tree

    def _card(self, parent: ttk.Frame, title: str, value: str, note: str = "") -> None:
        card = ttk.Frame(parent, style="Foreman.Card.TFrame", padding=12)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(card, text=title, style="Foreman.CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text=value, style="Foreman.CardValue.TLabel").pack(anchor="w", pady=(4, 0))
        if note:
            ttk.Label(card, text=note, style="Foreman.CardNote.TLabel").pack(anchor="w", pady=(2, 0))

    def refresh_data(self) -> None:
        self._status_var.set("Wczytywanie danych…")
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            self.snapshot = build_snapshot(self.period)
        except Exception as exc:
            log_akcja(f"[WM-ERR][FOREMAN] Nie udało się zbudować statystyk: {exc}")
            self.snapshot = {
                "summary": {}, "team": [], "leaves": [], "tasks": [],
                "machines": [], "tools": [], "attention": [],
            }
            self._status_var.set(f"Błąd danych: {exc}")
        else:
            generated = _short_dt(self.snapshot.get("generated_at"))
            self._status_var.set(f"Dane: {generated}")
        self._render_all()

    def _render_all(self) -> None:
        self._render_dashboard()
        self._render_team()
        self._render_leaves()
        self._render_tasks()
        self._render_equipment()
        self._render_stats()

    def _actual_presence_summary(self) -> tuple[int, int, int]:
        team = self.snapshot.get("team") or []
        available = sum(1 for row in team if _norm(row.get("status")) == "dostępny")
        absent = sum(1 for row in team if _norm(row.get("status")) in _ABSENT_STATUSES)
        off = max(0, len(team) - available - absent)
        return available, absent, off

    # ---------------- PULPIT ----------------
    def _render_dashboard(self) -> None:
        parent = self._tabs["Pulpit"]
        self._clear(parent)
        summary = self.snapshot.get("summary") or {}
        available, absent, off = self._actual_presence_summary()
        cards = ttk.Frame(parent, style="WM.Container.TFrame")
        cards.pack(fill="x", padx=8, pady=(8, 10))
        self._card(cards, "PRACOWNICY", str(summary.get("team", 0)), f"Dostępni: {available} • Wolne: {off}")
        self._card(cards, "NIEOBECNI", str(absent), "Urlop / L4 / NN")
        self._card(cards, "ZADANIA", str(summary.get("open_tasks", 0)), f"Pilne: {summary.get('urgent_tasks', 0)}")
        problems = int(summary.get("machine_alerts", 0) or 0) + int(summary.get("tool_alerts", 0) or 0)
        self._card(cards, "AWARIE / PROBLEMY", str(problems), f"Maszyny: {summary.get('machine_alerts', 0)} • Narzędzia: {summary.get('tool_alerts', 0)}")

        team_box = ttk.LabelFrame(parent, text="Dzisiaj — zespół", style="WM.Section.TLabelframe", padding=8)
        team_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tree = self._make_tree(team_box, [
            ("name", "Pracownik", 180, "w"),
            ("status", "Status", 105, "center"),
            ("shift", "Zmiana", 155, "center"),
            ("open", "Zadania", 75, "center"),
            ("progress", "W toku", 70, "center"),
            ("urgent", "Pilne", 60, "center"),
            ("work", "Aktualna praca", 340, "w"),
        ], height=7)
        for row in self.snapshot.get("team") or []:
            status = _txt(row.get("status"))
            tag = "urgent" if _norm(status) in _ABSENT_STATUSES else ("muted" if _norm(status) == "wolne" else "ok")
            tree.insert("", "end", values=(
                row.get("name"), status, row.get("shift"), row.get("open", 0),
                row.get("in_progress", 0), row.get("urgent", 0), row.get("current_work") or "—",
            ), tags=(tag,))

        attention_box = ttk.LabelFrame(parent, text="Wymaga uwagi", style="WM.Section.TLabelframe", padding=8)
        attention_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        attention = self._make_tree(attention_box, [
            ("type", "Typ", 110, "w"),
            ("object", "Obiekt", 300, "w"),
            ("info", "Informacja", 520, "w"),
        ], height=5)
        rows = self.snapshot.get("attention") or []
        if rows:
            for row in rows:
                attention.insert("", "end", values=(row.get("type"), row.get("object"), row.get("info")), tags=("warning",))
        else:
            attention.insert("", "end", values=("—", "Brak", "Brak pilnych zdarzeń do pokazania."), tags=("ok",))

    # ---------------- ZESPÓŁ ----------------
    def _render_team(self) -> None:
        parent = self._tabs["Zespół"]
        self._clear(parent)
        table_box = ttk.LabelFrame(parent, text=f"Zespół — {self.snapshot.get('period_label', '')}", style="WM.Section.TLabelframe", padding=8)
        table_box.pack(fill="both", expand=True, padx=8, pady=8)
        tree = self._make_tree(table_box, [
            ("name", "Pracownik", 185, "w"),
            ("role", "Rola", 110, "w"),
            ("shift", "Zmiana", 145, "center"),
            ("status", "Dzisiaj", 100, "center"),
            ("open", "Otwarte", 70, "center"),
            ("done", "Wykonane", 75, "center"),
            ("urgent", "Pilne", 60, "center"),
            ("tools", "Narzędzia", 75, "center"),
            ("machines", "Maszyny", 70, "center"),
            ("services", "Serwisy", 65, "center"),
            ("leave", "Urlop poz.", 80, "center"),
        ], height=13)
        details_by_iid: dict[str, dict] = {}
        for row in self.snapshot.get("team") or []:
            iid = tree.insert("", "end", values=(
                row.get("name"), row.get("role"), row.get("shift"), row.get("status"),
                row.get("open", 0), row.get("done", 0), row.get("urgent", 0),
                row.get("tools", 0), row.get("machines", 0), row.get("services", 0),
                _days(row.get("leave_remaining")),
            ))
            details_by_iid[iid] = row

        detail = tk.Text(parent, height=6, wrap="word", bg=WM_BG_ELEV, fg=WM_TEXT, insertbackground=WM_TEXT, relief="flat", padx=10, pady=8)
        detail.pack(fill="x", padx=8, pady=(0, 8))
        detail.configure(state="disabled")

        def show_details(_event=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            row = details_by_iid.get(sel[0], {})
            top_tools = ", ".join(f"{name} ({count})" for name, count in row.get("top_tools", [])) or "—"
            top_machines = ", ".join(f"{name} ({count})" for name, count in row.get("top_machines", [])) or "—"
            text = (
                f"{row.get('name')} (@{row.get('login')})\n"
                f"Aktualna praca: {row.get('current_work') or '—'}\n"
                f"Najczęściej przy narzędziach: {top_tools}\n"
                f"Najczęściej przy maszynach/serwisach: {top_machines}"
            )
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", text)
            detail.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show_details)
        if tree.get_children():
            first = tree.get_children()[0]
            tree.selection_set(first)
            show_details()

    # ---------------- URLOPY ----------------
    def _render_leaves(self) -> None:
        parent = self._tabs["Urlopy"]
        self._clear(parent)
        year = datetime.now().year
        head = ttk.Frame(parent, style="WM.Container.TFrame")
        head.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(head, text=f"Bilans nieobecności — {year}", style="WM.H1.TLabel").pack(side="left")
        source = _txt(self.snapshot.get("leaves_source"), "brak danych")
        ttk.Label(head, text=f"Źródło: {source}", style="WM.Muted.TLabel").pack(side="right")
        box = ttk.Frame(parent, style="WM.Container.TFrame")
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tree = self._make_tree(box, [
            ("name", "Pracownik", 220, "w"),
            ("limit", "Limit", 85, "center"),
            ("used", "Wykorzystano", 105, "center"),
            ("remaining", "Pozostało", 100, "center"),
            ("l4", "L4", 80, "center"),
            ("nn", "NN", 80, "center"),
            ("late", "Spóźnienia", 110, "center"),
        ], height=16)
        for row in self.snapshot.get("leaves") or []:
            remaining = float(row.get("remaining") or 0)
            tag = "urgent" if remaining < 0 else ""
            tree.insert("", "end", values=(
                row.get("name"), _days(row.get("limit")), _days(row.get("used")),
                _days(remaining), _days(row.get("l4")), _days(row.get("nn")),
                f"{int(row.get('late_minutes') or 0)} min",
            ), tags=(tag,) if tag else ())

    # ---------------- ZADANIA ----------------
    def _render_tasks(self) -> None:
        parent = self._tabs["Zadania"]
        self._clear(parent)
        toolbar = ttk.Frame(parent, style="WM.Container.TFrame")
        toolbar.pack(fill="x", padx=8, pady=8)
        ttk.Label(toolbar, text="Pracownik:", style="WM.Muted.TLabel").pack(side="left")
        workers = ["Wszyscy"] + [row.get("name") or row.get("login") for row in self.snapshot.get("team") or []]
        worker_combo = ttk.Combobox(toolbar, textvariable=self._task_worker, values=workers, state="readonly", width=22)
        worker_combo.pack(side="left", padx=(4, 10))
        if self._task_worker.get() not in workers:
            self._task_worker.set("Wszyscy")
        ttk.Label(toolbar, text="Status:", style="WM.Muted.TLabel").pack(side="left")
        status_combo = ttk.Combobox(toolbar, textvariable=self._task_status, values=["Wszystkie", "Otwarte", "W toku", "Pilne", "Zrobione"], state="readonly", width=14)
        status_combo.pack(side="left", padx=(4, 10))
        ttk.Label(toolbar, text="Szukaj:", style="WM.Muted.TLabel").pack(side="left")
        query = ttk.Entry(toolbar, textvariable=self._task_query, width=28)
        query.pack(side="left", padx=(4, 8))
        ttk.Button(toolbar, text="Filtruj", command=self._reload_task_tree).pack(side="left")

        box = ttk.Frame(parent, style="WM.Container.TFrame")
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._task_tree = self._make_tree(box, [
            ("worker", "Pracownik", 150, "w"),
            ("task", "Zadanie", 310, "w"),
            ("object", "Dotyczy", 300, "w"),
            ("status", "Status", 105, "center"),
            ("deadline", "Termin", 110, "center"),
            ("done", "Wykonano", 125, "center"),
        ], height=16)
        worker_combo.bind("<<ComboboxSelected>>", lambda _e: self._reload_task_tree())
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self._reload_task_tree())
        query.bind("<Return>", lambda _e: self._reload_task_tree())
        self._reload_task_tree()

    def _reload_task_tree(self) -> None:
        tree = getattr(self, "_task_tree", None)
        if tree is None or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        chosen_worker = _norm(self._task_worker.get())
        chosen_status = _norm(self._task_status.get())
        query = _norm(self._task_query.get())
        name_to_login = {_norm(row.get("name")): _norm(row.get("login")) for row in self.snapshot.get("team") or []}
        worker_login = name_to_login.get(chosen_worker, "")
        for row in self.snapshot.get("tasks") or []:
            worker = _txt(row.get("worker"), "—")
            if chosen_worker != "wszyscy" and _norm(worker) not in {chosen_worker, worker_login}:
                continue
            done = bool(row.get("done"))
            if chosen_status == "otwarte" and done:
                continue
            if chosen_status == "zrobione" and not done:
                continue
            if chosen_status == "w toku" and not bool(row.get("in_progress")):
                continue
            if chosen_status == "pilne" and not bool(row.get("urgent")):
                continue
            haystack = " ".join(_txt(row.get(key), "") for key in ("title", "object", "id", "worker", "status")).casefold()
            if query and query not in haystack:
                continue
            tag = "urgent" if row.get("urgent") and not done else ("ok" if done else "")
            tree.insert("", "end", values=(
                worker, row.get("title"), row.get("object"), row.get("status"),
                _short_dt(row.get("deadline")), _short_dt(row.get("done_at")) if done else "—",
            ), tags=(tag,) if tag else ())

    # ---------------- SPRZĘT ----------------
    def _render_equipment(self) -> None:
        parent = self._tabs["Sprzęt"]
        self._clear(parent)
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        machines_tab = ttk.Frame(nb, style="WM.Container.TFrame")
        tools_tab = ttk.Frame(nb, style="WM.Container.TFrame")
        nb.add(machines_tab, text="Maszyny")
        nb.add(tools_tab, text="Narzędzia")

        m_tree = self._make_tree(machines_tab, [
            ("id", "Nr", 80, "center"),
            ("name", "Maszyna", 280, "w"),
            ("status", "Status", 130, "center"),
            ("issues", "Awarie", 80, "center"),
            ("downtime", "Przestój", 110, "center"),
            ("services", "Serwisy", 80, "center"),
            ("last", "Ostatnia awaria", 120, "center"),
        ], height=16)
        formatter = self.snapshot.get("format_minutes")
        for row in self.snapshot.get("machines") or []:
            minutes = int(row.get("downtime_minutes") or 0)
            downtime = formatter(minutes) if callable(formatter) else f"{minutes} min"
            tag = "urgent" if row.get("current_problem") else ""
            m_tree.insert("", "end", values=(row.get("id"), row.get("name"), row.get("status"), row.get("issues", 0), downtime, row.get("services", 0), row.get("last_issue")), tags=(tag,) if tag else ())

        t_tree = self._make_tree(tools_tab, [
            ("id", "Nr", 80, "center"),
            ("name", "Narzędzie", 320, "w"),
            ("status", "Status", 140, "center"),
            ("problems", "Problemy", 90, "center"),
            ("tasks", "Wyk. zadania", 100, "center"),
            ("visits", "Wizyty", 80, "center"),
            ("last", "Ostatni problem", 120, "center"),
        ], height=16)
        for row in self.snapshot.get("tools") or []:
            tag = "urgent" if row.get("current_problem") else ""
            t_tree.insert("", "end", values=(row.get("id"), row.get("name"), row.get("status"), row.get("problems", 0), row.get("done_tasks", 0), row.get("visits", 0), row.get("last_problem")), tags=(tag,) if tag else ())

    # ---------------- STATYSTYKI ----------------
    def _render_stats(self) -> None:
        parent = self._tabs["Statystyki"]
        self._clear(parent)
        top = ttk.Frame(parent, style="WM.Container.TFrame")
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Okres:", style="WM.Muted.TLabel").pack(side="left")
        period_combo = ttk.Combobox(top, textvariable=self._stats_period, values=list(self._period_label_to_key.keys()), state="readonly", width=18)
        period_combo.pack(side="left", padx=(4, 8))
        period_combo.bind("<<ComboboxSelected>>", self._change_period)
        ttk.Label(top, text=f"Aktualnie: {self.snapshot.get('period_label', '')}", style="WM.Muted.TLabel").pack(side="left", padx=(8, 0))

        summary = self.snapshot.get("summary") or {}
        cards = ttk.Frame(parent, style="WM.Container.TFrame")
        cards.pack(fill="x", padx=8, pady=(0, 10))
        self._card(cards, "WYKONANE ZADANIA", str(summary.get("done_period", 0)), self.snapshot.get("period_label", ""))
        self._card(cards, "SERWISY MASZYN", str(summary.get("services_period", 0)), self.snapshot.get("period_label", ""))
        self._card(cards, "AWARIE MASZYN", str(summary.get("machine_issues_period", 0)), self.snapshot.get("period_label", ""))
        self._card(cards, "PROBLEMY NARZĘDZI", str(summary.get("tool_problems_period", 0)), self.snapshot.get("period_label", ""))

        body = ttk.Frame(parent, style="WM.Container.TFrame")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        workers_box = ttk.LabelFrame(body, text="Pracownicy — wykonane zadania", style="WM.Section.TLabelframe", padding=6)
        workers_box.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        w_tree = self._make_tree(workers_box, [("name", "Pracownik", 220, "w"), ("done", "Wykonane", 90, "center"), ("services", "Serwisy", 80, "center")], height=6)
        for row in sorted(self.snapshot.get("team") or [], key=lambda item: (-int(item.get("done", 0)), item.get("name", ""))):
            w_tree.insert("", "end", values=(row.get("name"), row.get("done", 0), row.get("services", 0)))

        machine_box = ttk.LabelFrame(body, text="Maszyny — awaryjność", style="WM.Section.TLabelframe", padding=6)
        machine_box.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        m_tree = self._make_tree(machine_box, [("name", "Maszyna", 260, "w"), ("issues", "Awarie", 70, "center"), ("down", "Przestój", 100, "center")], height=6)
        formatter = self.snapshot.get("format_minutes")
        for row in (self.snapshot.get("machines") or [])[:20]:
            minutes = int(row.get("downtime_minutes") or 0)
            m_tree.insert("", "end", values=(f"{row.get('id')} — {row.get('name')}", row.get("issues", 0), formatter(minutes) if callable(formatter) else f"{minutes} min"))

        tools_box = ttk.LabelFrame(body, text="Narzędzia — problemy", style="WM.Section.TLabelframe", padding=6)
        tools_box.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))
        t_tree = self._make_tree(tools_box, [("name", "Narzędzie", 260, "w"), ("issues", "Problemy", 80, "center"), ("tasks", "Zadania", 80, "center")], height=6)
        for row in (self.snapshot.get("tools") or [])[:20]:
            t_tree.insert("", "end", values=(f"{row.get('id')} — {row.get('name')}", row.get("problems", 0), row.get("done_tasks", 0)))

        absence_box = ttk.LabelFrame(body, text="Nieobecności — bieżący rok", style="WM.Section.TLabelframe", padding=6)
        absence_box.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))
        a_tree = self._make_tree(absence_box, [("name", "Pracownik", 200, "w"), ("leave", "Urlop", 70, "center"), ("l4", "L4", 60, "center"), ("nn", "NN", 60, "center")], height=6)
        for row in self.snapshot.get("leaves") or []:
            a_tree.insert("", "end", values=(row.get("name"), _days(row.get("used")), _days(row.get("l4")), _days(row.get("nn"))))

    def _change_period(self, _event=None) -> None:
        selected = self._stats_period.get()
        key = self._period_label_to_key.get(selected)
        if not key or key == self.period:
            return
        self.period = key
        self.refresh_data()


def build_profile_with_foreman_tabs(
    parent: ttk.Frame,
    owner,
    profile_renderer: Callable[[ttk.Frame], None],
) -> ttk.Notebook:
    """Zbuduj Profil + Brygadzista; panel brygadzisty jest ładowany leniwie."""
    notebook = ttk.Notebook(parent)
    notebook.pack(fill="both", expand=True)
    profile_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
    foreman_tab = ttk.Frame(notebook, style="WM.Container.TFrame")
    notebook.add(profile_tab, text="Profil")
    notebook.add(foreman_tab, text="Brygadzista")
    profile_renderer(profile_tab)
    state = {"built": False}

    def ensure_foreman() -> None:
        if state["built"]:
            return
        state["built"] = True
        panel = ForemanProfilePanel(foreman_tab, owner=owner)
        panel.pack(fill="both", expand=True)
        setattr(owner, "_wm_foreman_panel", panel)

    def on_tab_changed(_event=None) -> None:
        try:
            selected = notebook.tab(notebook.select(), "text")
        except Exception:
            return
        setattr(owner, "_wm_profile_main_tab", str(selected))
        if selected == "Brygadzista":
            ensure_foreman()

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed, add="+")
    previous = str(getattr(owner, "_wm_profile_main_tab", "Profil") or "Profil")
    if previous == "Brygadzista":
        notebook.select(foreman_tab)
        ensure_foreman()
    else:
        notebook.select(profile_tab)
    return notebook


__all__ = ["ForemanProfilePanel", "build_profile_with_foreman_tabs"]
