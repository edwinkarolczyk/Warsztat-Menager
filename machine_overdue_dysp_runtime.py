# version: 1.0
"""Obsługa Dyspozycji dla zaległych cyklicznych przeglądów maszyn.

Rozszerzenie nie zmienia automatycznego okna tworzenia Dyspozycji przed terminem.
Dodaje:
- akcję zbiorczą dla brakujących zaległych Dyspozycji w komunikacie Maszyn,
- ręczny przycisk „Utwórz Dyspozycję” przy wybranym zaległym przeglądzie.
"""

from __future__ import annotations

import datetime as dt
import inspect
import logging
import re

logger = logging.getLogger(__name__)

_DONE_REVIEW_STATUSES = {
    "done",
    "wykonany",
    "wykonane",
    "completed",
    "zamkniety",
    "zamknięty",
    "cancelled",
    "canceled",
    "anulowany",
    "anulowane",
}


def _machine_id(machine) -> str:
    if not isinstance(machine, dict):
        return ""
    return str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or machine.get("kod")
        or ""
    ).strip()


def _id_variants(value: object) -> set[str]:
    raw = str(value or "").strip()
    variants = {raw} if raw else set()
    if raw.isdigit():
        variants.add(str(int(raw)))
        variants.add(raw.zfill(3))
    return variants


def _find_machine(gui_module, machine_id: str):
    loader = getattr(gui_module, "load_machines_rows", None)
    if not callable(loader):
        return None
    wanted = _id_variants(machine_id)
    try:
        rows = loader() or []
    except Exception:
        logger.exception("[Maszyny][OVERDUE_DYSPO] Nie udało się wczytać maszyn.")
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _id_variants(_machine_id(row)) & wanted:
            return row
    return None


def _is_cycle_review(review) -> bool:
    if not isinstance(review, dict):
        return False
    source = str(review.get("source") or "").strip().casefold()
    review_id = str(review.get("id") or "").strip().casefold()
    return bool(
        source == "cycle"
        or review_id.startswith("cycle_")
        or (review.get("cycle_year") and review.get("cycle_month"))
    )


def _is_review_done(review) -> bool:
    if not isinstance(review, dict):
        return True
    status = str(review.get("status") or "").strip().casefold()
    return status in _DONE_REVIEW_STATUSES


def _planned_date(core, machine, review) -> dt.date | None:
    resolver = getattr(core, "_review_date", None)
    if callable(resolver):
        try:
            value = resolver(review, machine)
            if isinstance(value, dt.datetime):
                return value.date()
            if isinstance(value, dt.date):
                return value
        except Exception:
            pass

    raw = str(
        (review or {}).get("planned_date")
        or (review or {}).get("date")
        or (review or {}).get("data")
        or ""
    ).strip()
    try:
        return dt.date.fromisoformat(raw[:10]) if raw else None
    except Exception:
        return None


def _emit_dyspozycje_updated(widget) -> None:
    current = widget
    while current is not None:
        try:
            current.event_generate("<<DyspozycjeUpdated>>", when="tail")
        except Exception:
            pass
        current = getattr(current, "master", None)


def _ensure_review_dyspozycja(gui_module, machine, review):
    """Zwróć (rekord, utworzono_nowy) dla jednego zaległego cyklu."""
    import _maszyny_dyspozycje_core as core

    finder = getattr(core, "find_cycle_dyspozycja_for_review", None)
    ensure = getattr(core, "_ensure_cycle_dyspozycja_for_review", None)
    if not callable(finder) or not callable(ensure):
        raise RuntimeError("Brak funkcji powiązania cyklicznego przeglądu z Dyspozycją.")

    existing = finder(machine, review)
    if existing:
        return existing, False

    created = ensure(machine, review)
    if not created:
        raise RuntimeError("Nie udało się utworzyć Dyspozycji dla przeglądu.")
    return created, True


