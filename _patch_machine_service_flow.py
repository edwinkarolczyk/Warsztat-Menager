from __future__ import annotations

from pathlib import Path

EXPECTED_BLOBS = {
    "gui_maszyny.py": "c0d4266c993ef8b5cdc0f9807b5145aa4407afe2",
    "maszyny_dyspozycje.py": "a670a70a034b3dbce90965c57c5f0b3fd3a7ff43",
    "gui_zlecenia.py": "6e751f418d8ed1a34d15bc670e70b239c2ffa01e",
    "gui_dyspozycje_creator.py": "3348b6d3d4832a24f5ce09f510aacd2a7ad1dbb7",
    "utils_maszyny.py": "3396d23dd36847883e92bf217577f35adb448996",
}


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_gui_maszyny() -> None:
    path = Path("gui_maszyny.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "# version: 1.4\n# Zmiany 1.4:\n",
        "# version: 1.5\n"
        "# Zmiany 1.5:\n"
        "# - Cykliczny przegląd ma dokładny dzień miesiąca (domyślnie 1) i nadal powtarza się co roku.\n"
        "# - Serwis cykliczny i jego automatyczna Dyspozycja synchronizują rozpoczęcie oraz wykonanie.\n"
        "# - Najbliższy przegląd i zaległość są czytelniejsze na głównej liście; dodano proste ostrzeżenie o terminach.\n"
        "# - Historia serwisowa pokazuje powiązaną Dyspozycję i pełniejsze szczegóły wpisu.\n"
        "# - Usunięto stare podpięcie wm.dyspo_wizard; przycisk Maszyn otwiera aktywny kreator Dyspozycji.\n"
        "# - Harmonogram pomocniczy używa bieżącego roku zamiast stałego 2025.\n"
        "# - Aktywne okno Użytkowanie maszyny używa formatu Start/Stop: Dzień DD-MM-RR HH:MM.\n"
        "# Zmiany 1.4:\n",
        "gui header",
    )

    text = replace_once(
        text,
        "import datetime as dt\n",
        "import calendar\nimport datetime as dt\n",
        "gui calendar import",
    )

    old_dyspo_block = '''try:  # pragma: no cover - opcjonalny moduł nowego kreatora\n    from wm.dyspo_wizard import open_dyspo_wizard\nexcept Exception:  # pragma: no cover - brak nowego modułu w starszych instalacjach\n    open_dyspo_wizard = None  # type: ignore\n\ntry:  # pragma: no cover - skróty dostępne tylko w nowej wersji\n    from wm.gui.shortcuts import bind_ctrl_d\nexcept Exception:  # pragma: no cover - zachowaj kompatybilność\n    def bind_ctrl_d(*_args, **_kwargs):  # type: ignore\n        return None\n\n\ndef _maybe_open_dyspo(root, context):\n    if open_dyspo_wizard is None:\n        return\n    target = root\n    if hasattr(root, "winfo_toplevel"):\n        try:\n            target = root.winfo_toplevel()\n        except Exception:\n            target = root\n    if getattr(target, "tk", None) is None:\n        local_tk = globals().get("tk")\n        local_ttk = globals().get("ttk")\n        dialog = None\n        if hasattr(local_tk, "Toplevel"):\n            try:\n                dialog = local_tk.Toplevel(target)\n            except Exception:\n                dialog = None\n        proceed = None\n        if hasattr(local_ttk, "Button"):\n            try:\n                proceed = lambda: None\n                local_ttk.Button(\n                    dialog or target, text="Dalej", command=proceed\n                )\n            except Exception:\n                proceed = None\n        if dialog is not None and hasattr(dialog, "bind") and proceed is not None:\n            try:\n                dialog.bind("<Return>", proceed)\n            except Exception:\n                pass\n        return\n    open_dyspo_wizard(target, context=context)\n'''
    new_dyspo_block = '''def _maybe_open_dyspo(root, context):\n    """Otwórz aktywny kreator Dyspozycji z kontekstem Maszyn."""\n\n    try:\n        from gui_dyspozycje_creator import open_dyspozycje_creator\n    except Exception as exc:\n        messagebox.showerror(\n            "Maszyny",\n            f"Nie udało się otworzyć kreatora Dyspozycji:\\n{exc}",\n            parent=root if getattr(root, "tk", None) is not None else None,\n        )\n        return\n\n    target = root\n    if hasattr(root, "winfo_toplevel"):\n        try:\n            target = root.winfo_toplevel()\n        except Exception:\n            target = root\n\n    ctx = {\n        "typ_dyspozycji": "maszyna",\n        "modul_zrodlowy": "maszyny",\n    }\n    if isinstance(context, dict):\n        ctx.update(context)\n    try:\n        open_dyspozycje_creator(\n            target,\n            autor=_active_login_for_machine(target),\n            context=ctx,\n        )\n    except Exception as exc:\n        messagebox.showerror(\n            "Maszyny",\n            f"Nie udało się otworzyć kreatora Dyspozycji:\\n{exc}",\n            parent=target if getattr(target, "tk", None) is not None else None,\n        )\n'''
    text = replace_once(text, old_dyspo_block, new_dyspo_block, "active dysp creator")

    text = replace_once(
        text,
        "SCHEDULE_YEAR = 2025\n",
        "SCHEDULE_YEAR = dt.date.today().year\n",
        "current schedule year",
    )

    text = replace_once(
        text,
        '''def _review_date(value: object) -> Optional[dt.date]:\n    return _parse_schedule_date(value)\n\n\ndef _machine_review_months(machine: Dict[str, Any]) -> List[int]:\n''',
        '''def _review_date(value: object) -> Optional[dt.date]:\n    return _parse_schedule_date(value)\n\n\ndef _format_machine_review_date(value: object) -> str:\n    parsed = _review_date(value)\n    if parsed is None:\n        raw = str(value or "").strip()\n        return raw[:10] if raw else "—"\n    weekday = _MACHINE_WEEKDAY_LABELS_PL[parsed.weekday()]\n    return f"{weekday} {parsed.strftime('%d-%m-%y')}"\n\n\ndef _machine_review_months(machine: Dict[str, Any]) -> List[int]:\n''',
        "review date formatter",
    )

    text = replace_once(
        text,
        '''def _machine_review_months(machine: Dict[str, Any]) -> List[int]:\n    value = (\n        machine.get("review_months")\n        or machine.get("inspection_months")\n        or machine.get("miesiace_przegladu")\n        or machine.get("miesiące_przeglądu")\n        or machine.get("months")\n        or []\n    )\n    return _normalize_review_months(value)\n\n\ndef _review_month_done(\n''',
        '''def _machine_review_months(machine: Dict[str, Any]) -> List[int]:\n    value = (\n        machine.get("review_months")\n        or machine.get("inspection_months")\n        or machine.get("miesiace_przegladu")\n        or machine.get("miesiące_przeglądu")\n        or machine.get("months")\n        or []\n    )\n    return _normalize_review_months(value)\n\n\ndef _machine_review_day(machine: Dict[str, Any]) -> int:\n    try:\n        day = int(machine.get("review_day") or machine.get("inspection_day") or 1)\n    except (TypeError, ValueError):\n        day = 1\n    return max(1, min(31, day))\n\n\ndef _cycle_review_date(year: int, month: int, day: int) -> dt.date:\n    last_day = calendar.monthrange(int(year), int(month))[1]\n    return dt.date(int(year), int(month), min(max(1, int(day)), last_day))\n\n\ndef _review_month_done(\n''',
        "review day helpers",
    )

    text = replace_once(
        text,
        "            planned_date = dt.date(year, month, 1)\n",
        "            planned_date = _cycle_review_date(\n                year, month, _machine_review_day(machine)\n            )\n",
        "cycle planned day",
    )

    old_summary = '''    days = (date_value - today).days\n    if days < 0:\n        status = "overdue"\n        label = "Po terminie"\n    elif days <= SCHEDULE_SOON_THRESHOLD_DAYS:\n        status = "soon"\n        label = "Wkrótce"\n    else:\n        status = "ok"\n        label = "Planowane"\n\n    type_label = str(entry.get("type") or "Przegląd okresowy")\n    source_label = REVIEW_SOURCE_LABELS.get(\n        str(entry.get("source") or ""),\n        str(entry.get("source") or ""),\n    )\n\n    parts = [label, type_label]\n    if source_label:\n        parts.append(source_label)\n\n    status_label = " • ".join(parts)\n    return {\n        "upcoming": upcoming,\n        "history": history,\n        "next_entry": entry,\n        "next_date": date_value,\n        "status": status,\n        "key": status,\n        "status_key": status,\n        "next_label": date_value.isoformat(),\n        "status_label": status_label,\n        "status_text": f"{status_label} – {date_value.isoformat()}",\n        "days": days,\n        "color": SCHEDULE_STATUS_COLORS.get(status, SCHEDULE_STATUS_COLORS["none"]),\n    }\n'''
    new_summary = '''    days = (date_value - today).days\n    if days < 0:\n        status = "overdue"\n        label = f"Po terminie • {abs(days)} dni"\n    elif days == 0:\n        status = "soon"\n        label = "Dzisiaj"\n    elif days == 1:\n        status = "soon"\n        label = "Jutro"\n    elif days <= SCHEDULE_SOON_THRESHOLD_DAYS:\n        status = "soon"\n        label = f"Za {days} dni"\n    else:\n        status = "ok"\n        label = f"Za {days} dni"\n\n    type_label = str(entry.get("type") or "Przegląd okresowy")\n    source_label = REVIEW_SOURCE_LABELS.get(\n        str(entry.get("source") or ""),\n        str(entry.get("source") or ""),\n    )\n    date_label = _format_machine_review_date(date_value)\n    details = [type_label]\n    if source_label:\n        details.append(source_label)\n    details.append(label)\n\n    return {\n        "upcoming": upcoming,\n        "history": history,\n        "next_entry": entry,\n        "next_date": date_value,\n        "status": status,\n        "key": status,\n        "status_key": status,\n        "next_label": date_label,\n        "status_label": label,\n        "status_text": f"{' • '.join(details)} – {date_label}",\n        "days": days,\n        "color": SCHEDULE_STATUS_COLORS.get(status, SCHEDULE_STATUS_COLORS["none"]),\n    }\n'''
    text = replace_once(text, old_summary, new_summary, "schedule summary labels")

    text = replace_once(
        text,
        '''from utils_maszyny import (\n    load_machines_rows_with_fallback,\n    ensure_machines_sample_if_empty,\n    load_machines,\n    upsert_machine,\n    delete_machine,\n    merge_rows_union_by_id,\n    resolve_schedule_path,\n)\n''',
        '''from utils_maszyny import (\n    load_machines_rows_with_fallback,\n    ensure_machines_sample_if_empty,\n    load_machines,\n    upsert_machine,\n    delete_machine,\n    merge_rows_union_by_id,\n    resolve_schedule_path,\n)\nfrom maszyny_dyspozycje import (\n    find_cycle_dyspozycja_for_review,\n    sync_review_to_dyspozycja,\n)\n''',
        "machine dysp imports",
    )

    old_review_workers = '''            ttk.Label(review_box, text="Wykonawcy / serwis:").grid(\n                row=1, column=0, sticky="e", padx=6, pady=6\n            )\n            review_workers = self._row.get("review_workers") or []\n'''
    new_review_workers = '''            ttk.Label(review_box, text="Dzień miesiąca:").grid(\n                row=1, column=0, sticky="e", padx=6, pady=6\n            )\n            review_day_frame = ttk.Frame(review_box)\n            review_day_frame.grid(row=1, column=1, sticky="w", padx=6, pady=6)\n            self.review_day_var = tk.StringVar(\n                master=self, value=str(_machine_review_day(self._row))\n            )\n            self.review_day_spin = ttk.Spinbox(\n                review_day_frame,\n                from_=1,\n                to=31,\n                width=5,\n                textvariable=self.review_day_var,\n                state="readonly",\n            )\n            self.review_day_spin.pack(side="left")\n            ttk.Label(\n                review_day_frame,\n                text="(dla krótszego miesiąca WM użyje ostatniego dnia)",\n            ).pack(side="left", padx=(8, 0))\n            self.review_day_var.trace_add("write", _mark_dirty)\n\n            ttk.Label(review_box, text="Wykonawcy / serwis:").grid(\n                row=2, column=0, sticky="e", padx=6, pady=6\n            )\n            review_workers = self._row.get("review_workers") or []\n'''
    text = replace_once(text, old_review_workers, new_review_workers, "review day UI")
    text = replace_once(
        text,
        'workers_frame.grid(row=1, column=1, sticky="ew", padx=6, pady=6)',
        'workers_frame.grid(row=2, column=1, sticky="ew", padx=6, pady=6)',
        "workers row",
    )
    text = replace_once(
        text,
        ').grid(row=2, column=1, sticky="w", padx=6, pady=(0, 6))',
        ').grid(row=3, column=1, sticky="w", padx=6, pady=(0, 6))',
        "workers hint row",
    )

    text = replace_once(
        text,
        '''                "review_months": [\n                    month\n                    for month, var in self.review_month_vars.items()\n                    if bool(var.get())\n                ],\n                "review_workers": [\n''',
        '''                "review_months": [\n                    month\n                    for month, var in self.review_month_vars.items()\n                    if bool(var.get())\n                ],\n                "review_day": max(1, min(31, int(self.review_day_var.get() or 1))),\n                "review_workers": [\n''',
        "save review day",
    )
    text = replace_once(
        text,
        '            for key in ("status_history", "status_current"):\n',
        '            for key in ("status_history", "status_current", "reviews"):\n',
        "preserve reviews",
    )

    text = replace_once(
        text,
        '            "start": ("Start", 125, "center"),\n            "stop": ("Stop", 125, "center"),\n',
        '            "start": ("Start", 155, "center"),\n            "stop": ("Stop", 155, "center"),\n',
        "history date widths",
    )
    text = replace_once(
        text,
        '''            start = str(item.get("started_at") or "—").replace("T", " ")[:16]\n            if item.get("__current"):\n                stop = "w toku"\n                who = str(item.get("changed_by") or "—")\n                note = str(item.get("note") or "")\n            else:\n                stop = str(item.get("ended_at") or "—").replace("T", " ")[:16]\n''',
        '''            start = _format_machine_history_dt(item.get("started_at"))\n            if item.get("__current"):\n                stop = "w toku"\n                who = str(item.get("changed_by") or "—")\n                note = str(item.get("note") or "")\n            else:\n                stop = _format_machine_history_dt(item.get("ended_at"))\n''',
        "active history formatter",
    )

    text = replace_once(
        text,
        '''        def _people_text(value: object) -> str:\n            if isinstance(value, list):\n                return ", ".join(\n                    str(item) for item in value if str(item).strip()\n                )\n            return str(value or "")\n\n        def _refresh_reviews_tree() -> None:\n''',
        '''        def _people_text(value: object) -> str:\n            if isinstance(value, list):\n                return ", ".join(\n                    str(item) for item in value if str(item).strip()\n                )\n            return str(value or "")\n\n        def _linked_dysp_id(entry: Dict[str, Any]) -> str:\n            direct = str(entry.get("dyspozycja_id") or "").strip()\n            if direct:\n                return direct\n            source = str(entry.get("source") or "").strip().lower()\n            if source != REVIEW_SOURCE_CYCLE:\n                return ""\n            try:\n                linked = find_cycle_dyspozycja_for_review(machine, entry)\n            except Exception:\n                linked = None\n            return str((linked or {}).get("id") or "").strip()\n\n        def _refresh_reviews_tree() -> None:\n''',
        "linked dysp helper",
    )

    text = replace_once(
        text,
        '''                planned_text = (\n                    date_value.isoformat()\n                    if date_value is not None\n                    else str(entry.get("planned_date") or "—")\n                )\n''',
        '''                planned_text = (\n                    _format_machine_review_date(date_value)\n                    if date_value is not None\n                    else str(entry.get("planned_date") or "—")\n                )\n''',
        "review planned display",
    )
    text = replace_once(
        text,
        '                    completed_at = str(entry.get("completed_at") or "").replace("T", " ")[:16]\n',
        '                    completed_at = _format_machine_history_dt(entry.get("completed_at")) if entry.get("completed_at") else ""\n',
        "review completed display",
    )
    text = replace_once(
        text,
        '                    started_at = str(entry.get("started_at") or "").replace("T", " ")[:16]\n',
        '                    started_at = _format_machine_history_dt(entry.get("started_at")) if entry.get("started_at") else ""\n',
        "review started display",
    )
    text = replace_once(
        text,
        '''                if cycle_text and cycle_text.lower() not in details.lower():\n                    details = cycle_text + (f" | {details}" if details else "")\n\n                values = (\n''',
        '''                if cycle_text and cycle_text.lower() not in details.lower():\n                    details = cycle_text + (f" | {details}" if details else "")\n                dysp_id = _linked_dysp_id(entry)\n                if dysp_id and dysp_id.lower() not in details.lower():\n                    details = (details + " | " if details else "") + f"Dyspozycja: {dysp_id}"\n\n                values = (\n''',
        "show linked dysp in review list",
    )

    text = replace_once(
        text,
        '''        def _selected_review_entry() -> Optional[Dict[str, Any]]:\n            sel = reviews_tree.selection()\n            if not sel:\n                return None\n            return review_items.get(sel[0])\n\n        def _review_for_action(display_entry: Dict[str, Any]) -> Dict[str, Any]:\n''',
        '''        def _selected_review_entry() -> Optional[Dict[str, Any]]:\n            sel = reviews_tree.selection()\n            if not sel:\n                return None\n            return review_items.get(sel[0])\n\n        def _show_selected_review_details(_event=None) -> None:\n            entry = _selected_review_entry()\n            if not entry:\n                return\n            source = str(entry.get("source") or REVIEW_SOURCE_MANUAL).strip().lower()\n            source_label = REVIEW_SOURCE_LABELS.get(source, source or "Ręczny")\n            planned = _review_date(\n                entry.get("date") or entry.get("planned_date") or entry.get("completed_at")\n            )\n            lines = [\n                f"Maszyna: {machine_id} — {machine.get('nazwa') or machine.get('name') or ''}",\n                f"Plan: {_format_machine_review_date(planned) if planned else '—'}",\n                f"Typ: {entry.get('type') or 'Przegląd okresowy'}",\n                f"Źródło: {source_label}",\n                f"Status: {_review_status_label(entry.get('status'))}",\n                f"Dyspozycja: {_linked_dysp_id(entry) or '—'}",\n                f"Rozpoczął: {entry.get('started_by') or '—'}",\n                f"Start: {_format_machine_history_dt(entry.get('started_at')) if entry.get('started_at') else '—'}",\n                f"Wykonali: {_people_text(entry.get('completed_by')) or '—'}",\n                f"Wykonano: {_format_machine_history_dt(entry.get('completed_at')) if entry.get('completed_at') else '—'}",\n                f"Zakres / opis: {entry.get('description') or '—'}",\n                f"Wynik / uwagi: {entry.get('result_note') or '—'}",\n                f"Zdjęcia: {len(entry.get('photos') or []) if isinstance(entry.get('photos'), list) else 0}",\n            ]\n            messagebox.showinfo(\n                "Karta serwisowa maszyny",\n                "\\n".join(lines),\n                parent=win,\n            )\n\n        def _review_for_action(display_entry: Dict[str, Any]) -> Dict[str, Any]:\n''',
        "service history details",
    )

    old_start_block = '''            entry["status"] = "in_progress"\n            entry["started_at"] = _machine_now_iso()\n            entry["started_by"] = _active_login_for_machine(root)\n\n            updated = dict(machine)\n            updated["reviews"] = list(_machine_reviews(machine))\n            _apply_machine_status_change(\n                updated,\n                "alert",\n                actor=_active_login_for_machine(root),\n                note=note,\n                photos=[],\n            )\n            machine.update(updated)\n            _persist_machine_after_review_change(updated)\n            _refresh_history_tree()\n            _refresh_reviews_tree()\n'''
    new_start_block = '''            actor = _active_login_for_machine(root)\n            entry["status"] = "in_progress"\n            entry["started_at"] = _machine_now_iso()\n            entry["started_by"] = actor\n            try:\n                linked = sync_review_to_dyspozycja(\n                    machine,\n                    entry,\n                    status="in_progress",\n                    actor=actor,\n                    note=note,\n                )\n            except Exception:\n                logger.exception(\n                    "[Maszyny][DYSP] Nie udało się rozpocząć powiązanej Dyspozycji."\n                )\n                linked = None\n            if linked:\n                entry["dyspozycja_id"] = str(linked.get("id") or "")\n                note += f" | Dyspozycja: {entry['dyspozycja_id']}"\n\n            updated = dict(machine)\n            updated["reviews"] = list(_machine_reviews(machine))\n            _apply_machine_status_change(\n                updated,\n                "alert",\n                actor=actor,\n                note=note,\n                photos=[],\n            )\n            machine.update(updated)\n            _persist_machine_after_review_change(updated)\n            _refresh_history_tree()\n            _refresh_reviews_tree()\n            try:\n                root.event_generate("<<DyspozycjeUpdated>>", when="tail")\n            except Exception:\n                pass\n'''
    text = replace_once(text, old_start_block, new_start_block, "start review sync")

    old_complete_block = '''                target_entry["status"] = "done"\n                target_entry["completed_at"] = _machine_now_iso()\n                target_entry["completed_by"] = completed_by\n                target_entry["result_note"] = txt_result.get("1.0", "end").strip()\n\n                updated = dict(machine)\n                updated["reviews"] = list(_machine_reviews(machine))\n                if _normalize_machine_status(updated.get("status")) == "alert":\n                    note = (\n                        f"Wykonano {target_entry.get('type') or 'przegląd / serwis'}"\n                        f" | plan: {target_entry.get('planned_date') or '—'}"\n                    )\n                    if target_entry.get("result_note"):\n                        note += f" | {target_entry.get('result_note')}"\n                    _apply_machine_status_change(\n                        updated,\n                        "ok",\n                        actor=", ".join(completed_by),\n                        note=note,\n                        photos=[],\n                    )\n                machine.update(updated)\n                _persist_machine_after_review_change(updated)\n                _refresh_history_tree()\n                _refresh_reviews_tree()\n                dialog.destroy()\n'''
    new_complete_block = '''                target_entry["status"] = "done"\n                target_entry["completed_at"] = _machine_now_iso()\n                target_entry["completed_by"] = completed_by\n                target_entry["result_note"] = txt_result.get("1.0", "end").strip()\n\n                actor = ", ".join(completed_by)\n                note = (\n                    f"Wykonano {target_entry.get('type') or 'przegląd / serwis'}"\n                    f" | plan: {target_entry.get('planned_date') or '—'}"\n                )\n                if target_entry.get("result_note"):\n                    note += f" | {target_entry.get('result_note')}"\n                try:\n                    linked = sync_review_to_dyspozycja(\n                        machine,\n                        target_entry,\n                        status="done",\n                        actor=actor,\n                        note=target_entry.get("result_note") or note,\n                    )\n                except Exception:\n                    logger.exception(\n                        "[Maszyny][DYSP] Nie udało się zamknąć powiązanej Dyspozycji."\n                    )\n                    linked = None\n                if linked:\n                    target_entry["dyspozycja_id"] = str(linked.get("id") or "")\n                    note += f" | Dyspozycja: {target_entry['dyspozycja_id']}"\n\n                updated = dict(machine)\n                updated["reviews"] = list(_machine_reviews(machine))\n                if _normalize_machine_status(updated.get("status")) == "alert":\n                    _apply_machine_status_change(\n                        updated,\n                        "ok",\n                        actor=actor,\n                        note=note,\n                        photos=[],\n                    )\n                machine.update(updated)\n                _persist_machine_after_review_change(updated)\n                _refresh_history_tree()\n                _refresh_reviews_tree()\n                try:\n                    root.event_generate("<<DyspozycjeUpdated>>", when="tail")\n                except Exception:\n                    pass\n                dialog.destroy()\n'''
    text = replace_once(text, old_complete_block, new_complete_block, "complete review sync")

    text = replace_once(
        text,
        '''        _refresh_reviews_tree()\n\n        reviews_actions = ttk.Frame(reviews_box)\n''',
        '''        _refresh_reviews_tree()\n        reviews_tree.bind("<Double-1>", _show_selected_review_details, add=True)\n\n        reviews_actions = ttk.Frame(reviews_box)\n''',
        "bind service details",
    )

    old_sched_info = '''    def _refresh_schedule_info() -> None:\n        year = schedule_meta.get("year", schedule_year)\n        if schedule_entries:\n            parts = [f"Harmonogram {year}: {len(schedule_entries)} wpisów"]\n        else:\n            parts = [f"Harmonogram {year}: brak danych"]\n        source = schedule_meta.get("source")\n        if source:\n            parts.append(f"Źródło: {source}")\n        imported = schedule_meta.get("imported_at")\n        if imported:\n            parts.append(f"Import: {imported}")\n        schedule_info.set(" • ".join(parts))\n\n    def _update_info() -> None:\n'''
    new_sched_info = '''    def _refresh_schedule_info() -> None:\n        overdue = sum(1 for row in rows_cache if _schedule_status_key(row) == "overdue")\n        soon = sum(1 for row in rows_cache if _schedule_status_key(row) == "soon")\n        planned = sum(1 for row in rows_cache if _schedule_status_key(row) == "ok")\n        schedule_info.set(\n            f"Przeglądy maszyn: {overdue} po terminie • "\n            f"{soon} w ciągu {SCHEDULE_SOON_THRESHOLD_DAYS} dni • "\n            f"{planned} później"\n        )\n\n    def _show_review_notice_once() -> None:\n        if initial_machine_id:\n            return\n        overdue = sum(1 for row in rows_cache if _schedule_status_key(row) == "overdue")\n        soon = sum(1 for row in rows_cache if _schedule_status_key(row) == "soon")\n        if overdue <= 0 and soon <= 0:\n            return\n        try:\n            target = root.winfo_toplevel()\n        except Exception:\n            target = root\n        notice_key = f"{dt.date.today().isoformat()}:{overdue}:{soon}"\n        if getattr(target, "_wm_machine_review_notice_key", "") == notice_key:\n            return\n        try:\n            setattr(target, "_wm_machine_review_notice_key", notice_key)\n        except Exception:\n            pass\n        lines = []\n        if overdue:\n            lines.append(f"Po terminie: {overdue}")\n        if soon:\n            lines.append(\n                f"W ciągu {SCHEDULE_SOON_THRESHOLD_DAYS} dni: {soon}"\n            )\n        show_now = messagebox.askyesno(\n            "Przeglądy maszyn",\n            "\\n".join(lines)\n            + "\\n\\nOdpowiednie Dyspozycje są tworzone automatycznie. "\n            + "Pokazać te maszyny teraz?",\n            parent=target if getattr(target, "tk", None) is not None else None,\n        )\n        if show_now:\n            filter_var.set("Po terminie" if overdue else "Wkrótce")\n            _apply_filter()\n\n    def _update_info() -> None:\n'''
    text = replace_once(text, old_sched_info, new_sched_info, "review notice")

    text = replace_once(
        text,
        '''    def _on_rows_changed() -> None:\n        _attach_schedule(rows_cache, schedule_entries)\n        for row in rows_cache:\n            if isinstance(row, dict):\n                row["__schedule_summary"] = _combined_machine_schedule_summary(row)\n        _recompute_visible_rows()\n        _refresh_tree()\n''',
        '''    def _on_rows_changed() -> None:\n        _attach_schedule(rows_cache, schedule_entries)\n        for row in rows_cache:\n            if isinstance(row, dict):\n                row["__schedule_summary"] = _combined_machine_schedule_summary(row)\n        _recompute_visible_rows()\n        _refresh_tree()\n        _refresh_schedule_info()\n''',
        "refresh review summary",
    )

    old_bottom_wizard = '''    _open_maszyny = _open_machines_panel  # alias nazwy\n    if open_dyspo_wizard is not None:\n        toolbar = ttk.Frame(module_frame)\n        toolbar.pack(fill="x", padx=6, pady=(6, 0))\n        target = root\n        if hasattr(root, "winfo_toplevel"):\n            try:\n                target = root.winfo_toplevel()\n            except Exception:\n                target = root\n        ttk.Button(\n            toolbar,\n            text="Nowa dyspozycja…",\n            command=lambda: _maybe_open_dyspo(\n                target, {"module": "Maszyny"}\n            ),\n        ).pack(side=tk.RIGHT)\n        bind_ctrl_d(target, context={"module": "Maszyny"})\n\n    panel_container = ttk.Frame(module_frame)\n'''
    new_bottom_wizard = '''    _open_maszyny = _open_machines_panel  # alias nazwy\n    toolbar = ttk.Frame(module_frame)\n    toolbar.pack(fill="x", padx=6, pady=(6, 0))\n    target = root\n    if hasattr(root, "winfo_toplevel"):\n        try:\n            target = root.winfo_toplevel()\n        except Exception:\n            target = root\n    ttk.Button(\n        toolbar,\n        text="Nowa dyspozycja…",\n        command=lambda: _maybe_open_dyspo(\n            target,\n            {\n                "typ_dyspozycji": "maszyna",\n                "modul_zrodlowy": "maszyny",\n            },\n        ),\n    ).pack(side=tk.RIGHT)\n\n    panel_container = ttk.Frame(module_frame)\n'''
    text = replace_once(text, old_bottom_wizard, new_bottom_wizard, "remove old wizard")

    text = replace_once(
        text,
        '''    _refresh_schedule_info()\n    _recompute_visible_rows()\n    _refresh_tree()\n    initial_machine = _find_machine(initial_machine_id)\n''',
        '''    _refresh_schedule_info()\n    _recompute_visible_rows()\n    _refresh_tree()\n    if not initial_machine_id:\n        try:\n            root.after_idle(_show_review_notice_once)\n        except Exception:\n            pass\n    initial_machine = _find_machine(initial_machine_id)\n''',
        "schedule notice call",
    )

    path.write_text(text, encoding="utf-8")


