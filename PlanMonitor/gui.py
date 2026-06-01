"""Tkinter user interface for the standalone Plan Monitor application."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

try:
    from .main import (APP_DIR, CHANGE_LABELS, SUPPORTED_EXTENSIONS, PlanMonitor,
                       display_row, export_changes, load_history, save_config)
except ImportError:
    from main import (APP_DIR, CHANGE_LABELS, SUPPORTED_EXTENSIONS, PlanMonitor,
                      display_row, export_changes, load_history, save_config)

BG = "#171b22"
PANEL = "#222832"
TEXT = "#f2f4f8"
MUTED = "#aab4c3"
ACCENT = "#2f80ed"
SUCCESS = "#43a047"


class MonitorApp(tk.Tk):
    """Dark standalone GUI with a non-blocking monitoring worker."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Plan Monitor")
        self.geometry("1240x720")
        self.minsize(960, 620)
        self.configure(bg=BG)
        self.monitor = PlanMonitor()
        self.results: queue.Queue[Any] = queue.Queue()
        self.last_changes: list[dict[str, Any]] = []
        self._checking = False
        self._timer: str | None = None
        self._build_styles()
        self._build_ui()
        self.after(100, self._first_run)
        self.after(200, self._poll_results)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT,
                        fieldbackground=PANEL, rowheight=28)
        style.configure("Treeview.Heading", background="#303846",
                        foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)])

    def _build_ui(self) -> None:
        tk.Label(self, text="PLAN MONITOR", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=22,
                                                      pady=(18, 12))
        status = tk.Frame(self, bg=PANEL, padx=16, pady=12)
        status.pack(fill="x", padx=22)
        self.status_vars = {
            "Plik": tk.StringVar(value="—"),
            "Status": tk.StringVar(value="Oczekiwanie na konfigurację"),
            "Ostatnie sprawdzenie": tk.StringVar(value="—"),
            "Ostatnia zmiana pliku": tk.StringVar(value="—"),
        }
        for row, (label, variable) in enumerate(self.status_vars.items()):
            tk.Label(status, text=f"{label}:", width=23, anchor="w",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).grid(
                         row=row, column=0, sticky="w", pady=2)
            tk.Label(status, textvariable=variable, anchor="w", bg=PANEL,
                     fg=TEXT, font=("Segoe UI", 10, "bold")).grid(
                         row=row, column=1, sticky="w", pady=2)

        buttons = tk.Frame(self, bg=BG)
        buttons.pack(fill="x", padx=22, pady=12)
        for text, command in (
            ("Sprawdź teraz", lambda: self._check_async(force=True)),
            ("Pokaż zmiany", self._show_latest),
            ("Historia zmian", self._show_history),
            ("Ustawienia", self._open_settings),
            ("Eksportuj raport", self._export),
        ):
            tk.Button(buttons, text=text, command=command, bg=ACCENT,
                      fg="white", activebackground="#2469c3", bd=0,
                      padx=14, pady=8, font=("Segoe UI", 9, "bold")).pack(
                          side="left", padx=(0, 8))
        self.summary = tk.StringVar(value="Brak odczytanego raportu")
        tk.Label(buttons, textvariable=self.summary, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="right")

        columns = ("date", "type", "order", "symbol", "old", "new",
                   "department")
        self.table = ttk.Treeview(self, columns=columns, show="headings")
        headings = ("Data", "Typ zmiany", "Nr zlecenia", "Symbol",
                    "Stara wartość", "Nowa wartość", "Dotyczy działu")
        widths = (160, 110, 110, 220, 130, 130, 160)
        for column, heading, width in zip(columns, headings, widths):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="w")
        self.table.pack(fill="both", expand=True, padx=22, pady=(0, 20))

    def _first_run(self) -> None:
        plan_file = self.monitor.config.get("plan_file", "")
        if not plan_file:
            messagebox.showinfo("Plan Monitor", "Wybierz plik planu produkcji")
            plan_file = filedialog.askopenfilename(
                title="Wybierz plik planu produkcji",
                filetypes=[("Pliki Excel", "*.xls *.xlsx *.xlsm")],
            )
            if not plan_file:
                return
            self.monitor.config["plan_file"] = plan_file
            save_config(self.monitor.config, self.monitor.config_path)
        self.status_vars["Plik"].set(plan_file)
        self.status_vars["Status"].set("Monitorowanie aktywne")
        self._check_async(force=True)
        self._schedule_next()

    def _schedule_next(self) -> None:
        if self._timer:
            self.after_cancel(self._timer)
        seconds = max(1, int(self.monitor.config["check_interval_seconds"]))
        self._timer = self.after(seconds * 1000, self._scheduled_check)

    def _scheduled_check(self) -> None:
        self._check_async(force=False)
        self._schedule_next()

    def _check_async(self, force: bool) -> None:
        if not self.monitor.config.get("plan_file"):
            self._first_run()
            return
        if self._checking:
            return
        self._checking = True
        self.status_vars["Status"].set("Sprawdzanie planu…")
        threading.Thread(target=self._worker, args=(force,), daemon=True).start()

    def _worker(self, force: bool) -> None:
        self.results.put(self.monitor.check(force=force))

    def _poll_results(self) -> None:
        try:
            while True:
                result = self.results.get_nowait()
                self._handle_result(result)
        except queue.Empty:
            pass
        self.after(200, self._poll_results)

    def _handle_result(self, result: Any) -> None:
        self._checking = False
        self.status_vars["Ostatnie sprawdzenie"].set(result.checked_at)
        if result.file_modified_at:
            self.status_vars["Ostatnia zmiana pliku"].set(
                result.file_modified_at
            )
        if result.status == "error":
            self.status_vars["Status"].set("Błąd dostępu do pliku")
            messagebox.showwarning("Plan Monitor", result.message)
            return
        self.status_vars["Status"].set("Monitorowanie aktywne")
        if result.changes:
            self.last_changes = result.changes
            self._render(self.last_changes)
            messagebox.showinfo("Plan Monitor", result.message)
        else:
            self.summary.set(result.message)

    def _render(self, changes: list[dict[str, Any]]) -> None:
        self.table.delete(*self.table.get_children())
        for change in changes:
            self.table.insert("", "end", values=display_row(change))
        counts = Counter(change["type"] for change in changes)
        self.summary.set(
            f'Nowe: {counts["new"]}  |  Ilość: {counts["quantity_changed"]}'
            f'  |  Terminy: {counts["deadline_changed"]}'
            f'  |  Usunięte: {counts["removed"]}'
        )

    def _show_latest(self) -> None:
        self._render(self.last_changes)

    def _show_history(self) -> None:
        self._render(load_history(self.monitor.history_path))

    def _export(self) -> None:
        if not self.last_changes:
            messagebox.showinfo("Plan Monitor", "Brak zmian do eksportu.")
            return
        path = filedialog.asksaveasfilename(
            title="Eksportuj raport zmian",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("TXT", "*.txt")],
        )
        if path:
            export_changes(self.last_changes, path)
            messagebox.showinfo("Plan Monitor", "Raport został zapisany.")

    def _open_settings(self) -> None:
        SettingsDialog(self, self.monitor)