def _create_missing_overdue(gui_module) -> tuple[int, int, int]:
    """Utwórz brakujące Dyspozycje dla zaległych cykli bieżącego harmonogramu."""
    import _maszyny_dyspozycje_core as core

    loader = getattr(gui_module, "load_machines_rows", None)
    entries_builder = getattr(gui_module, "_combined_machine_review_entries", None)
    if not callable(loader) or not callable(entries_builder):
        raise RuntimeError("Moduł Maszyn nie udostępnia harmonogramu przeglądów.")

    today = dt.date.today()
    created_count = 0
    existing_count = 0
    error_count = 0

    try:
        machines = loader() or []
    except Exception as exc:
        raise RuntimeError(f"Nie udało się wczytać maszyn: {exc}") from exc

    for machine in machines:
        if not isinstance(machine, dict):
            continue
        try:
            entries = entries_builder(machine, today=today, years_ahead=1) or []
        except Exception:
            logger.exception(
                "[Maszyny][OVERDUE_DYSPO] Nie udało się zbudować harmonogramu maszyny %s.",
                _machine_id(machine),
            )
            error_count += 1
            continue

        for review in entries:
            if not isinstance(review, dict):
                continue
            if not _is_cycle_review(review) or _is_review_done(review):
                continue
            planned = _planned_date(core, machine, review)
            if planned is None or planned >= today:
                continue
            try:
                _row, created = _ensure_review_dyspozycja(gui_module, machine, review)
                if created:
                    created_count += 1
                else:
                    existing_count += 1
            except Exception:
                error_count += 1
                logger.exception(
                    "[Maszyny][OVERDUE_DYSPO] Błąd tworzenia Dyspozycji: maszyna=%s data=%s",
                    _machine_id(machine),
                    planned,
                )

    return created_count, existing_count, error_count


def _show_bulk_result(gui_module, parent, created: int, existing: int, errors: int) -> None:
    box = getattr(gui_module, "messagebox", None)
    if box is None:
        return
    lines = [f"Utworzono brakujące Dyspozycje: {created}"]
    if existing:
        lines.append(f"Już istniały (pominięto): {existing}")
    if errors:
        lines.append(f"Błędy: {errors}")
    try:
        box.showinfo(
            "Zaległe przeglądy",
            "\n".join(lines),
            parent=parent,
        )
    except Exception:
        pass


def _show_overdue_actions_dialog(gui_module, parent, original_message: str) -> bool:
    """Zwraca True wyłącznie dla akcji „Pokaż zaległe”."""
    tk_module = getattr(gui_module, "tk", None)
    ttk_module = getattr(gui_module, "ttk", None)
    if tk_module is None or ttk_module is None:
        return False

    base_tk = getattr(tk_module, "_wm_base_tk", tk_module)
    real_toplevel = getattr(base_tk, "Toplevel", None)
    if real_toplevel is None:
        return False

    win = real_toplevel(parent)
    win.title("Przeglądy maszyn")
    win.resizable(False, False)
    try:
        win.transient(parent)
    except Exception:
        pass

    result = {"show": False}
    frame = ttk_module.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)

    summary_lines = []
    for line in str(original_message or "").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("Odpowiednie Dyspozycje") or text.startswith("Pokazać te maszyny"):
            continue
        summary_lines.append(text)

    ttk_module.Label(
        frame,
        text="\n".join(summary_lines),
        justify="left",
    ).pack(anchor="w")
    ttk_module.Label(
        frame,
        text=(
            "Automat nadal tworzy Dyspozycje w ustawionym oknie przed terminem.\n"
            "Dla zaległych przeglądów możesz utworzyć tylko brakujące Dyspozycje."
        ),
        justify="left",
    ).pack(anchor="w", pady=(10, 12))

    buttons = ttk_module.Frame(frame)
    buttons.pack(fill="x")

    def _close(show: bool = False) -> None:
        result["show"] = bool(show)
        try:
            win.destroy()
        except Exception:
            pass

    def _create_all() -> None:
        try:
            created, existing, errors = _create_missing_overdue(gui_module)
            _show_bulk_result(gui_module, win, created, existing, errors)
            _emit_dyspozycje_updated(parent)
        except Exception as exc:
            box = getattr(gui_module, "messagebox", None)
            if box is not None:
                try:
                    box.showerror(
                        "Zaległe przeglądy",
                        f"Nie udało się utworzyć Dyspozycji:\n{exc}",
                        parent=win,
                    )
                except Exception:
                    pass
        _close(False)

    ttk_module.Button(
        buttons,
        text="Pokaż zaległe",
        command=lambda: _close(True),
    ).pack(side="left", padx=(0, 6))
    ttk_module.Button(
        buttons,
        text="Utwórz brakujące Dyspozycje",
        command=_create_all,
    ).pack(side="left", padx=(0, 6))
    ttk_module.Button(
        buttons,
        text="Anuluj",
        command=lambda: _close(False),
    ).pack(side="left")

    try:
        win.protocol("WM_DELETE_WINDOW", lambda: _close(False))
        win.grab_set()
        win.focus_force()
        win.wait_window()
    except Exception:
        try:
            win.wait_window()
        except Exception:
            pass
    return bool(result["show"])