def patch_gui_zlecenia() -> None:
    path = Path("gui_zlecenia.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "# version: 1.7\n# Zmiany 1.7:\n",
        "# version: 1.8\n"
        "# Zmiany 1.8:\n"
        "# - Automatyczna Dyspozycja przeglądu maszyny synchronizuje start i zamknięcie z wpisem serwisowym maszyny.\n"
        "# Zmiany 1.7:\n",
        "dysp list header",
    )
    text = replace_once(
        text,
        "from maszyny_dyspozycje import ensure_due_machine_cycle_dyspozycje\n",
        "from maszyny_dyspozycje import (\n"
        "    ensure_due_machine_cycle_dyspozycje,\n"
        "    sync_machine_review_from_dyspozycja,\n"
        ")\n",
        "dysp list sync import",
    )
    text = replace_once(
        text,
        '''        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)\n        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Ta zmiana statusu nie jest dozwolona.",\n                parent=self,\n            )\n            return False\n        try:\n            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n''',
        '''        changed = set_dyspozycja_status(dysp_id, target, changed_by=who)\n        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Ta zmiana statusu nie jest dozwolona.",\n                parent=self,\n            )\n            return False\n        try:\n            sync_machine_review_from_dyspozycja(changed, actor=who)\n        except Exception as exc:\n            logger.exception(\n                "[DYSP][MASZYNY] Nie udało się zsynchronizować statusu przeglądu: %s",\n                exc,\n            )\n        try:\n            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n''',
        "dysp start sync",
    )
    text = replace_once(
        text,
        '''        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Nie udało się zamknąć Dyspozycji.",\n                parent=self,\n            )\n            return\n        try:\n            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n''',
        '''        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Nie udało się zamknąć Dyspozycji.",\n                parent=self,\n            )\n            return\n        try:\n            sync_machine_review_from_dyspozycja(\n                changed,\n                actor=who,\n                result_note=note or "",\n            )\n        except Exception as exc:\n            logger.exception(\n                "[DYSP][MASZYNY] Nie udało się zamknąć wpisu przeglądu maszyny: %s",\n                exc,\n            )\n        try:\n            self.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")\n''',
        "dysp close sync",
    )
    path.write_text(text, encoding="utf-8")


