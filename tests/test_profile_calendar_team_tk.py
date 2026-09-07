# version: 1.2
import tkinter as tk
from tkinter import ttk

import gui_profile_calendar as calendar_ui
import profile_calendar_team_runtime as team_runtime
import profile_foreman_workspace_runtime as workspace


def _walk(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_walk(child))
    return out


def test_foreman_calendar_is_single_advanced_view_with_inline_day(monkeypatch):
    monkeypatch.setattr(team_runtime, "_is_foreman", lambda: True)
    monkeypatch.setattr(calendar_ui.ProfileCalendarPanel, "refresh", lambda self: None)
    team_runtime.install()
    workspace.install()

    sample_rows = [
        {
            "login": "marek",
            "name": "Marek",
            "short_name": "Marek",
            "slot": "POPO",
            "shift": "14–22",
            "status_code": "PLAN",
            "status": "Zaplanowana zmiana",
            "summary": "14–22",
            "pay_percent": None,
            "pay_label": "—",
        },
        {
            "login": "dawid",
            "name": "Dawid Karolczyk",
            "short_name": "Dawid",
            "slot": "RANO",
            "shift": "06–14",
            "status_code": "ŚW",
            "status": "Siła wyższa",
            "summary": "ŚW",
            "pay_percent": 50.0,
            "pay_label": "50%",
        },
    ]
    # Prawy panel szczegółów czyta pojedynczy dzień, a kafelki miesiąca korzystają
    # z szybkiego snapshotu zbiorczego. Test podmienia oba wejścia celowo.
    monkeypatch.setattr(team_runtime, "_team_day_rows", lambda _day: sample_rows)
    monkeypatch.setattr(
        team_runtime,
        "_team_month_rows",
        lambda _year, _month: {day: sample_rows for day in range(1, 31)},
    )

    root = tk.Tk()
    try:
        panel = calendar_ui.ProfileCalendarPanel(root, login="edwin")
        panel.pack(fill="both", expand=True)
        panel.year = 2026
        panel.month = 9
        panel._snapshot = {"leaves": [], "requests": []}
        panel._render_calendar()
        root.update_idletasks()

        # Brygadzista nie przełącza już między dwoma kalendarzami.
        radios = [
            str(widget.cget("text"))
            for widget in _walk(panel)
            if isinstance(widget, ttk.Radiobutton)
        ]
        assert "Mój" not in radios
        assert "Zespół" not in radios

        # Kafelki nadal pokazują skrót Zespołu z miesięcznego snapshotu.
        day_buttons = [
            widget
            for widget in panel.calendar_box.winfo_children()
            if isinstance(widget, tk.Button)
        ]
        day_texts = [str(widget.cget("text")) for widget in day_buttons]
        assert any("Marek 14–22" in text for text in day_texts)
        assert any("Dawid ŚW" in text for text in day_texts)

        # Szczegóły dnia są częścią tego samego panelu, a kliknięcie dnia
        # nie tworzy już osobnego Toplevela.
        detail_tree = panel._wm_team_detail_tree
        assert len(detail_tree.get_children()) == 2
        before_windows = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
        day_buttons[0].invoke()
        root.update_idletasks()
        after_windows = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
        assert after_windows == before_windows
    finally:
        root.destroy()