def _install_notice_proxy(gui_module) -> bool:
    messagebox = getattr(gui_module, "messagebox", None)
    if messagebox is None:
        return False
    if getattr(messagebox, "_wm_overdue_dysp_proxy", False):
        return True

    original = messagebox

    class _MessageboxProxy:
        _wm_overdue_dysp_proxy = True

        def askyesno(self, title, message, *args, **kwargs):
            text = str(message or "")
            match = re.search(r"Po terminie:\s*(\d+)", text, flags=re.IGNORECASE)
            if (
                str(title or "").strip() == "Przeglądy maszyn"
                and match
                and int(match.group(1)) > 0
                and "Odpowiednie Dyspozycje" in text
            ):
                parent = kwargs.get("parent")
                return _show_overdue_actions_dialog(gui_module, parent, text)
            return original.askyesno(title, message, *args, **kwargs)

        def __getattr__(self, name: str):
            return getattr(original, name)

    gui_module.messagebox = _MessageboxProxy()
    return True


def _machine_id_from_widget(widget) -> str:
    current = widget
    while current is not None:
        try:
            title = str(current.title() or "")
        except Exception:
            title = ""
        if "Użytkowanie maszyny" in title:
            for separator in ("—", "-"):
                if separator in title:
                    value = title.rsplit(separator, 1)[-1].strip()
                    if value:
                        return value
        current = getattr(current, "master", None)
    return ""