class SettingsDialog(tk.Toplevel):
    """Settings editor including manual spreadsheet column mapping."""

    def __init__(self, parent: MonitorApp, monitor: PlanMonitor) -> None:
        super().__init__(parent)
        self.parent = parent
        self.monitor = monitor
        self.title("Ustawienia Plan Monitor")
        self.geometry("620x430")
        self.configure(bg=BG)
        config = monitor.config
        mapping = config["column_mapping"]
        self.values = {
            "plan_file": tk.StringVar(value=config.get("plan_file", "")),
            "check_interval_seconds": tk.StringVar(
                value=str(config.get("check_interval_seconds", 60))
            ),
            "department_keywords": tk.StringVar(
                value=", ".join(config.get("department_keywords", []))
            ),
            "order": tk.StringVar(value=mapping.get("order", "")),
            "symbol": tk.StringVar(value=mapping.get("symbol", "")),
            "quantity": tk.StringVar(value=mapping.get("quantity", "")),
            "deadline": tk.StringVar(value=mapping.get("deadline", "")),
        }
        labels = (
            ("Plik planu", "plan_file"),
            ("Interwał sprawdzania (sekundy)", "check_interval_seconds"),
            ("Słowa kluczowe działu (po przecinku)", "department_keywords"),
            ("Kolumna: nr zlecenia", "order"),
            ("Kolumna: symbol / opis (np. B)", "symbol"),
            ("Kolumna: ilość", "quantity"),
            ("Kolumna: termin", "deadline"),
        )
        for row, (label, key) in enumerate(labels):
            tk.Label(self, text=label, bg=BG, fg=TEXT, anchor="w").grid(
                row=row, column=0, sticky="w", padx=16, pady=8)
            tk.Entry(self, textvariable=self.values[key], width=43,
                     bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat").grid(
                         row=row, column=1, sticky="ew", padx=8, pady=8)
        tk.Button(self, text="Wybierz plik", command=self._select_file,
                  bg=ACCENT, fg="white", bd=0, padx=10, pady=5).grid(
                      row=0, column=2, padx=8)
        tk.Button(self, text="Zapisz", command=self._save, bg=SUCCESS,
                  fg="white", bd=0, padx=18, pady=8).grid(
                      row=len(labels), column=1, sticky="e", pady=16)

    def _select_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz plik planu produkcji",
            filetypes=[("Pliki Excel", "*.xls *.xlsx *.xlsm")],
        )
        if path and Path(path).suffix.lower() in SUPPORTED_EXTENSIONS:
            self.values["plan_file"].set(path)

    def _save(self) -> None:
        try:
            interval = max(1, int(self.values["check_interval_seconds"].get()))
        except ValueError:
            messagebox.showerror("Plan Monitor", "Interwał musi być liczbą.")
            return
        config = {
            "plan_file": self.values["plan_file"].get().strip(),
            "check_interval_seconds": interval,
            "department_keywords": [
                item.strip() for item in
                self.values["department_keywords"].get().split(",")
                if item.strip()
            ],
            "column_mapping": {
                key: self.values[key].get().strip()
                for key in ("order", "symbol", "quantity", "deadline")
            },
        }
        save_config(config, self.monitor.config_path)
        self.monitor.reload_config()
        self.parent.status_vars["Plik"].set(config["plan_file"] or "—")
        self.parent._schedule_next()
        self.destroy()


def run() -> None:
    """Start the Tk event loop."""
    MonitorApp().mainloop()
