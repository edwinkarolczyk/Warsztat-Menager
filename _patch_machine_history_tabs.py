from __future__ import annotations

import subprocess
from pathlib import Path

PATH = Path("gui_maszyny.py")
EXPECTED_SHA = "c4f86a85d1e13a6475c6b9225c16fd17578d0749"


def blob_sha(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, got {count}")
    return text.replace(old, new)


def replace_region(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{label}: start marker not found")
    j = text.find(end, i + len(start))
    if j < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:i] + replacement + text[j:]


actual = blob_sha(PATH)
if actual != EXPECTED_SHA:
    raise RuntimeError(f"gui_maszyny.py changed: expected {EXPECTED_SHA}, got {actual}")

text = PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Version header
# ---------------------------------------------------------------------------
text = replace_once(
    text,
    "# version: 1.6\n",
    "# version: 1.7\n"
    "# Zmiany 1.7:\n"
    "# - Daty w module Maszyny są wyświetlane jako DD Miesiąc RRr, z godziną tam gdzie potrzebna.\n"
    "# - Użytkowanie maszyny ma osobne zakładki Podgląd i Historia.\n"
    "# - Podgląd rozdziela aktywne przeglądy, ostatnią historię statusów i ostatnią historię przeglądów.\n"
    "# - Wykonane przeglądy znikają z listy aktywnej, pozostając w historii; aktywne wpisy mają czytelne kolory.\n"
    "# - Listy i tabele Maszyn używają pogrubionej czcionki przy zachowaniu rozmiaru 11.\n",
    "version header",
)

# ---------------------------------------------------------------------------
# Polish month date format
# ---------------------------------------------------------------------------
old_history_format = '''_MACHINE_WEEKDAY_LABELS_PL = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")


def _format_machine_history_dt(value: object) -> str:
    parsed = _parse_machine_dt(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw.replace("T", " ")[:16] if raw else "—"
    weekday = _MACHINE_WEEKDAY_LABELS_PL[parsed.weekday()]
    return f"{weekday} {parsed.strftime('%d-%m-%y %H:%M')}"
'''
new_history_format = '''_MACHINE_WEEKDAY_LABELS_PL = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nie")
_MACHINE_MONTH_LABELS_PL = (
    "Styczeń",
    "Luty",
    "Marzec",
    "Kwiecień",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpień",
    "Wrzesień",
    "Październik",
    "Listopad",
    "Grudzień",
)


def _format_machine_history_dt(value: object) -> str:
    parsed = _parse_machine_dt(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw.replace("T", " ")[:16] if raw else "—"
    month = _MACHINE_MONTH_LABELS_PL[parsed.month - 1]
    return f"{parsed.day:02d} {month} {parsed.strftime('%y')}r {parsed.strftime('%H:%M')}"
'''
text = replace_once(text, old_history_format, new_history_format, "history date format")

old_review_format = '''def _format_machine_review_date(value: object) -> str:
    parsed = _review_date(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw[:10] if raw else "—"
    weekday = _MACHINE_WEEKDAY_LABELS_PL[parsed.weekday()]
    return f"{weekday} {parsed.strftime('%d-%m-%y')}"
'''
new_review_format = '''def _format_machine_review_date(value: object) -> str:
    parsed = _review_date(value)
    if parsed is None:
        raw = str(value or "").strip()
        return raw[:10] if raw else "—"
    month = _MACHINE_MONTH_LABELS_PL[parsed.month - 1]
    return f"{parsed.day:02d} {month} {parsed.strftime('%y')}r"
'''
text = replace_once(text, old_review_format, new_review_format, "review date format")

parse_start = "def _parse_schedule_date(value: object) -> Optional[dt.date]:\n"
parse_end = "def _normalize_schedule_entry(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:\n"
new_parse_region = '''def _parse_schedule_date(value: object) -> Optional[dt.date]:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, (int, float)):
        ordinal = int(value)
        if ordinal > 59:  # Excel 1900 date system offset
            try:
                return dt.date.fromordinal(ordinal + 693594)
            except ValueError:
                pass
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        # Format użytkownika w Maszynach: "23 Sierpień 26r".
        clean = raw.replace(",", " ").replace(".", " ")
        parts = [part for part in clean.split() if part]
        if len(parts) >= 3:
            month_lookup = {
                name.casefold(): idx
                for idx, name in enumerate(_MACHINE_MONTH_LABELS_PL, start=1)
            }
            month_lookup.update(
                {
                    "styczen": 1,
                    "luty": 2,
                    "marzec": 3,
                    "kwiecien": 4,
                    "maj": 5,
                    "czerwiec": 6,
                    "lipiec": 7,
                    "sierpien": 8,
                    "wrzesien": 9,
                    "pazdziernik": 10,
                    "listopad": 11,
                    "grudzien": 12,
                }
            )
            try:
                day = int(parts[0])
                month = month_lookup.get(parts[1].casefold())
                year_token = parts[2].casefold().rstrip("r")
                year = int(year_token)
                if year < 100:
                    year += 2000
                if month:
                    return dt.date(year, month, day)
            except (TypeError, ValueError):
                pass

        for fmt in (
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%Y.%m.%d",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return dt.datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _format_next_label(entry: Dict[str, Any], date_obj: dt.date) -> str:
    label = _format_machine_review_date(date_obj)
    typ = str(entry.get("type") or entry.get("typ") or "").strip()
    if typ:
        label = f"{label} ({typ})"
    return label


'''
text = replace_region(text, parse_start, parse_end, new_parse_region, "schedule date parser")

# ---------------------------------------------------------------------------
# Bold machine tables without changing the established 11 px size.
# ---------------------------------------------------------------------------
text = replace_once(
    text,
    'style.configure("Maszyny.Treeview", font=("Segoe UI", 11), rowheight=30)',
    'style.configure("Maszyny.Treeview", font=("Segoe UI", 11, "bold"), rowheight=30)',
    "machine tree bold",
)

text = replace_once(
    text,
    'upcoming_tree = ttk.Treeview(upcoming_section, columns=columns_details, show="headings", height=6)',
    'upcoming_tree = ttk.Treeview(upcoming_section, columns=columns_details, show="headings", height=6, style="Maszyny.Treeview")',
    "schedule upcoming style",
)
text = replace_once(
    text,
    'history_tree = ttk.Treeview(history_section, columns=columns_details, show="headings", height=5)',
    'history_tree = ttk.Treeview(history_section, columns=columns_details, show="headings", height=5, style="Maszyny.Treeview")',
    "schedule history style",
)

# Dates in the legacy schedule detail pane are display-only too.
text = replace_count(
    text,
    '            date_text = entry.get("date") or "—"\n',
    '            date_text = _format_machine_review_date(entry.get("date"))\n',
    2,
    "schedule detail dates",
)

# ---------------------------------------------------------------------------
# Usage window: notebook with Overview + full History.
# ---------------------------------------------------------------------------
summary_start = '        summary = machine.get("__schedule_summary") or {}\n'
history_marker = '        history_box = ttk.LabelFrame(outer, text="Historia statusów")\n'
new_summary = '''        notebook = ttk.Notebook(outer)
        notebook.grid(
            row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 8)
        )
        overview_tab = ttk.Frame(notebook, padding=(6, 8))
        full_history_tab = ttk.Frame(notebook, padding=(6, 8))
        notebook.add(overview_tab, text="Podgląd")
        notebook.add(full_history_tab, text="Historia")

        review_box = ttk.LabelFrame(overview_tab, text="Najbliższy przegląd")
        review_box.pack(fill="x", pady=(0, 8))
        next_review_var = tk.StringVar(value="—")
        review_status_var = tk.StringVar(value="Brak danych przeglądu")
        ttk.Label(review_box, textvariable=next_review_var).pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        ttk.Label(review_box, textvariable=review_status_var).pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        active_reviews_slot = ttk.Frame(overview_tab)
        active_reviews_slot.pack(fill="both", expand=True, pady=(0, 8))

        def _refresh_next_review_summary() -> None:
            summary = _combined_machine_schedule_summary(machine)
            machine["__schedule_summary"] = summary
            next_review = str(summary.get("next_label") or "—")
            review_status = str(
                summary.get("status_text") or "Brak danych przeglądu"
            )
            next_review_var.set(f"Termin: {next_review}")
            review_status_var.set(review_status)

        _refresh_next_review_summary()

'''
text = replace_region(text, summary_start, history_marker, new_summary, "usage notebook summary")

old_history_box = '''        history_box = ttk.LabelFrame(outer, text="Historia statusów")
        history_box.grid(
            row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8)
        )
        outer.rowconfigure(3, weight=1)
'''
new_history_box = '''        history_box = ttk.LabelFrame(overview_tab, text="Ostatnia historia statusów")
        history_box.pack(fill="both", expand=True, pady=(0, 8))
'''
text = replace_once(text, old_history_box, new_history_box, "short status history box")

old_hist_tree = '''        hist_tree = ttk.Treeview(
            history_box, columns=hist_cols, show="headings", height=9
        )
'''
new_hist_tree = '''        hist_tree = ttk.Treeview(
            history_box,
            columns=hist_cols,
            show="headings",
            height=5,
            style="Maszyny.Treeview",
        )
'''
text = replace_once(text, old_hist_tree, new_hist_tree, "short status history tree")

text = replace_count(text, '"start": ("Start", 155, "center"),', '"start": ("Start", 210, "center"),', 1, "status start width")
text = replace_count(text, '"stop": ("Stop", 155, "center"),', '"stop": ("Stop", 210, "center"),', 1, "status stop width")

old_hist_pack = '''        hist_tree.pack(fill="both", expand=True, padx=6, pady=6)

        history_items: Dict[str, Dict[str, Any]] = {}
'''
new_hist_pack = '''        hist_tree.pack(fill="both", expand=True, padx=6, pady=6)

        full_status_box = ttk.LabelFrame(
            full_history_tab, text="Pełna historia statusów"
        )
        full_status_box.pack(fill="both", expand=True, pady=(0, 8))
        full_status_tree = ttk.Treeview(
            full_status_box,
            columns=hist_cols,
            show="headings",
            height=10,
            style="Maszyny.Treeview",
        )
        for col, (label, width, anchor) in hist_setup.items():
            full_status_tree.heading(col, text=label)
            full_status_tree.column(col, width=width, anchor=anchor)
        full_status_tree.pack(fill="both", expand=True, padx=6, pady=6)

        history_items: Dict[str, Dict[str, Any]] = {}
        full_history_items: Dict[str, Dict[str, Any]] = {}
'''
text = replace_once(text, old_hist_pack, new_hist_pack, "full status history tree")

refresh_history_start = '        def _refresh_history_tree() -> None:\n'
refresh_history_end = '        def _selected_history_item() -> Optional[Dict[str, Any]]:\n'
new_refresh_history = '''        def _refresh_history_tree() -> None:
            history_items.clear()
            full_history_items.clear()
            for tree_view in (hist_tree, full_status_tree):
                for iid in tree_view.get_children():
                    tree_view.delete(iid)

            entries = list(reversed(_history_entries_for_usage(machine)))
            targets = (
                (hist_tree, history_items, entries[:5]),
                (full_status_tree, full_history_items, entries),
            )
            for tree_view, mapping, rows_to_show in targets:
                if rows_to_show:
                    for item in rows_to_show:
                        iid = tree_view.insert(
                            "", "end", values=_history_entry_values(item)
                        )
                        mapping[iid] = item
                else:
                    tree_view.insert(
                        "",
                        "end",
                        values=(
                            "—",
                            "—",
                            "—",
                            "—",
                            "Brak historii. Pierwszy wpis powstanie przy zmianie statusu.",
                        ),
                    )

        _refresh_history_tree()

'''
text = replace_region(text, refresh_history_start, refresh_history_end, new_refresh_history, "status history refresh")

old_selected_history = '''        def _selected_history_item() -> Optional[Dict[str, Any]]:
            selected = hist_tree.selection()
            if not selected:
                return None
            return history_items.get(selected[0])
'''
new_selected_history = '''        def _selected_history_item() -> Optional[Dict[str, Any]]:
            selected = hist_tree.selection()
            if selected:
                return history_items.get(selected[0])
            selected = full_status_tree.selection()
            if selected:
                return full_history_items.get(selected[0])
            return None
'''
text = replace_once(text, old_selected_history, new_selected_history, "selected status history")

text = replace_once(
    text,
    "                f\"{str(item.get('started_at') or '—').replace('T', ' ')[:16]}\"\n",
    "                f\"{_format_machine_history_dt(item.get('started_at'))}\"\n",
    "history photo date",
)

text = replace_once(
    text,
    '        hist_tree.bind("<Double-1>", lambda _event: _show_history_photos())\n',
    '        hist_tree.bind("<Double-1>", lambda _event: _show_history_photos())\n        full_status_tree.bind("<Double-1>", lambda _event: _show_history_photos())\n',
    "full status history double click",
)

# ---------------------------------------------------------------------------
# Active reviews + separate short/full review history.
# ---------------------------------------------------------------------------
old_reviews_box = '''        reviews_box = ttk.LabelFrame(outer, text="Przeglądy / serwis maszyny")
        reviews_box.grid(
            row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 8)
        )
'''
new_reviews_box = '''        reviews_box = ttk.LabelFrame(
            active_reviews_slot, text="Najbliższe przeglądy / serwis"
        )
        reviews_box.pack(fill="both", expand=True)
'''
text = replace_once(text, old_reviews_box, new_reviews_box, "active reviews box")

old_reviews_tree = '''        reviews_tree = ttk.Treeview(
            reviews_box,
            columns=reviews_cols,
            show="headings",
            height=6,
        )
'''
new_reviews_tree = '''        reviews_tree = ttk.Treeview(
            reviews_box,
            columns=reviews_cols,
            show="headings",
            height=5,
            style="Maszyny.Treeview",
        )
'''
text = replace_once(text, old_reviews_tree, new_reviews_tree, "active reviews tree")
text = replace_once(text, '"date": ("Data", 105, "center"),', '"date": ("Data", 155, "center"),', "review date width")

old_review_pack = '''        reviews_tree.pack(fill="both", expand=True, padx=6, pady=6)

        review_items: Dict[str, Dict[str, Any]] = {}
'''
new_review_pack = '''        reviews_tree.pack(fill="both", expand=True, padx=6, pady=6)
        reviews_tree.tag_configure(
            "overdue", background="#fee2e2", foreground="#7f1d1d"
        )
        reviews_tree.tag_configure(
            "pending", background="#fef3c7", foreground="#854d0e"
        )

        review_history_box = ttk.LabelFrame(
            overview_tab, text="Ostatnia historia przeglądów / serwisów"
        )
        review_history_box.pack(fill="both", expand=True, pady=(0, 8))
        review_history_cols = ("plan", "done", "type", "people", "details")
        review_history_setup = {
            "plan": ("Plan", 155, "center"),
            "done": ("Wykonano", 210, "center"),
            "type": ("Typ", 165, "w"),
            "people": ("Osoby", 170, "w"),
            "details": ("Szczegóły", 360, "w"),
        }
        review_history_tree = ttk.Treeview(
            review_history_box,
            columns=review_history_cols,
            show="headings",
            height=5,
            style="Maszyny.Treeview",
        )
        for col, (label, width, anchor) in review_history_setup.items():
            review_history_tree.heading(col, text=label)
            review_history_tree.column(col, width=width, anchor=anchor)
        review_history_tree.pack(fill="both", expand=True, padx=6, pady=6)

        full_review_history_box = ttk.LabelFrame(
            full_history_tab, text="Pełna historia przeglądów / serwisów"
        )
        full_review_history_box.pack(fill="both", expand=True)
        full_review_history_tree = ttk.Treeview(
            full_review_history_box,
            columns=review_history_cols,
            show="headings",
            height=10,
            style="Maszyny.Treeview",
        )
        for col, (label, width, anchor) in review_history_setup.items():
            full_review_history_tree.heading(col, text=label)
            full_review_history_tree.column(col, width=width, anchor=anchor)
        full_review_history_tree.pack(fill="both", expand=True, padx=6, pady=6)

        review_items: Dict[str, Dict[str, Any]] = {}
        review_history_items: Dict[str, Dict[str, Any]] = {}
        full_review_history_items: Dict[str, Dict[str, Any]] = {}
'''
text = replace_once(text, old_review_pack, new_review_pack, "review history trees")

refresh_reviews_start = '        def _refresh_reviews_tree() -> None:\n'
refresh_reviews_end = '        def _selected_review_entry() -> Optional[Dict[str, Any]]:\n'
new_refresh_reviews = '''        def _next_cycle_date_after(entry: Dict[str, Any]) -> Optional[dt.date]:
            if str(entry.get("source") or "").strip().lower() != REVIEW_SOURCE_CYCLE:
                return None
            base = _review_date(
                entry.get("date")
                or entry.get("planned_date")
                or entry.get("completed_at")
            )
            months = _machine_review_months(machine)
            if base is None or not months:
                return None
            candidates: List[dt.date] = []
            for year in range(base.year, base.year + 3):
                for month in months:
                    candidate = _cycle_review_date(
                        year, month, _machine_review_day(machine)
                    )
                    if candidate > base:
                        candidates.append(candidate)
            return min(candidates) if candidates else None

        def _review_history_values(entry: Dict[str, Any]) -> tuple:
            source = str(entry.get("source") or REVIEW_SOURCE_MANUAL).strip().lower()
            planned = _review_date(
                entry.get("date")
                or entry.get("planned_date")
                or entry.get("completed_at")
            )
            planned_text = _format_machine_review_date(planned) if planned else "—"
            completed_text = (
                _format_machine_history_dt(entry.get("completed_at"))
                if entry.get("completed_at")
                else "—"
            )
            type_text = (
                "Przegląd cykliczny"
                if source == REVIEW_SOURCE_CYCLE
                else str(entry.get("type") or "Przegląd / serwis")
            )
            people = _people_text(entry.get("completed_by")) or "—"
            details = str(entry.get("result_note") or entry.get("description") or "").strip()
            dysp_id = _linked_dysp_id(entry)
            if dysp_id:
                details = (details + " | " if details else "") + f"Dyspozycja: {dysp_id}"
            next_date = _next_cycle_date_after(entry)
            if next_date is not None:
                details = (details + " | " if details else "") + (
                    f"Następny: {_format_machine_review_date(next_date)}"
                )
            return planned_text, completed_text, type_text, people, details or "—"

        def _refresh_review_history_trees(
            entries: List[Dict[str, Any]],
        ) -> None:
            review_history_items.clear()
            full_review_history_items.clear()
            for tree_view in (review_history_tree, full_review_history_tree):
                for iid in tree_view.get_children():
                    tree_view.delete(iid)

            done_entries = [
                item
                for item in entries
                if _review_status_key(item.get("status")) == REVIEW_STATUS_DONE
            ]
            done_entries.sort(
                key=lambda item: str(
                    item.get("completed_at")
                    or item.get("planned_date")
                    or item.get("date")
                    or ""
                ),
                reverse=True,
            )
            for tree_view, mapping, rows_to_show in (
                (review_history_tree, review_history_items, done_entries[:5]),
                (full_review_history_tree, full_review_history_items, done_entries),
            ):
                for item in rows_to_show:
                    iid = tree_view.insert(
                        "", "end", values=_review_history_values(item)
                    )
                    mapping[iid] = item

        def _refresh_reviews_tree() -> None:
            review_items.clear()
            for iid in reviews_tree.get_children():
                reviews_tree.delete(iid)
            entries = _combined_machine_review_entries(
                machine, today=dt.date.today(), years_ahead=1
            )
            month_names = dict(MONTH_LABELS_PL)
            for entry in entries:
                status_key = _review_status_key(entry.get("status"))
                if status_key in {REVIEW_STATUS_DONE, REVIEW_STATUS_CANCELLED}:
                    continue

                source = str(entry.get("source") or REVIEW_SOURCE_MANUAL).strip().lower()
                is_cycle = source == REVIEW_SOURCE_CYCLE
                date_value = _review_date(
                    entry.get("date")
                    or entry.get("planned_date")
                    or entry.get("completed_at")
                )
                planned_text = (
                    _format_machine_review_date(date_value)
                    if date_value is not None
                    else str(entry.get("planned_date") or "—")
                )
                type_text = (
                    "Przegląd cykliczny"
                    if is_cycle
                    else str(entry.get("type") or "")
                )
                cycle_text = ""
                if is_cycle and date_value is not None:
                    cycle_text = (
                        f"Cykliczny: {month_names.get(date_value.month, str(date_value.month))} "
                        f"{date_value.year}"
                    )

                status_label = _review_status_label(entry.get("status"))
                if status_label == "W trakcie":
                    people = str(entry.get("started_by") or "") or _people_text(
                        entry.get("suggested_workers") or entry.get("suggested_people")
                    )
                    started_at = (
                        _format_machine_history_dt(entry.get("started_at"))
                        if entry.get("started_at")
                        else ""
                    )
                    details = str(entry.get("description") or "")
                    if started_at:
                        details = f"Rozpoczęto: {started_at}" + (
                            f" | {details}" if details else ""
                        )
                else:
                    people = _people_text(
                        entry.get("suggested_workers") or entry.get("suggested_people")
                    )
                    details = str(entry.get("description") or "")

                if cycle_text and cycle_text.lower() not in details.lower():
                    details = cycle_text + (f" | {details}" if details else "")
                dysp_id = _linked_dysp_id(entry)
                if dysp_id and dysp_id.lower() not in details.lower():
                    details = (details + " | " if details else "") + f"Dyspozycja: {dysp_id}"

                values = (
                    planned_text,
                    type_text,
                    status_label,
                    people or "—",
                    details or "—",
                )
                overdue = bool(date_value is not None and date_value < dt.date.today())
                tag = "overdue" if overdue else "pending"
                iid = reviews_tree.insert("", "end", values=values, tags=(tag,))
                review_items[iid] = entry

            _refresh_review_history_trees(entries)
            _refresh_next_review_summary()

'''
text = replace_region(text, refresh_reviews_start, refresh_reviews_end, new_refresh_reviews, "active and historical reviews refresh")

old_selected_review = '''        def _selected_review_entry() -> Optional[Dict[str, Any]]:
            sel = reviews_tree.selection()
            if not sel:
                return None
            return review_items.get(sel[0])
'''
new_selected_review = '''        def _selected_review_entry(
            source_tree: Optional[ttk.Treeview] = None,
        ) -> Optional[Dict[str, Any]]:
            trees = (
                (reviews_tree, review_items),
                (review_history_tree, review_history_items),
                (full_review_history_tree, full_review_history_items),
            )
            if source_tree is not None:
                trees = tuple(
                    pair for pair in trees if pair[0] is source_tree
                ) or trees
            for tree_view, mapping in trees:
                sel = tree_view.selection()
                if sel:
                    return mapping.get(sel[0])
            return None
'''
text = replace_once(text, old_selected_review, new_selected_review, "selected review across tabs")

text = replace_once(
    text,
    '''        def _show_selected_review_details(_event=None) -> None:
            entry = _selected_review_entry()
''',
    '''        def _show_selected_review_details(_event=None) -> None:
            source_tree = getattr(_event, "widget", None) if _event is not None else None
            entry = _selected_review_entry(
                source_tree if isinstance(source_tree, ttk.Treeview) else None
            )
''',
    "review details source tree",
)

text = replace_once(
    text,
    '        reviews_tree.bind("<Double-1>", _show_selected_review_details, add=True)\n',
    '        reviews_tree.bind("<Double-1>", _show_selected_review_details, add=True)\n        review_history_tree.bind("<Double-1>", _show_selected_review_details, add=True)\n        full_review_history_tree.bind("<Double-1>", _show_selected_review_details, add=True)\n',
    "review history double clicks",
)

# Manual review date editor uses the same visible format, but data remains ISO internally.
text = replace_once(
    text,
    '            var_date = tk.StringVar(value=dt.date.today().isoformat())\n',
    '            var_date = tk.StringVar(value=_format_machine_review_date(dt.date.today()))\n',
    "manual review visible date",
)
text = replace_once(
    text,
    '                        "Podaj poprawną datę, np. 2026-06-01.",\n',
    '                        "Podaj poprawną datę, np. 23 Sierpień 26r.",\n',
    "manual review date hint",
)

# Generated status notes should not leak ISO dates back into visible history.
text = replace_once(
    text,
    '''                f"Rozpoczęto {entry.get('type') or 'przegląd / serwis'}"
                f" | plan: {entry.get('planned_date') or '—'}"
''',
    '''                f"Rozpoczęto {entry.get('type') or 'przegląd / serwis'}"
                f" | plan: {_format_machine_review_date(entry.get('planned_date'))}"
''',
    "review start note date",
)
text = replace_once(
    text,
    '''                    f"Wykonano {target_entry.get('type') or 'przegląd / serwis'}"
                    f" | plan: {target_entry.get('planned_date') or '—'}"
''',
    '''                    f"Wykonano {target_entry.get('type') or 'przegląd / serwis'}"
                    f" | plan: {_format_machine_review_date(target_entry.get('planned_date'))}"
''',
    "review completion note date",
)

# Bottom buttons remain outside the notebook.
text = replace_once(
    text,
    '        buttons.grid(row=5, column=0, columnspan=2, sticky="e")\n',
    '        buttons.grid(row=3, column=0, columnspan=2, sticky="e")\n',
    "usage buttons row",
)

PATH.write_text(text, encoding="utf-8")
print("Patched gui_maszyny.py")