def _manual_create_for_selected(gui_module, owner_widget, selection_resolver) -> None:
    box = getattr(gui_module, "messagebox", None)
    parent = None
    try:
        parent = owner_widget.winfo_toplevel()
    except Exception:
        parent = None

    if not callable(selection_resolver):
        if box is not None:
            box.showwarning(
                "Dyspozycja przeglądu",
                "Nie udało się odczytać zaznaczonego przeglądu.",
                parent=parent,
            )
        return

    review = selection_resolver()
    if not isinstance(review, dict):
        if box is not None:
            box.showinfo(
                "Dyspozycja przeglądu",
                "Wybierz zaległy przegląd z listy.",
                parent=parent,
            )
        return

    machine_id = _machine_id_from_widget(owner_widget)
    machine = _find_machine(gui_module, machine_id)
    if not machine:
        if box is not None:
            box.showwarning(
                "Dyspozycja przeglądu",
                "Nie udało się odnaleźć maszyny dla wybranego przeglądu.",
                parent=parent,
            )
        return

    if not _is_cycle_review(review):
        if box is not None:
            box.showinfo(
                "Dyspozycja przeglądu",
                "Ręczne tworzenie dotyczy zaległych przeglądów cyklicznych.",
                parent=parent,
            )
        return
    if _is_review_done(review):
        if box is not None:
            box.showinfo(
                "Dyspozycja przeglądu",
                "Ten przegląd jest już wykonany albo anulowany.",
                parent=parent,
            )
        return

    import _maszyny_dyspozycje_core as core

    planned = _planned_date(core, machine, review)
    if planned is None:
        if box is not None:
            box.showwarning(
                "Dyspozycja przeglądu",
                "Wybrany przegląd nie ma poprawnej daty planowanej.",
                parent=parent,
            )
        return
    if planned >= dt.date.today():
        if box is not None:
            box.showinfo(
                "Dyspozycja przeglądu",
                "Ten przycisk służy do tworzenia Dyspozycji dla przeglądów po terminie.",
                parent=parent,
            )
        return

    try:
        row, created = _ensure_review_dyspozycja(gui_module, machine, review)
    except Exception as exc:
        if box is not None:
            box.showerror(
                "Dyspozycja przeglądu",
                f"Nie udało się utworzyć Dyspozycji:\n{exc}",
                parent=parent,
            )
        return

    dysp_id = str((row or {}).get("id") or "").strip()
    status = str((row or {}).get("status") or "").strip()
    if box is not None:
        if created:
            box.showinfo(
                "Dyspozycja przeglądu",
                f"Utworzono Dyspozycję {dysp_id or 'dla przeglądu'}\nTermin przeglądu: {planned.strftime('%d-%m-%Y')}",
                parent=parent,
            )
        else:
            box.showinfo(
                "Dyspozycja przeglądu",
                f"Dyspozycja już istnieje: {dysp_id or '—'}\nStatus: {status or '—'}",
                parent=parent,
            )
    _emit_dyspozycje_updated(parent or owner_widget)


def _install_manual_button_proxy(gui_module) -> bool:
    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None:
        return False
    if getattr(ttk_module, "_wm_overdue_dysp_button_proxy", False):
        return True

    base_button = getattr(ttk_module, "Button", None)
    if base_button is None:
        return False

    class _OverdueDyspButton(base_button):
        def __init__(self, *args, **kwargs):
            original_command = kwargs.get("command")
            text = str(kwargs.get("text") or "")
            super().__init__(*args, **kwargs)

            if text != "Oznacz jako wykonany":
                return

            nonlocals = {}
            if callable(original_command):
                try:
                    nonlocals = inspect.getclosurevars(original_command).nonlocals
                except Exception:
                    nonlocals = {}
            selection_resolver = nonlocals.get("_selected_review_entry")

            def _add_button() -> None:
                master = getattr(self, "master", None)
                if master is None or getattr(master, "_wm_overdue_dysp_button_added", False):
                    return
                try:
                    button = base_button(
                        master,
                        text="Utwórz Dyspozycję",
                        command=lambda: _manual_create_for_selected(
                            gui_module,
                            self,
                            selection_resolver,
                        ),
                    )
                    button.pack(side="left", padx=(0, 6))
                    master._wm_overdue_dysp_button_added = True
                except Exception:
                    logger.exception(
                        "[Maszyny][OVERDUE_DYSPO] Nie udało się dodać przycisku ręcznej Dyspozycji."
                    )

            try:
                self.after_idle(_add_button)
            except Exception:
                _add_button()

    class _TtkProxy:
        _wm_overdue_dysp_button_proxy = True
        _wm_base_ttk = getattr(ttk_module, "_wm_base_ttk", ttk_module)
        Button = _OverdueDyspButton

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkProxy()
    return True


def install_machine_overdue_dysp(gui_module) -> bool:
    """Podłącz obsługę brakujących Dyspozycji dla zaległych przeglądów."""
    if gui_module is None:
        return False
    notice_ok = _install_notice_proxy(gui_module)
    button_ok = _install_manual_button_proxy(gui_module)
    return bool(notice_ok or button_ok)


__all__ = ["install_machine_overdue_dysp"]
