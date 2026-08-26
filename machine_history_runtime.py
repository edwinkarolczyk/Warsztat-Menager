# version: 1.0
"""Integracja GUI dodatkowej historii DOCX i wydruku planu serwisów maszyn."""

from __future__ import annotations

import datetime as dt
import logging
import os
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from machine_history_doc import append_history_entry

logger = logging.getLogger(__name__)

_DONE_STATUSES = {
    "done",
    "wykonany",
    "wykonane",
    "completed",
    "zamkniety",
    "zamknięty",
}


def _normalize_text(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("\xa0", " ").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _machine_id(machine: Mapping[str, Any]) -> str:
    return str(
        machine.get("id")
        or machine.get("nr_ewid")
        or machine.get("nr")
        or machine.get("numer")
        or ""
    ).strip()


def _status_key(value: object) -> str:
    raw = _normalize_text(value).replace("_", " ").replace("-", " ")
    if raw in {"warn", "warm", "warning", "awaria", "stop"}:
        return "warn"
    if raw in {"ok", "sprawna", "sprawny", "sprawne"}:
        return "ok"
    if raw in {"alert", "serwis", "przeglad", "serwis/przeglad"}:
        return "alert"
    return raw


def _review_done(review: Mapping[str, Any]) -> bool:
    return _normalize_text(review.get("status")) in _DONE_STATUSES


def _review_identity(review: Mapping[str, Any]) -> tuple[str, str]:
    ident = str(review.get("id") or "").strip()
    if not ident:
        ident = "|".join(
            [
                str(review.get("planned_date") or review.get("date") or "").strip(),
                str(review.get("type") or review.get("typ") or "").strip(),
            ]
        )
    completed = str(review.get("completed_at") or review.get("done_at") or "").strip()
    return ident, completed


def _load_machine_rows(gui_module) -> list[dict[str, Any]]:
    loader = getattr(gui_module, "load_machines_rows", None)
    if callable(loader):
        try:
            rows = loader()
            return [dict(row) for row in rows if isinstance(row, dict)]
        except Exception:
            logger.exception("[Maszyny][DOCX_HISTORY] Nie udało się wczytać maszyn.")
    return []


def _find_machine(gui_module, machine_id: str) -> dict[str, Any] | None:
    wanted = str(machine_id or "").strip()
    if not wanted:
        return None
    for machine in _load_machine_rows(gui_module):
        current = _machine_id(machine)
        if current == wanted:
            return machine
        if wanted.isdigit() and current.isdigit() and int(current) == int(wanted):
            return machine
    return None


def _dialog_parent(gui_module):
    tk_module = getattr(gui_module, "tk", None)
    base = getattr(tk_module, "_wm_base_tk", tk_module)
    return getattr(base, "_default_root", None)


def _resolve_docx_absolute(gui_module, stored_path: str) -> str:
    resolver = getattr(gui_module, "_resolve_card_absolute", None)
    if callable(resolver):
        try:
            return str(resolver(stored_path) or "")
        except Exception:
            pass
    return os.path.abspath(os.path.expanduser(stored_path))


def _store_docx_path(gui_module, selected_path: str) -> str:
    resolver = getattr(gui_module, "_resolve_card_storage", None)
    if callable(resolver):
        try:
            return str(resolver(selected_path) or selected_path)
        except Exception:
            pass
    return os.path.normpath(selected_path)


def _warn(gui_module, title: str, text: str, *, parent=None) -> None:
    messagebox = getattr(gui_module, "messagebox", None)
    if messagebox is None:
        logger.warning("%s: %s", title, text)
        return
    try:
        messagebox.showwarning(title, text, parent=parent or _dialog_parent(gui_module))
    except Exception:
        logger.warning("%s: %s", title, text)


def _info(gui_module, title: str, text: str, *, parent=None) -> None:
    messagebox = getattr(gui_module, "messagebox", None)
    if messagebox is None:
        logger.info("%s: %s", title, text)
        return
    try:
        messagebox.showinfo(title, text, parent=parent or _dialog_parent(gui_module))
    except Exception:
        logger.info("%s: %s", title, text)


def _choose_docx(machine: dict[str, Any], gui_module, *, parent=None) -> str:
    filedialog = getattr(gui_module, "filedialog", None)
    if filedialog is None:
        return ""
    try:
        selected = filedialog.askopenfilename(
            parent=parent or _dialog_parent(gui_module),
            title="Wybierz kartę historii maszyny (.docx)",
            filetypes=(("Dokument Word DOCX", "*.docx"),),
        )
    except Exception:
        return ""
    if not selected:
        return ""
    if Path(selected).suffix.casefold() != ".docx":
        _warn(
            gui_module,
            "Karta historii maszyny",
            "Można wybrać tylko plik w formacie .docx.",
            parent=parent,
        )
        return ""
    stored = _store_docx_path(gui_module, selected)
    machine["service_history_file"] = stored
    return stored


def _assigned_docx(machine: Mapping[str, Any], gui_module, *, parent=None) -> str:
    stored = str(machine.get("service_history_file") or "").strip()
    if not stored:
        logger.info(
            "[Maszyny][DOCX_HISTORY] Maszyna %s nie ma przypisanej karty DOCX.",
            _machine_id(machine),
        )
        return ""
    if Path(stored).suffix.casefold() != ".docx":
        _warn(
            gui_module,
            "Karta historii maszyny",
            "Przypisana karta historii nie jest plikiem .docx. "
            "Wybierz poprawny plik przy edycji maszyny.",
            parent=parent,
        )
        return ""
    absolute = _resolve_docx_absolute(gui_module, stored)
    if not absolute or not os.path.isfile(absolute):
        _warn(
            gui_module,
            "Karta historii maszyny",
            "Historia WM została zapisana, ale przypisany plik karty nie istnieje:\n"
            f"{absolute}",
            parent=parent,
        )
        return ""
    return absolute


def _write_event(
    machine: Mapping[str, Any],
    gui_module,
    *,
    entry_type: str,
    performed_at: object,
    performed_by: object,
    description: object,
    parent=None,
) -> bool:
    absolute = _assigned_docx(machine, gui_module, parent=parent)
    if not absolute:
        return False
    try:
        append_history_entry(
            absolute,
            entry_type=entry_type,
            performed_at=performed_at,
            performed_by=performed_by,
            description=description,
        )
        logger.info(
            "[Maszyny][DOCX_HISTORY] Zapisano %s | maszyna=%s | plik=%s",
            entry_type,
            _machine_id(machine),
            absolute,
        )
        return True
    except Exception as exc:
        logger.exception(
            "[Maszyny][DOCX_HISTORY] Nie udało się dopisać historii do %s",
            absolute,
        )
        _warn(
            gui_module,
            "Karta historii maszyny",
            "Historia w WM została zapisana, ale nie udało się dopisać "
            f"wpisu do karty DOCX:\n{exc}",
            parent=parent,
        )
        return False


def _machine_id_from_usage_window(window) -> str:
    current = getattr(window, "master", None)
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


def _walk_widgets(widget):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield from _walk_widgets(child)


def _decorate_completed_review_dialog(window, gui_module) -> None:
    if getattr(window, "_wm_docx_review_decorated", False):
        return
    try:
        title = str(window.title() or "")
    except Exception:
        return
    if "Oznacz przegląd / serwis jako wykonany" not in title:
        return

    button = None
    for child in _walk_widgets(window):
        try:
            text = str(child.cget("text") or "")
        except Exception:
            continue
        if text == "Zapisz wykonanie":
            button = child
            break
    if button is None or getattr(button, "_wm_docx_command_wrapped", False):
        return

    machine_id = _machine_id_from_usage_window(window)
    if not machine_id:
        logger.warning(
            "[Maszyny][DOCX_HISTORY] Nie rozpoznano ID maszyny z okna wykonania."
        )
        return

    try:
        original_tcl_command = str(button.cget("command") or "")
    except Exception:
        original_tcl_command = ""
    if not original_tcl_command:
        return

    def _save_and_write_docx() -> None:
        before_machine = _find_machine(gui_module, machine_id)
        before_done = {
            _review_identity(review)
            for review in (before_machine or {}).get("reviews", [])
            if isinstance(review, dict) and _review_done(review)
        }

        button.tk.call(original_tcl_command)

        after_machine = _find_machine(gui_module, machine_id)
        if not after_machine:
            logger.warning(
                "[Maszyny][DOCX_HISTORY] Po zapisie nie znaleziono maszyny %s.",
                machine_id,
            )
            return

        candidates = [
            review
            for review in after_machine.get("reviews", [])
            if isinstance(review, dict)
            and _review_done(review)
            and _review_identity(review) not in before_done
        ]
        candidates.sort(
            key=lambda review: str(
                review.get("completed_at") or review.get("done_at") or ""
            ),
            reverse=True,
        )
        if not candidates:
            logger.warning(
                "[Maszyny][DOCX_HISTORY] Zapis WM zakończony, ale nie wykryto "
                "nowego wykonanego przeglądu dla maszyny %s.",
                machine_id,
            )
            return

        review = candidates[0]
        _write_event(
            after_machine,
            gui_module,
            entry_type="P",
            performed_at=review.get("completed_at")
            or review.get("done_at")
            or dt.datetime.now().isoformat(),
            performed_by=review.get("completed_by") or [],
            description=review.get("result_note")
            or review.get("description")
            or review.get("type")
            or "Przegląd / serwis",
            parent=getattr(window, "master", None),
        )

    button.configure(command=_save_and_write_docx)
    button._wm_docx_command_wrapped = True
    window._wm_docx_review_decorated = True


def _latest_closed_failure(machine: Mapping[str, Any]) -> Mapping[str, Any] | None:
    history = machine.get("status_history")
    if not isinstance(history, list):
        return None
    candidates = [
        item
        for item in history
        if isinstance(item, dict)
        and _status_key(item.get("status")) == "warn"
        and str(item.get("ended_at") or "").strip()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: str(item.get("ended_at") or ""))


def _decorate_machine_edit_dialog(window, gui_module) -> None:
    if getattr(window, "_wm_docx_runtime_decorated", False):
        return
    if window.__class__.__name__ != "MachineEditDialog":
        return
    row = getattr(window, "_row", None)
    if not isinstance(row, dict):
        return

    window._wm_docx_runtime_decorated = True
    ttk = getattr(gui_module, "ttk", None)
    if ttk is None:
        return

    box = ttk.LabelFrame(
        window,
        text="Dodatkowa karta historii przeglądów i napraw",
    )
    box.pack(side="bottom", fill="x", padx=12, pady=(4, 0))

    label = ttk.Label(box)
    label.pack(side="left", padx=(8, 12), pady=6)
    open_button = ttk.Button(box, text="Otwórz kartę")
    open_button.pack(side="left", pady=6)

    def _refresh() -> None:
        stored = str(row.get("service_history_file") or "").strip()
        if stored:
            label.configure(text=f"Plik: {os.path.basename(stored)}")
            open_button.state(["!disabled"])
        else:
            label.configure(text="Plik: brak")
            open_button.state(["disabled"])

    def _choose() -> None:
        stored = _choose_docx(row, gui_module, parent=window)
        if not stored:
            return
        try:
            window._dirty = True
        except Exception:
            pass
        _refresh()

    def _open() -> None:
        stored = str(row.get("service_history_file") or "").strip()
        if not stored:
            return
        absolute = _resolve_docx_absolute(gui_module, stored)
        if not absolute or not os.path.isfile(absolute):
            _warn(gui_module, "Karta historii maszyny", f"Plik nie istnieje:\n{absolute}", parent=window)
            return
        opener = getattr(gui_module, "_open_external", None)
        if not callable(opener) or not opener(absolute):
            _warn(gui_module, "Karta historii maszyny", "Nie udało się otworzyć pliku.", parent=window)

    ttk.Button(
        box,
        text="Wybierz plik .docx...",
        command=_choose,
    ).pack(side="left", padx=(0, 6), pady=6, before=open_button)
    open_button.configure(command=_open)

    original_on_ok = getattr(window, "_on_ok", None)
    old_status = _status_key(getattr(window, "_old_status", row.get("status")))
    if callable(original_on_ok) and not getattr(original_on_ok, "_wm_docx_runtime_wrapper", False):

        def _on_ok_with_history(updated_row):
            stored = str(row.get("service_history_file") or "").strip()
            if isinstance(updated_row, dict) and stored:
                updated_row["service_history_file"] = stored

            new_status = _status_key(updated_row.get("status")) if isinstance(updated_row, dict) else ""
            machine_id = _machine_id(updated_row) if isinstance(updated_row, dict) else ""
            result = original_on_ok(updated_row)

            if old_status == "warn" and new_status == "ok" and machine_id:
                persisted = _find_machine(gui_module, machine_id)
                event = _latest_closed_failure(persisted or {})
                if persisted and event:
                    _write_event(
                        persisted,
                        gui_module,
                        entry_type="N",
                        performed_at=event.get("ended_at") or dt.datetime.now().isoformat(),
                        performed_by=[
                            str(event.get("closed_by") or event.get("changed_by") or "").strip()
                        ],
                        description=event.get("close_note")
                        or event.get("note")
                        or "Naprawa / przywrócenie sprawności",
                        parent=window,
                    )
                else:
                    logger.warning(
                        "[Maszyny][DOCX_HISTORY] Nie znaleziono zapisanego "
                        "zamknięcia awarii dla maszyny %s.",
                        machine_id,
                    )
            return result

        _on_ok_with_history._wm_docx_runtime_wrapper = True
        window._on_ok = _on_ok_with_history

    _refresh()


def _print_plan(gui_module, *, parent=None) -> None:
    try:
        from machine_service_plan_pdf import generate_machine_service_plan_pdf

        path, count = generate_machine_service_plan_pdf(
            _load_machine_rows(gui_module),
            gui_module=gui_module,
        )
        if count <= 0:
            _info(
                gui_module,
                "Plan przeglądów maszyn",
                "Brak aktywnych lub planowanych przeglądów/serwisów do wydruku.",
                parent=parent,
            )
            return
        opener = getattr(gui_module, "_open_external", None)
        if callable(opener) and opener(str(path)):
            logger.info("[Maszyny][PRINT] Plan przeglądów: %s wpisów -> %s", count, path)
            return
        _info(gui_module, "Plan przeglądów maszyn", f"Zapisano PDF:\n{path}", parent=parent)
    except Exception as exc:
        logger.exception("[Maszyny][PRINT] Nie udało się utworzyć planu przeglądów.")
        _warn(gui_module, "Plan przeglądów maszyn", f"Nie udało się przygotować wydruku:\n{exc}", parent=parent)


def _install_ttk_button_hook(gui_module) -> None:
    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None or getattr(ttk_module, "_wm_machine_print_proxy", False):
        return
    real_button = getattr(ttk_module, "Button", None)
    if real_button is None:
        return

    class _MachineAwareButton(real_button):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                text = str(self.cget("text") or "")
            except Exception:
                text = ""
            if text != "Drukuj pustą kartę maszyny":
                return
            master = getattr(self, "master", None)
            if master is None or getattr(master, "_wm_service_plan_button", None):
                return

            def _add_button() -> None:
                if getattr(master, "_wm_service_plan_button", None):
                    return
                button = real_button(
                    master,
                    text="Drukuj plan przeglądów",
                    command=lambda: _print_plan(gui_module, parent=self.winfo_toplevel()),
                )
                button.pack(side="left", padx=(6, 0))
                master._wm_service_plan_button = button

            try:
                self.after_idle(_add_button)
            except Exception:
                pass

    class _TtkProxy:
        _wm_machine_print_proxy = True
        _wm_base_ttk = ttk_module
        Button = _MachineAwareButton

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkProxy()


def _install_toplevel_hook(gui_module) -> None:
    tk_module = getattr(gui_module, "tk", None)
    if tk_module is None or getattr(tk_module, "_wm_docx_runtime_proxy", False):
        return
    real_toplevel = getattr(tk_module, "Toplevel", None)
    if real_toplevel is None:
        return

    class _HistoryAwareToplevel(real_toplevel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            def _decorate() -> None:
                try:
                    _decorate_machine_edit_dialog(self, gui_module)
                    _decorate_completed_review_dialog(self, gui_module)
                except Exception:
                    logger.exception("[Maszyny][DOCX_HISTORY] Błąd dekorowania okna Maszyn.")

            try:
                self.after_idle(_decorate)
            except Exception:
                pass

    class _TkProxy:
        _wm_docx_runtime_proxy = True
        _wm_base_tk = tk_module
        Toplevel = _HistoryAwareToplevel

        def __getattr__(self, name: str):
            return getattr(tk_module, name)

    gui_module.tk = _TkProxy()


def install_gui_integration(gui_module) -> bool:
    """Podłącz kartę DOCX oraz przycisk wydruku planu do ``gui_maszyny``."""

    if gui_module is None:
        return False
    if getattr(gui_module, "_wm_machine_history_runtime_installed", False):
        return True

    required = (
        "_resolve_card_storage",
        "_resolve_card_absolute",
        "_open_external",
        "filedialog",
        "messagebox",
        "ttk",
        "tk",
    )
    if any(not hasattr(gui_module, name) for name in required):
        return False

    _install_ttk_button_hook(gui_module)
    _install_toplevel_hook(gui_module)
    gui_module._wm_machine_history_runtime_installed = True
    logger.info("[Maszyny][DOCX_HISTORY] Integracja runtime 1.0 aktywna.")
    return True


__all__ = ["install_gui_integration"]
