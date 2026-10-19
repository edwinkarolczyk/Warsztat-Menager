# WM-VERSION: 0.1
# Plik: planista_excel_dual_ui.py
"""Jedno okno zarządzania zewnętrznym planem Excel; bez zmiany silnika zleceń."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from planista_excel_auto_runtime import load_auto_state, save_auto_state
from planista_excel_dual_runtime import load_dual_state, resolve_dual_conflict


def show_excel_sources_window(owner) -> None:
    import planista_excel_runtime as runtime

    existing = getattr(owner.root, "_wm_excel_sources_window", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass

    state = load_auto_state()
    window = tk.Toplevel(owner.root)
    window.title("Planista — źródła Excel, zmiany i akceptacja")
    window.geometry("1210x740")
    window.minsize(920, 560)
    window.transient(owner.root)
    owner.root._wm_excel_sources_window = window

    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=10, pady=(10, 3))
    sources_tab = ttk.Frame(notebook, padding=12)
    changes_tab = ttk.Frame(notebook, padding=12)
    conflicts_tab = ttk.Frame(notebook, padding=12)
    history_tab = ttk.Frame(notebook, padding=12)
    notebook.add(sources_tab, text="Źródła i automat")
    notebook.add(changes_tab, text="Zmiany / zlecenia")
    notebook.add(conflicts_tab, text="Konflikty A ↔ B")
    notebook.add(history_tab, text="Historia i wydruk")

    source_a = tk.StringVar(window, value=str(state.get("source_path") or ""))
    source_b = tk.StringVar(window, value=str(state.get("source_path_b") or ""))
    monitor_var = tk.BooleanVar(window, value=bool(state.get("enabled")))
    accept_var = tk.BooleanVar(window, value=bool(state.get("auto_accept")))
    print_var = tk.BooleanVar(window, value=bool(state.get("auto_print")))
    interval_var = tk.StringVar(window, value=str(state.get("interval_minutes") or 1))
    feedback = tk.StringVar(window, value="Gotowe. Wskaż dwa pliki i włącz monitorowanie.")
    source_status: dict[str, tk.StringVar] = {}
    latest = {"payload": getattr(owner, "_excel_plan_import", None)}

    def save_options() -> bool:
        from planista_excel_auto_runtime import normalize_interval_minutes
        a, b = source_a.get().strip(), source_b.get().strip()
        if monitor_var.get() and (not a or not b):
            messagebox.showwarning("Plan Excel", "Do automatycznego monitoringu A+B wskaż oba pliki.", parent=window)
            return False
        if monitor_var.get() and (not Path(a).is_file() or not Path(b).is_file()):
            messagebox.showwarning("Plan Excel", "Nie można włączyć monitoringu: jeden z plików jest niedostępny.", parent=window)
            return False
        interval = normalize_interval_minutes(interval_var.get())
        interval_var.set(str(interval))
        save_auto_state(
            enabled=monitor_var.get(), source_path=a, source_path_b=b,
            interval_minutes=interval, auto_accept=accept_var.get(), auto_print=print_var.get(),
        )
        owner._excel_auto_source_path = a
        owner._excel_auto_var.set(monitor_var.get())
        owner._excel_auto_interval_var.set(str(interval))
        owner._excel_auto_accept_var.set(accept_var.get())
        owner._excel_auto_print_var.set(print_var.get())
        runtime.sync_global_excel_watcher(owner.root)
        feedback.set("Ustawienia zapamiętane. Monitoring działa od uruchomienia WM.")
        return True

    def choose_file(variable: tk.StringVar) -> None:
        candidate = filedialog.askopenfilename(
            parent=window, title="Wybierz plik planu produkcji",
            filetypes=(("Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")),
        )
        if candidate:
            variable.set(str(Path(candidate).resolve()))
            if monitor_var.get():
                monitor_var.set(False)
            save_options()

    ttk.Label(
        sources_tab,
        text="Oba źródła są równorzędne. WM czyta tylko chwilowe kopie plików.",
    ).pack(anchor="w", pady=(0, 12))
    for label, variable in (("A — Oryginał", source_a), ("B — Kopia", source_b)):
        outer = ttk.LabelFrame(sources_tab, text=label, padding=9)
        outer.pack(fill="x", pady=(0, 8))
        line = ttk.Frame(outer)
        line.pack(fill="x")
        entry = ttk.Entry(line, textvariable=variable, state="readonly")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(line, text="Wybierz plik…", command=lambda var=variable: choose_file(var)).pack(side="left")
        source_status[label[0]] = tk.StringVar(window, value="Jeszcze nie odczytano")
        ttk.Label(outer, textvariable=source_status[label[0]]).pack(anchor="w", pady=(5, 0))
    options = ttk.LabelFrame(sources_tab, text="Automat", padding=10)
    options.pack(fill="x", pady=(5, 0))
    ttk.Checkbutton(
        options, text="Monitoruj oba pliki od uruchomienia WM",
        variable=monitor_var,
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=3)
    ttk.Label(options, text="Sprawdzaj co").grid(row=1, column=0, sticky="w", pady=3)
    ttk.Spinbox(options, from_=1, to=60, textvariable=interval_var, width=5).grid(
        row=1, column=1, sticky="w", padx=(5, 4), pady=3
    )
    ttk.Label(options, text="minut (1–60)").grid(row=1, column=2, sticky="w", pady=3)
    ttk.Checkbutton(
        options, text="Automatycznie akceptuj bezpieczne zlecenia (opcjonalnie)",
        variable=accept_var,
    ).grid(row=2, column=0, columnspan=3, sticky="w", pady=3)
    ttk.Checkbutton(
        options, text="Drukuj nowe zlecenia po ich utworzeniu w WM",
        variable=print_var,
    ).grid(row=3, column=0, columnspan=3, sticky="w", pady=3)
    ttk.Button(options, text="Zapisz ustawienia", command=save_options).grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(12, 0)
    )

    changes_tab.rowconfigure(1, weight=1)
    changes_tab.columnconfigure(0, weight=1)
    change_actions = ttk.Frame(changes_tab)
    change_actions.grid(row=0, column=0, sticky="ew", pady=(0, 7))
    change_summary = tk.StringVar(window, value="Brak bieżącej analizy.")
    columns = ("source", "order", "product", "qty", "date", "status", "note")
    labels = ("Excel", "Nr zlec.", "Produkt", "Ilość", "Termin", "Dopasowanie", "Uwagi")
    widths = (75, 92, 325, 75, 115, 155, 380)
    body = ttk.Frame(changes_tab)
    body.grid(row=1, column=0, sticky="nsew")
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)
    tree = ttk.Treeview(body, columns=columns, show="headings")
    for col, label, width in zip(columns, labels, widths):
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor="w", stretch=col in {"product", "note"})
    tree.grid(row=0, column=0, sticky="nsew")
    ttk.Scrollbar(body, orient="vertical", command=tree.yview).grid(row=0, column=1, sticky="ns")
    ttk.Scrollbar(body, orient="horizontal", command=tree.xview).grid(row=1, column=0, sticky="ew")
    tree.configure(yscrollcommand=lambda first, last: None)
    ttk.Label(changes_tab, textvariable=change_summary).grid(row=2, column=0, sticky="w", pady=(8, 0))

    conflicts_tab.rowconfigure(1, weight=1)
    conflicts_tab.columnconfigure(0, weight=1)
    ttk.Label(
        conflicts_tab, text="Rozbieżności blokują automatyczne zapisanie danej pozycji."
    ).grid(row=0, column=0, sticky="w")
    conflict_tree = ttk.Treeview(
        conflicts_tab, columns=("key", "a", "b", "reason"), show="headings", height=11
    )
    for col, label, width in (
        ("key", "Zlecenie / produkt", 245),
        ("a", "Excel A", 270),
        ("b", "Excel B", 270),
        ("reason", "Przyczyna", 350),
    ):
        conflict_tree.heading(col, text=label)
        conflict_tree.column(col, width=width, stretch=col in {"a", "b", "reason"})
    conflict_tree.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
    conflict_records = {}

    history_tab.rowconfigure(0, weight=1)
    history_tab.columnconfigure(0, weight=1)
    history_text = tk.Text(history_tab, wrap="word", state="disabled")
    history_text.grid(row=0, column=0, sticky="nsew")
    ttk.Scrollbar(history_tab, orient="vertical", command=history_text.yview).grid(
        row=0, column=1, sticky="ns"
    )

    def render(payload: dict | None = None) -> None:
        if isinstance(payload, dict):
            latest["payload"] = payload
            owner._excel_plan_import = payload
        data = latest["payload"] if isinstance(latest["payload"], dict) else {}
        tree.delete(*tree.get_children())
        for row in data.get("rows") or []:
            if not isinstance(row, dict):
                continue
            tree.insert("", "end", values=(
                row.get("source_tag", "A"), row.get("nr_zlec", ""),
                row.get("produkt", ""), row.get("ilosc", ""),
                row.get("data_wysylki", ""),
                row.get("match_category") or row.get("match_status", ""),
                row.get("match_note", ""),
            ))
        conflict_tree.delete(*conflict_tree.get_children())
        conflict_records.clear()
        for idx, conflict in enumerate(data.get("dual_conflicts") or []):
            def describe(items):
                if not items:
                    return "Brak pozycji"
                row = items[0]
                return f"{row.get('ilosc', '—')} szt. | {row.get('data_wysylki') or '—'} | {row.get('proces') or '—'}"
            iid = str(idx)
            conflict_records[iid] = conflict
            conflict_tree.insert("", "end", iid=iid, values=(
                conflict.get("key", ""), describe(conflict.get("A")),
                describe(conflict.get("B")), conflict.get("reason", ""),
            ))
        counts = data.get("match_summary") or {}
        change_summary.set(
            f"Pozycje: {len(data.get('rows') or [])}   |   "
            f"Znalezione: {counts.get('Znaleziony w WM', 0)}   |   "
            f"Konflikty A/B: {len(data.get('dual_conflicts') or [])}   |   "
            f"Odczyt niepełny: {len(data.get('dual_source_errors') or [])}"
        )
        state_now = load_dual_state()
        for label in ("A", "B"):
            record = state_now.get("sources", {}).get(label) or {}
            source_status[label].set(
                f"Status: {record.get('status') or 'Nie odczytano'}  |  "
                f"Ostatni odczyt: {record.get('checked_at') or '—'}"
            )
        history_text.configure(state="normal")
        history_text.delete("1.0", "end")
        for event in reversed((state_now.get("history") or [])[-100:]):
            history_text.insert(
                "end", f"{event.get('at', '')}  |  {event.get('event', '')}"
                f"  {event.get('key', '')}  {event.get('decision', '')}"
                f"  {event.get('changes', '')}  {event.get('errors', '')}\n"
            )
        history_text.configure(state="disabled")

    scanning = {"active": False}

    def scan_now() -> None:
        if scanning["active"] or not save_options():
            return
        if not source_a.get().strip():
            messagebox.showwarning("Plan Excel", "Najpierw wskaż Excel A.", parent=window)
            return
        scanning["active"] = True
        feedback.set("Odczytuję oba Excele z odłączonych kopii…")
        def worker():
            try:
                payload = runtime._load_auto_payload(owner, source_a.get().strip())
                error = ""
            except Exception as exc:
                payload, error = None, str(exc)
            def finish():
                scanning["active"] = False
                if error:
                    feedback.set("Błąd odczytu: " + error)
                else:
                    render(payload)
                    feedback.set("Zakończono porównanie. Zmiany są gotowe do przeglądu.")
            try:
                window.after(0, finish)
            except Exception:
                pass
        threading.Thread(target=worker, name="WM-Excel-Dwa-Zrodla", daemon=True).start()

    ttk.Button(change_actions, text="Sprawdź oba pliki", command=scan_now).pack(side="left")
    ttk.Button(
        change_actions, text="Zatwierdź wybrane zlecenia…",
        command=lambda: runtime._open_excel_sync(owner),
    ).pack(side="left", padx=(10, 0))
    ttk.Label(change_actions, text="Istniejący silnik synchronizacji WM").pack(side="left", padx=(12, 0))

    def choose_conflict(decision: str) -> None:
        chosen = conflict_tree.selection()
        record = conflict_records.get(chosen[0]) if chosen else None
        if not record:
            messagebox.showinfo("Konflikty", "Najpierw zaznacz konflikt.", parent=window)
            return
        if not record.get("signature"):
            messagebox.showwarning(
                "Konflikty",
                "Zduplikowane partie wymagają osobnych stabilnych identyfikatorów.",
                parent=window,
            )
            return
        values = {}
        if decision == "Własne":
            qty = simpledialog.askfloat(
                "Własne wartości", "Ilość sztuk:", minvalue=0.001, parent=window
            )
            if qty is None:
                return
            date = simpledialog.askstring(
                "Własne wartości", "Termin (RRRR-MM-DD):", parent=window
            )
            if date is None:
                return
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Termin", "Podaj termin RRRR-MM-DD.", parent=window)
                return
            process = simpledialog.askstring(
                "Własne wartości", "Proces:", parent=window
            )
            if process is None:
                return
            values = {"ilosc": qty, "data_wysylki": date, "proces": process}
        resolve_dual_conflict(
            record["key"], record["signature"], decision, values,
            user=str(getattr(owner, "login", "") or "operator WM"),
        )
        feedback.set("Zapisano decyzję. Ponawiam analizę obu plików.")
        scan_now()

    decision_bar = ttk.Frame(conflicts_tab)
    decision_bar.grid(row=2, column=0, sticky="ew")
    for label, action in (
        ("Przyjmij Excel A", "A"), ("Przyjmij Excel B", "B"),
        ("Własne wartości…", "Własne"),
    ):
        ttk.Button(
            decision_bar, text=label,
            command=lambda decision=action: choose_conflict(decision)
        ).pack(side="left", padx=(0, 8))
    ttk.Button(
        decision_bar, text="Odłóż", command=lambda: feedback.set(
            "Konflikt pozostaje do wyjaśnienia — niczego nie zapisano."
        )
    ).pack(side="left")

    ttk.Label(
        history_tab,
        text="W trybie A+B drukowanie następuje po utworzeniu zlecenia WM, nie po samym odczycie Excela.",
    ).grid(row=1, column=0, sticky="w", pady=(9, 0))
    ttk.Label(window, textvariable=feedback).pack(fill="x", padx=13, pady=(0, 10))

    window._wm_dual_refresh = render
    render()
