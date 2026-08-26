# version: 1.1
# Zmiany 1.1:
# - Zamknięcie przeglądu z Dyspozycji zapisuje wpis P do DOCX bezpośrednio po historii WM.
# - Wyłączono dla tego formularza pośredni hook DOCX, aby nie tworzyć podwójnych wpisów.
"""Zamykanie Dyspozycji przeglądu maszyny przez formularz wykonania serwisu."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_AUTO_SOURCE = "machine_cycle_review"


def _is_machine_review_dyspozycja(row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    source = str(meta.get("auto_source") or "").strip()
    auto_key = str(meta.get("auto_key") or "").strip()
    return source == _AUTO_SOURCE or auto_key.startswith("machine-cycle-review:")


def _copy_role_to_owner(parent, owner) -> None:
    sources = [parent]
    try:
        sources.append(parent.winfo_toplevel())
    except Exception:
        pass
    for source in sources:
        if source is None:
            continue
        for attr in ("_wm_rola", "rola", "role", "user_role"):
            try:
                value = getattr(source, attr, "")
            except Exception:
                value = ""
            if str(value or "").strip():
                try:
                    setattr(owner, "_wm_rola", value)
                except Exception:
                    pass
                return


def _machine_id(row: dict[str, Any]) -> str:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    return str(
        meta.get("machine_id")
        or row.get("obiekt_id")
        or row.get("maszyna_id")
        or ""
    ).strip()


def _patch_completed_review(
    gui_maszyny,
    *,
    machine_id: str,
    dysp_id: str,
    auto_key: str,
    completed_at: str,
    completed_by: list[str],
    result_note: str,
) -> bool:
    """Uzupełnij dokładną datę/osoby po synchronizacji Dyspozycja -> Maszyna."""

    try:
        cfg = gui_maszyny.get_config() or {}
        rows, primary_path = gui_maszyny.load_machines_rows_with_fallback(
            cfg, gui_maszyny.resolve_rel
        )
    except Exception:
        logger.exception("[DYSP][MASZYNY] Nie udało się ponownie wczytać maszyn.")
        return False

    rows = [dict(row) for row in rows if isinstance(row, dict)]
    wanted = str(machine_id or "").strip()
    wanted_numeric = int(wanted) if wanted.isdigit() else None

    for idx, machine in enumerate(rows):
        current_id = str(
            machine.get("id") or machine.get("nr_ewid") or machine.get("nr") or ""
        ).strip()
        same_machine = current_id == wanted
        if not same_machine and wanted_numeric is not None and current_id.isdigit():
            same_machine = int(current_id) == wanted_numeric
        if not same_machine:
            continue

        reviews_raw = machine.get("reviews")
        reviews = [
            dict(item) for item in reviews_raw if isinstance(item, dict)
        ] if isinstance(reviews_raw, list) else []

        target = None
        for review in reviews:
            if str(review.get("dyspozycja_id") or "").strip() == dysp_id:
                target = review
                break
        if target is None and auto_key:
            for review in reviews:
                if str(review.get("auto_key") or "").strip() == auto_key:
                    target = review
                    break
        if target is None:
            logger.warning(
                "[DYSP][MASZYNY] Nie znaleziono wpisu przeglądu po zamknięciu %s.",
                dysp_id,
            )
            return False

        target["status"] = "done"
        target["completed_at"] = completed_at
        target["completed_by"] = list(completed_by)
        target["result_note"] = str(result_note or "").strip()
        machine["reviews"] = reviews
        rows[idx] = machine

        try:
            return bool(gui_maszyny._save_machines(primary_path, rows))
        except Exception:
            logger.exception(
                "[DYSP][MASZYNY] Nie udało się zapisać daty/osób wykonania przeglądu."
            )
            return False

    return False


def _find_completed_review_for_docx(
    machine: dict[str, Any], *, dysp_id: str, auto_key: str
) -> dict[str, Any] | None:
    reviews = machine.get("reviews")
    if not isinstance(reviews, list):
        return None
    for review in reviews:
        if not isinstance(review, dict):
            continue
        if str(review.get("dyspozycja_id") or "").strip() == dysp_id:
            return review
    if auto_key:
        for review in reviews:
            if not isinstance(review, dict):
                continue
            if str(review.get("auto_key") or "").strip() == auto_key:
                return review
    return None


def _write_docx_after_review(
    gui_maszyny,
    *,
    machine_id: str,
    dysp_id: str,
    auto_key: str,
    completed_at: str,
    completed_by: list[str],
    result_note: str,
    parent=None,
) -> bool:
    """Dopisz P do przypisanego DOCX po poprawnym zapisie historii WM."""

    try:
        import machine_history_runtime as history_runtime

        machine = history_runtime._find_machine(gui_maszyny, machine_id)
        if not machine:
            logger.warning(
                "[DYSP][DOCX_HISTORY] Po zapisie nie znaleziono maszyny %s.",
                machine_id,
            )
            return False

        review = _find_completed_review_for_docx(
            machine,
            dysp_id=dysp_id,
            auto_key=auto_key,
        )
        description = str(result_note or "").strip()
        if not description and review:
            description = str(
                review.get("result_note")
                or review.get("description")
                or review.get("type")
                or ""
            ).strip()
        if not description:
            description = "Przegląd / serwis"

        return bool(
            history_runtime._write_event(
                machine,
                gui_maszyny,
                entry_type="P",
                performed_at=completed_at,
                performed_by=completed_by,
                description=description,
                parent=parent,
            )
        )
    except Exception:
        logger.exception(
            "[DYSP][DOCX_HISTORY] Nie udało się wykonać bezpośredniego zapisu P."
        )
        return False


def _open_completion_dialog(parent, row: dict[str, Any], *, who: str) -> bool:
    try:
        import gui_maszyny
        from dyspozycje_store import set_dyspozycja_status
        from _maszyny_dyspozycje_core import sync_machine_review_from_dyspozycja
    except Exception:
        logger.exception("[DYSP][MASZYNY] Nie udało się przygotować formularza wykonania.")
        return False

    machine_id = _machine_id(row)
    dysp_id = str(row.get("id") or "").strip()
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    auto_key = str(meta.get("auto_key") or "").strip()
    if not machine_id or not dysp_id:
        return False

    tk = getattr(gui_maszyny, "tk", None)
    ttk = getattr(gui_maszyny, "ttk", None)
    messagebox = getattr(gui_maszyny, "messagebox", None)
    if tk is None or ttk is None or messagebox is None:
        return False

    # Ukryty właściciel zachowuje kontekst roli i ID maszyny.
    owner = tk.Toplevel(parent)
    owner.title(f"Użytkowanie maszyny — {machine_id}")
    _copy_role_to_owner(parent, owner)
    try:
        owner.withdraw()
    except Exception:
        pass

    dialog = tk.Toplevel(owner)
    dialog.title("Oznacz przegląd / serwis jako wykonany")
    # Ten formularz zapisuje DOCX bezpośrednio. Blokujemy tylko automatyczny
    # hook DOCX, aby ten sam przegląd nie został dopisany drugi raz.
    dialog._wm_docx_review_decorated = True
    dialog.geometry("620x520")
    dialog.transient(owner)
    dialog.grab_set()

    frm = ttk.Frame(dialog, padding=12)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Wykonali:").grid(
        row=0, column=0, sticky="ne", padx=4, pady=4
    )
    users_box = ttk.Frame(frm)
    users_box.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

    try:
        user_logins = list(gui_maszyny._load_wm_user_logins())
    except Exception:
        user_logins = []
    actor = str(who or "").strip()
    if actor and actor not in user_logins:
        user_logins.insert(0, actor)
    if not user_logins:
        user_logins = [actor or "system"]

    selected_vars: dict[str, Any] = {}
    for idx, login in enumerate(user_logins):
        var = tk.BooleanVar(value=(login == actor))
        selected_vars[login] = var
        ttk.Checkbutton(
            users_box,
            text=login,
            variable=var,
        ).grid(
            row=idx // 3,
            column=idx % 3,
            sticky="w",
            padx=(0, 12),
            pady=2,
        )

    ttk.Label(frm, text="Co wykonano:").grid(
        row=1, column=0, sticky="ne", padx=4, pady=4
    )
    txt_result = tk.Text(frm, height=10, wrap="word")
    txt_result.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
    frm.rowconfigure(1, weight=1)

    def _close_windows() -> None:
        try:
            dialog.destroy()
        except Exception:
            pass
        try:
            owner.destroy()
        except Exception:
            pass

    def _save_completed() -> None:
        completed_by = [
            login for login, var in selected_vars.items() if bool(var.get())
        ]
        if not completed_by:
            messagebox.showwarning(
                "Przegląd / serwis",
                "Wybierz przynajmniej jedną osobę, która wykonała przegląd/serwis.",
                parent=dialog,
            )
            return

        result_note = txt_result.get("1.0", "end").strip()
        # Dla Brygadzisty tę funkcję na czas kliknięcia podmienia istniejący
        # mechanizm daty wstecz/kalendarza, więc ta wartość jest wspólna dla WM i DOCX.
        performed_at = str(gui_maszyny._machine_now_iso())
        changed = set_dyspozycja_status(
            dysp_id,
            "zamknieta",
            changed_by=actor or str(row.get("autor") or "").strip(),
            uwagi=result_note,
        )
        if not changed:
            messagebox.showerror(
                "Dyspozycje",
                "Nie udało się zamknąć Dyspozycji.",
                parent=dialog,
            )
            return

        review_actor = ", ".join(completed_by)
        try:
            synced = sync_machine_review_from_dyspozycja(
                changed,
                actor=review_actor,
                result_note=result_note,
            )
        except Exception as exc:
            logger.exception(
                "[DYSP][MASZYNY] Dyspozycja zamknięta, ale synchronizacja przeglądu nie powiodła się."
            )
            messagebox.showwarning(
                "Dyspozycje / Maszyny",
                "Dyspozycja została zamknięta, ale nie udało się zsynchronizować "
                f"przeglądu maszyny:\n{exc}",
                parent=dialog,
            )
            return

        if not synced:
            messagebox.showwarning(
                "Dyspozycje / Maszyny",
                "Dyspozycja została zamknięta, ale nie znaleziono powiązanego "
                "przeglądu maszyny.",
                parent=dialog,
            )
            return

        patched = _patch_completed_review(
            gui_maszyny,
            machine_id=machine_id,
            dysp_id=dysp_id,
            auto_key=auto_key,
            completed_at=performed_at,
            completed_by=completed_by,
            result_note=result_note,
        )
        if not patched:
            messagebox.showwarning(
                "Dyspozycje / Maszyny",
                "Dyspozycja została zamknięta, ale nie udało się zapisać dokładnej "
                "daty/osób w historii przeglądu. Wpis DOCX nie został wykonany.",
                parent=dialog,
            )
            return

        _write_docx_after_review(
            gui_maszyny,
            machine_id=machine_id,
            dysp_id=dysp_id,
            auto_key=auto_key,
            completed_at=performed_at,
            completed_by=completed_by,
            result_note=result_note,
            parent=owner,
        )

        try:
            parent.winfo_toplevel().event_generate(
                "<<DyspozycjeUpdated>>", when="tail"
            )
        except Exception:
            pass
        _close_windows()

    btns = ttk.Frame(frm)
    btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(
        btns,
        text="Zapisz wykonanie",
        command=_save_completed,
    ).pack(side="left", padx=4)
    ttk.Button(
        btns,
        text="Anuluj",
        command=_close_windows,
    ).pack(side="left", padx=4)
    dialog.protocol("WM_DELETE_WINDOW", _close_windows)
    return True


def _try_handle_close(view) -> bool:
    try:
        row = view._selected_row()
    except Exception:
        return False
    if not _is_machine_review_dyspozycja(row):
        return False

    status = str((row or {}).get("status") or "").strip().lower()
    if status not in {"w_toku", "wstrzymana"}:
        return False

    who = str(
        getattr(view, "_login_user", "")
        or (row or {}).get("autor")
        or ""
    ).strip()
    return _open_completion_dialog(view, dict(row or {}), who=who)


def install_machine_review_dysp_close(gui_module) -> bool:
    """Przechwyć Zamknij tylko dla Dyspozycji cyklicznego przeglądu maszyny."""
    if gui_module is None:
        return False

    ttk_module = getattr(gui_module, "ttk", None)
    if ttk_module is None:
        return False
    if getattr(ttk_module, "_wm_machine_review_close_proxy", False):
        return True

    real_button = getattr(ttk_module, "Button", None)
    if real_button is None:
        return False

    class _ReviewAwareButton(real_button):
        def __init__(self, *args, **kwargs):
            text = str(kwargs.get("text") or "")
            command = kwargs.get("command")
            if text == "Zamknij Dyspozycję" and callable(command):
                original_command = command

                def _wrapped_command(*_args, **_kwargs):
                    view = getattr(original_command, "__self__", None)
                    try:
                        if view is not None and _try_handle_close(view):
                            return None
                    except Exception:
                        logger.exception(
                            "[DYSP][MASZYNY] Błąd otwierania formularza wykonania przeglądu."
                        )
                    return original_command()

                kwargs["command"] = _wrapped_command
            super().__init__(*args, **kwargs)

    class _TtkProxy:
        _wm_machine_review_close_proxy = True
        _wm_base_ttk = getattr(ttk_module, "_wm_base_ttk", ttk_module)
        Button = _ReviewAwareButton

        def __getattr__(self, name: str):
            return getattr(ttk_module, name)

    gui_module.ttk = _TtkProxy()
    return True


__all__ = ["install_machine_review_dysp_close"]
