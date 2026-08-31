# version: 1.2
import sys
from types import ModuleType
import tkinter as tk
from tkinter import ttk

import profile_user_actions_runtime as runtime


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def test_edit_profile_has_calendar_for_employment_date(monkeypatch):
    root = tk.Tk()
    root.withdraw()
    saved = []
    try:
        view = ttk.Frame(root)
        view.pack()
        view.login = "edwin"
        view._can_edit_profile = lambda: True
        view._user_editable_fields = lambda: (["imie", "zatrudniony_od", "telefon"], False, 4)
        view._refresh_view = lambda: None

        monkeypatch.setattr(
            runtime,
            "get_user",
            lambda _login: {
                "login": "edwin",
                "imie": "Edwin",
                "zatrudniony_od": "2020-05-12",
                "telefon": "123",
            },
        )
        monkeypatch.setattr(runtime, "save_user", lambda row: saved.append(dict(row)))

        runtime._open_edit_profile(view)
        root.update_idletasks()
        dialog = next(widget for widget in _walk(root) if isinstance(widget, tk.Toplevel))

        buttons = [w for w in _walk(dialog) if isinstance(w, ttk.Button)]
        calendar_button = next(w for w in buttons if str(w.cget("text")) == "📅")
        calendar_button.invoke()
        root.update_idletasks()

        picker = next(
            widget
            for widget in _walk(dialog)
            if isinstance(widget, runtime.ProfileDatePicker)
        )
        picker.year = 2021
        picker.month = 7
        picker._pick(9)
        root.update_idletasks()

        entries = [w for w in _walk(dialog) if isinstance(w, ttk.Entry)]
        values = [entry.get() for entry in entries]
        assert "2021-07-09" in values
        assert runtime.ProfileDatePicker._parse_date("2021-07-09").isoformat() == "2021-07-09"
    finally:
        root.destroy()


def test_profile_finish_uses_fresh_store_row_and_accepts_display_status(monkeypatch):
    root = tk.Tk()
    root.withdraw()
    calls = []
    infos = []
    errors = []
    try:
        view = ttk.Frame(root)
        view.pack()
        view.login = "edwin"
        # Cache celowo jest stary: status "Nowa". Store zwróci świeże "W toku".
        view._dysp_cache = [
            {
                "id": "DYSP-TEST",
                "status": "Nowa",
                "termin": "2026-09-01",
                "tytul": "Test",
                "typ_dyspozycji": "maszyna",
            }
        ]
        view._refresh_view = lambda: calls.append(("refresh",))

        tree = ttk.Treeview(root, columns=("x",), show="headings")
        iid = tree.insert("", "end", values=("Test",))
        tree.selection_set(iid)

        monkeypatch.setattr(
            runtime,
            "get_dyspozycja",
            lambda _dysp_id: {
                "id": "DYSP-TEST",
                "status": "W toku",
                "termin": "2026-09-01",
                "tytul": "Test",
                "typ_dyspozycji": "maszyna",
            },
        )
        monkeypatch.setattr(runtime.simpledialog, "askstring", lambda *a, **k: "gotowe")
        monkeypatch.setattr(runtime.messagebox, "showinfo", lambda *a, **k: infos.append((a, k)))
        monkeypatch.setattr(runtime.messagebox, "showerror", lambda *a, **k: errors.append((a, k)))

        fake_actions = ModuleType("dyspozycje_actions")

        class FakeDyspozycjaActionError(RuntimeError):
            pass

        fake_actions.DyspozycjaActionError = FakeDyspozycjaActionError
        fake_actions.close_dyspozycja = (
            lambda row, **kwargs: calls.append(("close", dict(row), dict(kwargs))) or dict(row)
        )
        monkeypatch.setitem(sys.modules, "dyspozycje_actions", fake_actions)

        runtime._finish_selected(view, tree)

        close_calls = [item for item in calls if item[0] == "close"]
        assert len(close_calls) == 1
        assert close_calls[0][1]["status"] == "W toku"
        assert close_calls[0][2]["who"] == "edwin"
        assert close_calls[0][2]["note"] == "gotowe"
        assert errors == []
        assert runtime._status_key("W toku") == "w_toku"
        assert ("refresh",) in calls
    finally:
        root.destroy()
