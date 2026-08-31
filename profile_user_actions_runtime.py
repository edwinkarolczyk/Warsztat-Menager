# version: 1.0
"""Drobne akcje użytkownika w aktywnym Profilu WM.

- własna edycja profilu z kalendarzem dla ``zatrudniony_od``;
- zamykanie Dyspozycji na podstawie świeżego rekordu ze wspólnego store.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from dyspozycje_store import get_dyspozycja
from logger import log_akcja
from services.profile_service import get_user, save_user
from ui_theme import apply_theme_safe as apply_theme


_FIELD_LABELS = {
    "imie": "Imię",
    "nazwisko": "Nazwisko",
    "zatrudniony_od": "Zatrudniony od",
    "telefon": "Telefon",
    "email": "E-mail",
}


class ProfileDatePicker(tk.Toplevel):
    """Mały kalendarz bez zewnętrznej biblioteki, zapisujący YYYY-MM-DD."""

    def __init__(self, owner: tk.Misc, variable: tk.StringVar) -> None:
        super().__init__(owner)
        self.variable = variable
        self.title("Wybierz datę")
        self.transient(owner.winfo_toplevel())
        self.resizable(False, False)
        apply_theme(self)
        self.grab_set()

        initial = self._parse_date(variable.get()) or date.today()
        self.year = initial.year
        self.month = initial.month

        self._header = ttk.Frame(self, padding=(8, 8, 8, 2))
        self._header.pack(fill="x")
        ttk.Button(self._header, text="‹", width=3, command=lambda: self._move_month(-1)).pack(side="left")
        self._title_var = tk.StringVar(master=self)
        ttk.Label(self._header, textvariable=self._title_var, anchor="center", width=18).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(self._header, text="›", width=3, command=lambda: self._move_month(1)).pack(side="right")

        self._body = ttk.Frame(self, padding=(8, 2, 8, 8))
        self._body.pack(fill="both", expand=True)
        self._render_month()

        try:
            self.bind("<Escape>", lambda _e: self.destroy())
            self.focus_set()
        except Exception:
            pass

    @staticmethod
    def _parse_date(value: object) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _move_month(self, delta: int) -> None:
        index = self.year * 12 + (self.month - 1) + int(delta)
        self.year, month_index = divmod(index, 12)
        self.month = month_index + 1
        self._render_month()

    def _render_month(self) -> None:
        for child in self._body.winfo_children():
            child.destroy()

        month_names = (
            "", "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
        )
        self._title_var.set(f"{month_names[self.month]} {self.year}")
        for col, day_name in enumerate(("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")):
            ttk.Label(self._body, text=day_name, anchor="center", width=4).grid(
                row=0, column=col, padx=1, pady=(0, 2)
            )

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        for row_index, week in enumerate(weeks, start=1):
            for col, day_no in enumerate(week):
                if day_no <= 0:
                    ttk.Label(self._body, text="", width=4).grid(row=row_index, column=col, padx=1, pady=1)
                    continue
                ttk.Button(
                    self._body,
                    text=str(day_no),
                    width=4,
                    command=lambda d=day_no: self._pick(d),
                ).grid(row=row_index, column=col, padx=1, pady=1)

    def _pick(self, day_no: int) -> None:
        self.variable.set(f"{self.year:04d}-{self.month:02d}-{int(day_no):02d}")
        self.destroy()


def _open_edit_profile(view: Any) -> None:
    """Otwórz własny profil; data zatrudnienia ma przycisk kalendarza."""
    if not view._can_edit_profile():
        messagebox.showwarning(
            "Brak uprawnień",
            "Możesz edytować wyłącznie swój profil.",
            parent=view.winfo_toplevel(),
        )
        return

    fields, allow_pin, pin_min = view._user_editable_fields()
    if not fields and not allow_pin:
        messagebox.showinfo(
            "Profil",
            "W Ustawienia → Profile nie udostępniono żadnych pól do samodzielnej edycji.",
            parent=view.winfo_toplevel(),
        )
        return

    win = tk.Toplevel(view)
    win.title("Edytuj mój profil")
    apply_theme(win)
    win.transient(view.winfo_toplevel())
    win.grab_set()
    win.resizable(False, False)

    form = ttk.Frame(win, padding=12)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    user_data = get_user(view.login) or {"login": view.login}
    widgets: dict[str, tk.StringVar] = {}
    row = 0

    for field in fields:
        label = _FIELD_LABELS.get(field, field.replace("_", " ").capitalize())
        ttk.Label(form, text=f"{label}:").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        var = tk.StringVar(master=win, value=str(user_data.get(field, "") or ""))
        widgets[field] = var

        if field == "zatrudniony_od":
            date_box = ttk.Frame(form)
            date_box.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
            date_box.columnconfigure(0, weight=1)
            entry = ttk.Entry(date_box, textvariable=var, width=18)
            entry.grid(row=0, column=0, sticky="ew")
            ttk.Button(
                date_box,
                text="📅",
                width=4,
                command=lambda v=var: ProfileDatePicker(win, v),
            ).grid(row=0, column=1, padx=(6, 0))
        else:
            ttk.Entry(form, textvariable=var).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        row += 1

    pin_var: tk.StringVar | None = None
    if allow_pin:
        ttk.Label(form, text="PIN:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        pin_var = tk.StringVar(master=win, value=str(user_data.get("pin", "") or ""))
        ttk.Entry(form, textvariable=pin_var, show="*").grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(form, text=f"Min. długość: {pin_min}").grid(
            row=row, column=2, sticky="w", padx=(8, 0), pady=4
        )
        row += 1

    def _save() -> None:
        updated = dict(user_data)
        for field, var in widgets.items():
            value = str(var.get() or "").strip()
            if field == "zatrudniony_od" and value:
                try:
                    parsed = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    messagebox.showwarning(
                        "Data zatrudnienia",
                        "Wybierz datę z kalendarza albo wpisz ją jako RRRR-MM-DD.",
                        parent=win,
                    )
                    return
                value = parsed.isoformat()
            updated[field] = value

        if pin_var is not None:
            pin_text = str(pin_var.get() or "").strip()
            if pin_text and len(pin_text) < int(pin_min):
                messagebox.showwarning(
                    "PIN",
                    f"PIN musi mieć co najmniej {pin_min} znaki.",
                    parent=win,
                )
                return
            updated["pin"] = pin_text

        updated.setdefault("login", view.login)
        updated.setdefault("disabled_modules", [])
        try:
            save_user(updated)
        except Exception as exc:
            messagebox.showerror("Profil", f"Nie udało się zapisać profilu:\n{exc}", parent=win)
            return
        try:
            log_akcja(f"[PROFILE] Użytkownik {view.login} zaktualizował własny profil")
        except Exception:
            pass
        win.destroy()
        try:
            view._refresh_view()
        except Exception:
            pass

    buttons = ttk.Frame(form)
    buttons.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Zapisz", command=_save).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Anuluj", command=win.destroy).pack(side="left")


def _descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _status_key(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "w_toku": "w_toku",
        "wtoku": "w_toku",
        "wstrzymana": "wstrzymana",
        "nowa": "nowa",
        "zamknieta": "zamknieta",
        "zamknięta": "zamknieta",
    }
    return aliases.get(raw, raw)


def _active_rows(view: Any) -> list[dict[str, Any]]:
    rows = [
        row
        for row in list(getattr(view, "_dysp_cache", []) or [])
        if isinstance(row, dict) and _status_key(row.get("status")) != "zamknieta"
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("termin") or "9999-12-31"),
            str(row.get("tytul") or "").casefold(),
        )
    )
    return rows


def _selected_current_row(view: Any, tree: ttk.Treeview, *, show_message: bool = True) -> dict[str, Any] | None:
    selected = tree.selection()
    if not selected:
        if show_message:
            messagebox.showinfo("Profil", "Zaznacz Dyspozycję.", parent=view.winfo_toplevel())
        return None
    try:
        index = int(tree.index(selected[0]))
    except Exception:
        return None
    rows = _active_rows(view)
    if not (0 <= index < len(rows)):
        return None
    cached = rows[index]
    dysp_id = str(cached.get("id") or "").strip()
    current = get_dyspozycja(dysp_id) if dysp_id else None
    return dict(current or cached)


def _finish_selected(view: Any, tree: ttk.Treeview) -> None:
    row = _selected_current_row(view, tree)
    if not row:
        return

    status = _status_key(row.get("status"))
    dysp_id = str(row.get("id") or "").strip()
    print(f"[WM-DBG][PROFILE][DYSP] finish id={dysp_id} status={status}")
    try:
        log_akcja(f"[PROFILE][DYSP] Próba zakończenia {dysp_id}; status={status}")
    except Exception:
        pass

    if status == "nowa":
        messagebox.showinfo(
            "Zakończ Dyspozycję",
            "Ta Dyspozycja jest jeszcze Nowa. Najpierw kliknij „Rozpocznij Dyspozycję”, a potem ją zakończ.",
            parent=view.winfo_toplevel(),
        )
        return
    if status not in {"w_toku", "wstrzymana"}:
        messagebox.showinfo(
            "Zakończ Dyspozycję",
            f"Aktualny status nie pozwala na zakończenie: {row.get('status') or '—'}.",
            parent=view.winfo_toplevel(),
        )
        return

    note = simpledialog.askstring(
        "Zakończ Dyspozycję",
        "Uwagi przy zakończeniu (opcjonalnie):",
        parent=view.winfo_toplevel(),
    )
    if note is None:
        return

    actual_qty = None
    typ = str(row.get("typ_dyspozycji") or row.get("typ") or "").strip().lower()
    if typ in {"zlecenie_wykonania", "zamowienie"}:
        meta = dict(row.get("meta") or {}) if isinstance(row.get("meta"), dict) else {}
        try:
            planned = float(str(meta.get("ilosc_do_wykonania") or 0).replace(",", "."))
        except (TypeError, ValueError):
            planned = 0.0
        actual_qty = simpledialog.askfloat(
            "Rozlicz wykonanie",
            "Ile faktycznie wykonano?",
            initialvalue=planned if planned > 0 else 1,
            minvalue=0.0,
            parent=view.winfo_toplevel(),
        )
        if actual_qty is None:
            return

    who = str(getattr(view, "login", "") or row.get("autor") or "").strip()
    try:
        from dyspozycje_actions import DyspozycjaActionError, close_dyspozycja

        close_dyspozycja(
            row,
            who=who,
            note=str(note or ""),
            actual_qty=actual_qty,
        )
    except DyspozycjaActionError as exc:
        print(f"[WM-DBG][PROFILE][DYSP][BLOCK] id={dysp_id} error={exc}")
        messagebox.showerror("Profil — Dyspozycja", str(exc), parent=view.winfo_toplevel())
        return
    except Exception as exc:
        print(f"[WM-DBG][PROFILE][DYSP][ERROR] id={dysp_id} error={exc!r}")
        messagebox.showerror(
            "Profil — Dyspozycja",
            f"Nie udało się zakończyć Dyspozycji:\n{exc}",
            parent=view.winfo_toplevel(),
        )
        return

    try:
        view.winfo_toplevel().event_generate("<<DyspozycjeUpdated>>", when="tail")
    except Exception:
        pass
    messagebox.showinfo("Profil", "Dyspozycja została zakończona.", parent=view.winfo_toplevel())
    try:
        view._refresh_view()
    except Exception:
        pass


def _patch_finish_button(view: Any, parent: tk.Misc) -> None:
    tree = None
    finish_button = None
    for widget in _descendants(parent):
        if isinstance(widget, ttk.Treeview):
            try:
                if str(widget.cget("style")) == "Profile.Dyspozycje.Treeview":
                    tree = widget
            except Exception:
                pass
        elif isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == "Zakończ Dyspozycję":
                    finish_button = widget
            except Exception:
                pass
    if tree is None or finish_button is None:
        return

    finish_button.configure(command=lambda: _finish_selected(view, tree))

    def _sync_state(_event=None) -> None:
        row = _selected_current_row(view, tree, show_message=False)
        status = _status_key((row or {}).get("status"))
        try:
            finish_button.state(["!disabled"] if status in {"w_toku", "wstrzymana"} else ["disabled"])
        except Exception:
            pass

    tree.bind("<<TreeviewSelect>>", _sync_state, add="+")
    _sync_state()


def install(profile_view_cls: type) -> None:
    """Podepnij poprawki do finalnej klasy ``gui_profile.ProfileView``."""
    if getattr(profile_view_cls, "_wm_user_actions_runtime", False):
        return

    original_render = profile_view_cls._render_simple_profile

    def _render_simple_profile(self, parent, *args, **kwargs):
        result = original_render(self, parent, *args, **kwargs)
        try:
            _patch_finish_button(self, parent)
        except Exception as exc:
            print(f"[WM-DBG][PROFILE][DYSP][PATCH-WARN] {exc!r}")
        return result

    profile_view_cls._render_simple_profile = _render_simple_profile
    profile_view_cls._open_edit_profile = _open_edit_profile
    profile_view_cls._wm_user_actions_runtime = True


__all__ = [
    "ProfileDatePicker",
    "_active_rows",
    "_selected_current_row",
    "_status_key",
    "install",
]