def patch_gui_creator() -> None:
    path = Path("gui_dyspozycje_creator.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "# version: 1.3\n# Zmiany 1.3:\n",
        "# version: 1.4\n"
        "# Zmiany 1.4:\n"
        "# - Zamknięcie automatycznej Dyspozycji przeglądu z kreatora aktualizuje również serwis maszyny.\n"
        "# Zmiany 1.3:\n",
        "creator header",
    )
    text = replace_once(
        text,
        '''from dyspozycje_store import (\n    add_dyspozycja,\n    close_dyspozycja,\n    load_dyspozycje,\n    make_dyspozycja,\n    update_dyspozycja,\n)\n''',
        '''from dyspozycje_store import (\n    add_dyspozycja,\n    close_dyspozycja,\n    load_dyspozycje,\n    make_dyspozycja,\n    update_dyspozycja,\n)\nfrom maszyny_dyspozycje import sync_machine_review_from_dyspozycja\n''',
        "creator sync import",
    )
    text = replace_once(
        text,
        '''        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Nie udało się zamknąć Dyspozycji.",\n                parent=win,\n            )\n            return\n        _event_updated()\n''',
        '''        if not changed:\n            messagebox.showerror(\n                "Dyspozycje",\n                "Nie udało się zamknąć Dyspozycji.",\n                parent=win,\n            )\n            return\n        try:\n            sync_machine_review_from_dyspozycja(\n                changed, actor=_actor_login()\n            )\n        except Exception:\n            pass\n        _event_updated()\n''',
        "creator close sync",
    )
    path.write_text(text, encoding="utf-8")


