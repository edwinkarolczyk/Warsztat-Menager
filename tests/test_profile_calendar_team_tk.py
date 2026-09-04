import tkinter as tk
from tkinter import ttk

import gui_profile_calendar as calendar_ui
import profile_calendar_team_runtime as team_runtime


def _walk(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_walk(child))
    return out


def test_foreman_calendar_has_my_team_toggle_and_compact_day(monkeypatch):
    monkeypatch.setattr(team_runtime, "_is_foreman", lambda: True)
    monkeypatch.setattr(calendar_ui.ProfileCalendarPanel, "refresh", lambda self: None)
    team_runtime.install()

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
    monkeypatch.setattr(team_runtime, "_team_day_rows", lambda _day: sample_rows)

    root = tk.Tk()
    try:
        panel = calendar_ui.ProfileCalendarPanel(root, login="edwin")
        panel.pack(fill="both", expand=True)
        panel.year = 2026
        panel.month = 9
        panel._snapshot = {"leaves": [], "requests": []}
        root.update_idletasks()

        radios = [
            str(widget.cget("text"))
            for widget in _walk(panel)
            if isinstance(widget, ttk.Radiobutton)
        ]
        assert "Mój" in radios
        assert "Zespół" in radios

        panel._wm_calendar_mode.set("Zespół")
        panel._render_calendar()
        root.update_idletasks()
        day_texts = [
            str(widget.cget("text"))
            for widget in panel.calendar_box.winfo_children()
            if isinstance(widget, tk.Button)
        ]
        assert any("Marek 14–22" in text for text in day_texts)
        assert any("Dawid ŚW" in text for text in day_texts)
    finally:
        root.destroy()