def patch_utils_maszyny() -> None:
    path = Path("utils_maszyny.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '# version: 1.0\n"""Narzędzia wspólne dla modułu maszyn."""\n',
        '# version: 1.1\n# Zmiany 1.1:\n# - Domyślny rok harmonogramu jest pobierany z bieżącej daty zamiast stałego 2025.\n"""Narzędzia wspólne dla modułu maszyn."""\n',
        "utils header",
    )
    text = replace_once(
        text,
        "import json\n",
        "import datetime as dt\nimport json\n",
        "utils datetime import",
    )
    text = replace_once(
        text,
        '''def resolve_schedule_path(year: int = 2025, cfg: Any | None = None) -> str:\n    """Return absolute path to the maintenance schedule JSON for *year*."""\n\n    filename = f"harmonogram_{year}.json"\n''',
        '''def resolve_schedule_path(year: int | None = None, cfg: Any | None = None) -> str:\n    """Return absolute path to the maintenance schedule JSON for *year*."""\n\n    if year is None:\n        year = dt.date.today().year\n    filename = f"harmonogram_{int(year)}.json"\n''',
        "utils schedule year",
    )
    path.write_text(text, encoding="utf-8")


NEW_MASZYNY_DYSPOZYCJE = r'''# version: 1.1
# Zmiany 1.1:
# - Cykl przeglądu uwzględnia dokładny dzień miesiąca zapisany w maszynie.
# - Dodano dwukierunkową synchronizację cyklicznego serwisu z automatyczną Dyspozycją.
# - Powiązanie zachowuje maszynę, rok i miesiąc, więc kolejne lata są osobnymi cyklami bez duplikatów.
# Zmiany 1.0:
# - Automatyczne Dyspozycje dla cyklicznych przeglądów maszyn do 7 dni przed terminem.
# - Klucz cyklu zawiera maszynę, rok i miesiąc, więc przeglądy powtarzają się co roku bez duplikatów.

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any, Iterable

from dyspozycje_store import (
    add_dyspozycja,
    load_dyspozycje,
    make_dyspozycja,
    set_dyspozycja_status,
)


AUTO_SOURCE = "machine_cycle_review"
AUTO_WINDOW_DAYS = 7

_MONTH_NAMES = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}


def _machine_id(machine: dict[str, Any]) -> str:
    return str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or machine.get("kod")
        or ""
    ).strip()


def _machine_name(machine: dict[str, Any]) -> str:
    return str(
        machine.get("nazwa")
        or machine.get("name")
        or machine.get("opis")
        or ""
    ).strip()


def _machine_type(machine: dict[str, Any]) -> str:
    return str(machine.get("typ") or machine.get("type") or "").strip()


def _review_months(machine: dict[str, Any]) -> list[int]:
    value = (
        machine.get("review_months")
        or machine.get("inspection_months")
        or machine.get("miesiace_przegladu")
        or machine.get("miesiące_przeglądu")
        or machine.get("months")
        or []
    )
    if not isinstance(value, list):
        value = [value]
    out: list[int] = []
    for item in value:
        try:
            month = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12 and month not in out:
            out.append(month)
    return sorted(out)


def _review_day(machine: dict[str, Any]) -> int:
    try:
        day = int(machine.get("review_day") or machine.get("inspection_day") or 1)
    except (TypeError, ValueError):
        day = 1
    return max(1, min(31, day))


def _planned_cycle_date(year: int, month: int, day: int) -> dt.date:
    last_day = calendar.monthrange(int(year), int(month))[1]
    return dt.date(int(year), int(month), min(max(1, int(day)), last_day))


def _default_review_type(machine: dict[str, Any]) -> str:
    return str(
        machine.get("default_review_type")
        or machine.get("domyslny_typ_przegladu")
        or machine.get("typ_przegladu")
        or "Przegląd okresowy"
    ).strip() or "Przegląd okresowy"


def _parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _review_date(review: dict[str, Any], machine: dict[str, Any] | None = None) -> dt.date | None:
    parsed = _parse_date(
        review.get("date")
        or review.get("data")
        or review.get("planned_date")
        or review.get("completed_at")
        or review.get("done_at")
    )
    if parsed is not None:
        return parsed
    try:
        year = int(review.get("cycle_year") or 0)
        month = int(review.get("cycle_month") or 0)
    except (TypeError, ValueError):
        return None
    if year <= 0 or not 1 <= month <= 12:
        return None
    return _planned_cycle_date(year, month, _review_day(machine or {}))


def _is_done_status(value: Any) -> bool:
    raw = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    return raw in {
        "done",
        "wykonany",
        "wykonane",
        "zrobione",
        "zamkniety",
        "zamknięty",
        "completed",
    }


def _cycle_done(
    machine: dict[str, Any],
    *,
    year: int,
    month: int,
    review_type: str,
) -> bool:
    reviews = machine.get("reviews")
    if not isinstance(reviews, list):
        return False
    wanted_type = str(review_type or "").strip().lower()
    for review in reviews:
        if not isinstance(review, dict) or not _is_done_status(review.get("status")):
            continue
        date_value = _review_date(review, machine)
        if date_value is None or date_value.year != year or date_value.month != month:
            continue
        current_type = str(review.get("type") or review.get("typ") or "").strip().lower()
        if not current_type or current_type == wanted_type:
            return True
    return False


def _cycle_key(machine_id: str, year: int, month: int) -> str:
    return f"machine-cycle-review:{machine_id}:{year}:{month:02d}"


def _existing_auto_keys(rows: Iterable[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
            continue
        key = str(meta.get("auto_key") or "").strip()
        if key:
            keys.add(key)
    return keys


def _find_auto_by_key(rows: Iterable[dict[str, Any]], auto_key: str) -> dict[str, Any] | None:
    wanted = str(auto_key or "").strip()
    if not wanted:
        return None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
            continue
        if str(meta.get("auto_key") or "").strip() == wanted:
            return row
    return None


def _build_cycle_spec(
    machine: dict[str, Any],
    *,
    planned: dt.date,
    review_type: str | None = None,
) -> dict[str, Any]:
    machine_id = _machine_id(machine)
    name = _machine_name(machine)
    machine_type = _machine_type(machine)
    review_type = str(review_type or _default_review_type(machine)).strip() or "Przegląd okresowy"
    machine_label = f"{machine_id} - {name}" if name else machine_id
    month_name = _MONTH_NAMES.get(planned.month, str(planned.month))
    auto_key = _cycle_key(machine_id, planned.year, planned.month)

    details = [
        "Dyspozycja dodana automatycznie z cyklicznego przeglądu maszyny.",
        f"Maszyna: {machine_label}.",
    ]
    if machine_type:
        details.append(f"Typ maszyny: {machine_type}.")
    details.extend(
        [
            f"Cykl: {month_name} {planned.year}.",
            f"Planowany termin przeglądu: {planned.strftime('%d-%m-%Y')}.",
        ]
    )

    return {
        "typ_dyspozycji": "maszyna",
        "tytul": f"Przegląd cykliczny – {machine_label}",
        "opis": " ".join(details),
        "autor": "system",
        "przypisane_do": "",
        "dla_wszystkich": True,
        "termin": planned.isoformat(),
        "priorytet": "normalny",
        "modul_zrodlowy": "maszyny",
        "obiekt_id": machine_id,
        "status": "nowa",
        "meta": {
            "auto_source": AUTO_SOURCE,
            "auto_key": auto_key,
            "auto_created": True,
            "machine_id": machine_id,
            "object_label": machine_label,
            "cycle_year": planned.year,
            "cycle_month": planned.month,
            "cycle_month_name": month_name,
            "planned_review_date": planned.isoformat(),
            "review_type": review_type,
        },
    }


def collect_due_machine_cycle_specs(
    machines: Iterable[dict[str, Any]],
    existing_dyspozycje: Iterable[dict[str, Any]],
    *,
    today: dt.date | None = None,
    window_days: int = AUTO_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Zwraca brakujące automatyczne Dyspozycje dla cykli w najbliższych dniach."""

    today = today or dt.date.today()
    window_days = max(0, int(window_days))
    existing_keys = _existing_auto_keys(existing_dyspozycje)
    specs: list[dict[str, Any]] = []
    years = (today.year, today.year + 1)

    for machine in machines or []:
        if not isinstance(machine, dict):
            continue
        machine_id = _machine_id(machine)
        months = _review_months(machine)
        if not machine_id or not months:
            continue

        review_type = _default_review_type(machine)
        review_day = _review_day(machine)
        for year in years:
            for month in months:
                planned = _planned_cycle_date(year, month, review_day)
                days_to_due = (planned - today).days
                if days_to_due < 0 or days_to_due > window_days:
                    continue
                if _cycle_done(
                    machine,
                    year=year,
                    month=month,
                    review_type=review_type,
                ):
                    continue

                auto_key = _cycle_key(machine_id, year, month)
                if auto_key in existing_keys:
                    continue
                specs.append(
                    _build_cycle_spec(
                        machine,
                        planned=planned,
                        review_type=review_type,
                    )
                )
                existing_keys.add(auto_key)

    return specs


def find_cycle_dyspozycja_for_review(
    machine: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any] | None:
    machine_id = _machine_id(machine)
    planned = _review_date(review, machine)
    if not machine_id or planned is None:
        return None
    auto_key = _cycle_key(machine_id, planned.year, planned.month)
    return _find_auto_by_key(load_dyspozycje(), auto_key)


def _ensure_cycle_dyspozycja_for_review(
    machine: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any] | None:
    existing = find_cycle_dyspozycja_for_review(machine, review)
    if existing:
        return existing
    machine_id = _machine_id(machine)
    planned = _review_date(review, machine)
    if not machine_id or planned is None:
        return None
    spec = _build_cycle_spec(
        machine,
        planned=planned,
        review_type=str(review.get("type") or review.get("typ") or _default_review_type(machine)),
    )
    item = make_dyspozycja(**spec)
    return add_dyspozycja(item)


def sync_review_to_dyspozycja(
    machine: dict[str, Any],
    review: dict[str, Any],
    *,
    status: str,
    actor: str = "",
    note: str = "",
) -> dict[str, Any] | None:
    """Przenieś rozpoczęcie/wykonanie cyklicznego serwisu do jego Dyspozycji."""

    source = str(review.get("source") or "").strip().lower()
    review_id = str(review.get("id") or "").strip().lower()
    is_cycle = (
        source == "cycle"
        or review_id.startswith("cycle_")
        or bool(review.get("cycle_year") and review.get("cycle_month"))
    )
    if not is_cycle:
        return None

    item = _ensure_cycle_dyspozycja_for_review(machine, review)
    if not item:
        return None
    review["dyspozycja_id"] = str(item.get("id") or "")
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    if meta.get("auto_key"):
        review["auto_key"] = str(meta.get("auto_key"))

    target = str(status or "").strip().lower()
    current = str(item.get("status") or "nowa").strip().lower()
    dysp_id = str(item.get("id") or "").strip()
    if not dysp_id:
        return item

    if target in {"in_progress", "w_toku", "started"}:
        if current == "nowa":
            return set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
        if current == "wstrzymana":
            return set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
        return item

    if target in {"done", "wykonany", "completed", "zamknieta"}:
        if current == "nowa":
            item = set_dyspozycja_status(
                dysp_id, "w_toku", changed_by=actor
            ) or item
            current = str(item.get("status") or current).strip().lower()
        if current in {"w_toku", "wstrzymana"}:
            return set_dyspozycja_status(
                dysp_id,
                "zamknieta",
                changed_by=actor,
                uwagi=note,
            ) or item
    return item


def _id_variants(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    out = {raw, raw.lower()}
    if raw.isdigit():
        out.add(str(int(raw)))
        out.add(raw.zfill(3))
    return out


def sync_machine_review_from_dyspozycja(
    dyspozycja: dict[str, Any],
    *,
    actor: str = "",
    result_note: str = "",
) -> bool:
    """Przenieś start/zamknięcie automatycznej Dyspozycji do wpisu serwisowego maszyny."""

    if not isinstance(dyspozycja, dict):
        return False
    meta = dyspozycja.get("meta") if isinstance(dyspozycja.get("meta"), dict) else {}
    if str(meta.get("auto_source") or "").strip() != AUTO_SOURCE:
        return False

    machine_id = str(meta.get("machine_id") or dyspozycja.get("obiekt_id") or "").strip()
    dysp_id = str(dyspozycja.get("id") or "").strip()
    planned = _parse_date(meta.get("planned_review_date") or dyspozycja.get("termin"))
    if not machine_id or not dysp_id or planned is None:
        return False

    try:
        from gui_maszyny import (
            _apply_machine_status_change,
            _machine_now_iso,
            _normalize_machine_status,
            _save_machines,
            get_config,
            load_machines_rows_with_fallback,
            resolve_rel,
        )
    except Exception:
        return False

    cfg = get_config() or {}
    rows, primary_path = load_machines_rows_with_fallback(cfg, resolve_rel)
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    wanted_ids = _id_variants(machine_id)
    machine_index = None
    for idx, row in enumerate(rows):
        rid = _machine_id(row)
        if wanted_ids.intersection(_id_variants(rid)):
            machine_index = idx
            break
    if machine_index is None:
        return False

    machine = dict(rows[machine_index])
    raw_reviews = machine.get("reviews")
    reviews = [
        dict(review)
        for review in raw_reviews
        if isinstance(review, dict)
    ] if isinstance(raw_reviews, list) else []
    review_type = str(meta.get("review_type") or _default_review_type(machine)).strip()
    auto_key = str(meta.get("auto_key") or _cycle_key(machine_id, planned.year, planned.month))

    target_review: dict[str, Any] | None = None
    for review in reviews:
        if str(review.get("dyspozycja_id") or "").strip() == dysp_id:
            target_review = review
            break
    if target_review is None:
        for review in reviews:
            source = str(review.get("source") or "").strip().lower()
            date_value = _review_date(review, machine)
            current_type = str(review.get("type") or review.get("typ") or "").strip()
            if (
                source == "cycle"
                and date_value is not None
                and date_value.year == planned.year
                and date_value.month == planned.month
                and (not current_type or current_type == review_type)
            ):
                target_review = review
                break

    if target_review is None:
        month_name = _MONTH_NAMES.get(planned.month, str(planned.month))
        target_review = {
            "id": f"rev_auto_{planned.year}{planned.month:02d}_{machine_id}",
            "type": review_type or "Przegląd okresowy",
            "planned_date": planned.isoformat(),
            "status": "planned",
            "source": "cycle",
            "cycle_year": planned.year,
            "cycle_month": planned.month,
            "suggested_workers": list(machine.get("review_workers") or [])
            if isinstance(machine.get("review_workers"), list)
            else [],
            "description": f"Przegląd cykliczny: {month_name} {planned.year}",
            "completed_at": "",
            "completed_by": [],
            "result_note": "",
            "photos": [],
        }
        reviews.append(target_review)

    target_review["dyspozycja_id"] = dysp_id
    target_review["auto_key"] = auto_key
    target_review["planned_date"] = planned.isoformat()
    target_review["source"] = "cycle"
    target_review["cycle_year"] = planned.year
    target_review["cycle_month"] = planned.month

    status = str(dyspozycja.get("status") or "").strip().lower()
    who = str(
        actor
        or dyspozycja.get("zamkniete_przez")
        or dyspozycja.get("wykonuje")
        or dyspozycja.get("autor")
        or "system"
    ).strip()

    if status == "w_toku" and not _is_done_status(target_review.get("status")):
        target_review["status"] = "in_progress"
        target_review["started_at"] = str(
            dyspozycja.get("rozpoczal_at") or _machine_now_iso()
        )
        target_review["started_by"] = who
        if _normalize_machine_status(machine.get("status")) != "warn":
            note = (
                f"Rozpoczęto {review_type or 'przegląd / serwis'}"
                f" | plan: {planned.isoformat()} | Dyspozycja: {dysp_id}"
            )
            _apply_machine_status_change(
                machine,
                "alert",
                actor=who,
                note=note,
                photos=[],
            )
    elif status == "zamknieta":
        target_review["status"] = "done"
        target_review["completed_at"] = str(
            dyspozycja.get("zamknieto_at")
            or dyspozycja.get("wykonano")
            or _machine_now_iso()
        )
        target_review["completed_by"] = [who] if who else []
        note_value = str(result_note or dyspozycja.get("uwagi") or "").strip()
        if note_value:
            target_review["result_note"] = note_value
        if _normalize_machine_status(machine.get("status")) == "alert":
            note = (
                f"Wykonano {review_type or 'przegląd / serwis'}"
                f" | plan: {planned.isoformat()} | Dyspozycja: {dysp_id}"
            )
            if note_value:
                note += f" | {note_value}"
            _apply_machine_status_change(
                machine,
                "ok",
                actor=who,
                note=note,
                photos=[],
            )
    else:
        return False

    machine["reviews"] = reviews
    rows[machine_index] = machine
    return bool(_save_machines(primary_path, rows))


def ensure_due_machine_cycle_dyspozycje(
    *,
    today: dt.date | None = None,
    window_days: int = AUTO_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Dodaje brakujące cykliczne Dyspozycje i zwraca tylko nowo utworzone rekordy."""

    try:
        from gui_maszyny import load_machines_rows

        machines = load_machines_rows()
    except Exception:
        machines = []

    existing = load_dyspozycje()
    specs = collect_due_machine_cycle_specs(
        machines,
        existing,
        today=today,
        window_days=window_days,
    )

    created: list[dict[str, Any]] = []
    for spec in specs:
        auto_key = str((spec.get("meta") or {}).get("auto_key") or "").strip()
        if auto_key and auto_key in _existing_auto_keys(load_dyspozycje()):
            continue
        item = make_dyspozycja(**spec)
        created.append(add_dyspozycja(item))
    return created
'''


def patch_maszyny_dyspozycje() -> None:
    Path("maszyny_dyspozycje.py").write_text(NEW_MASZYNY_DYSPOZYCJE, encoding="utf-8")


def main() -> None:
    patch_gui_maszyny()
    patch_maszyny_dyspozycje()
    patch_gui_zlecenia()
    patch_gui_creator()
    patch_utils_maszyny()


if __name__ == "__main__":
    main()
